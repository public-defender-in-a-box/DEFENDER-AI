"""Node 7: Comparable Sentence Lookup — Local seed corpus matching.

Deterministic local retrieval. No LLM calls in MVP.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..config import COMPARABLES_PATH, MAX_COMPARABLES, MIN_COMPARABLES_WARNING_THRESHOLD
from ..models.inputs import SentencingAgentInput
from ..models.outputs import ComparableSentence, NodeAuditRecord
from ..models.state import SentencingGraphState


def load_comparables_corpus() -> list[dict[str, Any]]:
    """Load the Georgia marijuana comparables seed data."""
    with open(COMPARABLES_PATH) as f:
        return json.load(f)


def _prior_record_level(input_data: SentencingAgentInput) -> str:
    """Derive a simplified prior-record level for matching."""
    history = input_data.criminal_history
    if not history.has_prior_convictions:
        return "none"
    total = history.prior_felonies + history.prior_misdemeanors
    if total == 1:
        return "one_prior_misdemeanor" if history.prior_felonies == 0 else "one_prior_felony"
    return "multiple_priors"


def _score_comparable(
    comp: dict[str, Any],
    county: str,
    circuit: str | None,
    prior_level: str,
) -> float:
    """Score a comparable record by match quality. Higher is better."""
    score = 0.0

    # Priority 1: county match
    if comp.get("county", "").lower() == county.lower():
        score += 4.0

    # Priority 2: judicial circuit match
    if circuit and comp.get("judicial_circuit", "").lower() == circuit.lower():
        score += 2.0

    # Priority 3: prior record level match
    if comp.get("defendant_profile", {}).get("prior_record_level") == prior_level:
        score += 1.5

    # Priority 4: verified source bonus
    if comp.get("verification_status") == "confirmed":
        score += 0.5

    return score


def find_comparable_sentences(
    input_data: SentencingAgentInput,
    corpus: list[dict[str, Any]] | None = None,
) -> list[ComparableSentence]:
    """Find matching comparable sentences from the seed corpus."""
    if corpus is None:
        corpus = load_comparables_corpus()

    county = input_data.jurisdiction_context.county
    circuit = input_data.jurisdiction_context.judicial_circuit
    prior_level = _prior_record_level(input_data)

    # Score and sort
    scored = [(comp, _score_comparable(comp, county, circuit, prior_level)) for comp in corpus]
    scored.sort(key=lambda x: x[1], reverse=True)

    # Take top N
    results: list[ComparableSentence] = []
    for comp, _score in scored[:MAX_COMPARABLES]:
        profile = comp.get("defendant_profile", {})
        disposition = comp.get("disposition", {})

        results.append(
            ComparableSentence(
                description=disposition.get("outcome_description", ""),
                offense=comp.get("offense", ""),
                defendant_profile=(
                    f"Prior record: {profile.get('prior_record_level', 'unknown')}, "
                    f"Age: {profile.get('age_range', 'unknown')}, "
                    f"Employment: {profile.get('employment_status', 'unknown')}"
                ),
                sentence_imposed=disposition.get("outcome_description", ""),
                jurisdiction=f"{comp.get('county', 'Unknown')} County, {comp.get('judicial_circuit', 'Unknown')} Circuit",
                date=comp.get("date"),
                source=comp.get("source", "verified_corpus"),
                verification_status=comp.get("verification_status", "confirmed"),
                source_ref=comp.get("source_ref"),
                relevance_notes=comp.get("notes", ""),
            )
        )

    return results


def comparable_sentence_lookup(state: SentencingGraphState) -> SentencingGraphState:
    """Comparable sentence lookup node — matches against local seed corpus."""
    started_at = datetime.now(timezone.utc).isoformat()
    audit_records: list[NodeAuditRecord] = list(state.get("audit_records") or [])
    warnings: list[str] = list(state.get("warnings") or [])

    if state.get("scope_status") != "in_scope":
        audit_records.append(
            NodeAuditRecord(
                node_name="comparable_sentence_lookup",
                status="skipped",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                warnings=["Skipped: case is not in scope"],
                output_keys=[],
            )
        )
        state["audit_records"] = audit_records
        return state

    input_data = state["input"]

    # Bundled seed data: a load failure is a bug and raises (Phase 1 §3.2).
    comparables = find_comparable_sentences(input_data)

    if len(comparables) < MIN_COMPARABLES_WARNING_THRESHOLD:
        warnings.append(
            f"Only {len(comparables)} comparable(s) found — limited county/circuit data in current corpus"
        )

    state["comparable_sentences"] = comparables
    state["warnings"] = warnings
    audit_records.append(
        NodeAuditRecord(
            node_name="comparable_sentence_lookup",
            status="ok" if len(comparables) >= MIN_COMPARABLES_WARNING_THRESHOLD else "warning",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            warnings=warnings,
            output_keys=["comparable_sentences"],
        )
    )
    state["audit_records"] = audit_records
    return state
