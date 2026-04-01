"""Node 9: Output Assembler — Merges all node outputs into final SentencingAgentOutput.

Deterministic. Computes confidence, adds ethics flags, preserves warnings and provenance.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..config import (
    CONFIDENCE_WEIGHTS,
    MAX_CONFIDENCE_OUT_OF_SCOPE,
    MAX_CONFIDENCE_SELF_REPORTED_HISTORY,
)
from ..models.inputs import VerificationStatus
from ..models.outputs import (
    NodeAuditRecord,
    SectionConfidence,
    SentencingAgentOutput,
)
from ..models.state import SentencingGraphState


def calculate_confidence(factors: dict[str, float]) -> float:
    """Calculate overall confidence from weighted factors."""
    return round(
        sum(factors.get(k, 0.0) * w for k, w in CONFIDENCE_WEIGHTS.items()),
        3,
    )


def _compute_confidence_factors(state: SentencingGraphState) -> dict[str, float]:
    """Compute individual confidence factors from state."""
    input_data = state["input"]
    factors: dict[str, float] = {}

    # Scope validation
    factors["scope_validation"] = 1.0 if state.get("scope_status") == "in_scope" else 0.0

    # Criminal history verification
    ver = input_data.criminal_history.verification_status
    if ver == VerificationStatus.VERIFIED:
        factors["criminal_history_verified"] = 1.0
    elif ver == VerificationStatus.MIXED:
        factors["criminal_history_verified"] = 0.6
    elif ver == VerificationStatus.SELF_REPORTED:
        factors["criminal_history_verified"] = 0.3
    else:
        factors["criminal_history_verified"] = 0.2

    # Local context
    has_county = bool(input_data.jurisdiction_context.county)
    has_circuit = bool(input_data.jurisdiction_context.judicial_circuit)
    factors["local_context_present"] = 1.0 if (has_county and has_circuit) else (0.6 if has_county else 0.2)

    # Diversion availability quality
    diversion_opts = state.get("diversion_options") or []
    if diversion_opts:
        confirmed = sum(1 for d in diversion_opts if d.availability_status == "confirmed_available")
        factors["diversion_availability_quality"] = min(1.0, confirmed / max(len(diversion_opts), 1))
    else:
        factors["diversion_availability_quality"] = 0.0

    # Mitigation fact coverage
    fact_sheet = state.get("mitigation_fact_sheet")
    if fact_sheet:
        count = fact_sheet.get("fact_count", 0)
        factors["mitigation_fact_coverage"] = min(1.0, count / 5.0)  # 5+ facts = full score
    else:
        factors["mitigation_fact_coverage"] = 0.0

    # Comparable sentence quality
    comparables = state.get("comparable_sentences") or []
    factors["comparable_sentence_quality"] = min(1.0, len(comparables) / 3.0)

    # LLM outputs schema valid
    narrative = state.get("mitigation_narrative")
    departure_args = state.get("departure_arguments")
    valid_count = 0
    total_count = 2
    if narrative and narrative.full_narrative:
        valid_count += 1
    if departure_args:
        valid_count += 1
    factors["llm_outputs_schema_valid"] = valid_count / total_count

    return factors


def _compute_section_confidences(state: SentencingGraphState) -> list[SectionConfidence]:
    """Compute per-section confidence scores."""
    sections: list[SectionConfidence] = []

    # Exposure
    guideline = state.get("guideline_range")
    sections.append(
        SectionConfidence(
            section_name="sentencing_exposure",
            score=0.95 if guideline else 0.0,
            reasons=["Deterministic calculation from verified statute data"] if guideline else ["Not calculated"],
        )
    )

    # Diversion
    diversion = state.get("diversion_options") or []
    div_confirmed = sum(1 for d in diversion if d.availability_status == "confirmed_available")
    div_score = 0.8 if div_confirmed > 0 else 0.4
    sections.append(
        SectionConfidence(
            section_name="diversion_options",
            score=div_score,
            reasons=[f"{div_confirmed} program(s) with confirmed availability"],
        )
    )

    # Mitigation narrative
    narrative = state.get("mitigation_narrative")
    if narrative and not narrative.unsupported_claim_warnings:
        narr_score = 0.8
        reasons = ["Narrative drafted from fact sheet"]
    elif narrative:
        narr_score = 0.5
        reasons = [f"{len(narrative.unsupported_claim_warnings)} unsupported claim warning(s)"]
    else:
        narr_score = 0.0
        reasons = ["No narrative generated"]
    sections.append(SectionConfidence(section_name="mitigation_narrative", score=narr_score, reasons=reasons))

    # Comparable sentences
    comparables = state.get("comparable_sentences") or []
    comp_score = min(0.9, len(comparables) * 0.2)
    sections.append(
        SectionConfidence(
            section_name="comparable_sentences",
            score=comp_score,
            reasons=[f"{len(comparables)} comparable(s) found"],
        )
    )

    # Memo
    memo = state.get("sentencing_memo")
    sections.append(
        SectionConfidence(
            section_name="sentencing_memo",
            score=0.7 if memo else 0.0,
            reasons=["Template-based memo generated"] if memo else ["No memo generated"],
        )
    )

    return sections


def output_assembler(state: SentencingGraphState) -> SentencingGraphState:
    """Output assembler node — merges all outputs into final result."""
    started_at = datetime.now(timezone.utc).isoformat()
    audit_records: list[NodeAuditRecord] = list(state.get("audit_records") or [])
    input_data = state["input"]
    warnings: list[str] = list(state.get("warnings") or [])
    ethics_flags: list[str] = list(state.get("ethics_flags") or [])
    flags: list[str] = list(state.get("flags") or [])

    scope_status = state.get("scope_status", "insufficient_data")

    # Compute confidence
    factors = _compute_confidence_factors(state)
    confidence = calculate_confidence(factors)

    # Apply confidence caps
    if scope_status != "in_scope":
        confidence = min(confidence, MAX_CONFIDENCE_OUT_OF_SCOPE)

    if input_data.criminal_history.verification_status == VerificationStatus.SELF_REPORTED:
        confidence = min(confidence, MAX_CONFIDENCE_SELF_REPORTED_HISTORY)
        if "SELF_REPORTED_CRIMINAL_HISTORY" not in str(ethics_flags):
            ethics_flags.append(
                "SELF_REPORTED_CRIMINAL_HISTORY: criminal history verification recommended"
            )

    # Check for unverified authority
    authority_bundle = state.get("authority_bundle") or {}
    if authority_bundle.get("missing_statutes"):
        ethics_flags.append(
            f"MISSING_AUTHORITY: {len(authority_bundle['missing_statutes'])} statute(s) not found in corpus"
        )

    # Narrative unsupported claims check
    narrative = state.get("mitigation_narrative")
    if narrative and narrative.unsupported_claim_warnings:
        flags.append("UNSUPPORTED_CLAIMS_IN_NARRATIVE: memo mitigation section marked EDIT_REQUIRED")

    # Section confidences
    section_confidence = _compute_section_confidences(state)

    # Attorney decision points
    attorney_decision_points = list(state.get("attorney_decision_points") or [])
    if scope_status == "in_scope":
        attorney_decision_points.append(
            "Review all sections marked ANNOTATION_REQUIRED before any filing or client communication"
        )

    audit_records.append(
        NodeAuditRecord(
            node_name="output_assembler",
            status="ok",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            output_keys=["final_output"],
        )
    )

    # Store assembled output in state for the graph to return
    # The actual SentencingAgentOutput is constructed by the graph runner
    state["flags"] = flags
    state["warnings"] = warnings
    state["ethics_flags"] = ethics_flags
    state["attorney_decision_points"] = attorney_decision_points
    state["audit_records"] = audit_records

    # Store computed values for the graph runner to pick up
    state["_confidence_score"] = confidence
    state["_section_confidence"] = section_confidence
    state["_timestamp"] = datetime.now(timezone.utc).isoformat()

    return state
