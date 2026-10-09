"""Node 6: Mitigation Narrative Builder — LLM-driven drafting from fact sheet.

Uses LLM to draft a mitigation narrative grounded in the structured fact sheet.

A failed model call fails the node (PHASE_1_MODEL_GATEWAY.md §0.4); the labeled
fallback narrative is removed. With no mitigation facts the node abstains — a
deterministic, explicitly labeled "nothing to draft from" — rather than calling the
model.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from src.models.responses.sentencing import NarrativeDraft
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

from ..models.outputs import MitigationNarrative, NodeAuditRecord
from ..models.state import SentencingGraphState

logger = logging.getLogger(__name__)

# Prompts: src/prompts/sentencing_agent/
_SYSTEM = load_prompt("sentencing_agent.mitigation_narrative", "v1")
_INPUT = load_prompt("sentencing_agent.mitigation_input", "v1")
# Thinking tokens count toward max_tokens on current models (Phase 1 §2).
_MAX_TOKENS = 16000


def _build_narrative_prompt(state: SentencingGraphState) -> tuple[str, str]:
    """Build the system and user prompts for mitigation narrative drafting."""
    input_data = state["input"]
    fact_sheet = state.get("mitigation_fact_sheet")
    user_prompt = _INPUT.text.format(
        statute=input_data.offense_details.statute,
        charge_description=input_data.offense_details.charge_description,
        county=input_data.jurisdiction_context.county,
        fact_sheet=(
            json.dumps(fact_sheet, default=str, indent=2)
            if fact_sheet
            else "No facts available — narrative cannot be drafted."
        ),
    )
    return _SYSTEM.text, user_prompt


def _to_narrative(draft: NarrativeDraft) -> MitigationNarrative:
    return MitigationNarrative(**draft.model_dump())


def _abstention_narrative() -> MitigationNarrative:
    """No mitigation facts in the record: say so instead of drafting (CLAUDE.md §4.5)."""
    return MitigationNarrative(
        summary="The record contains no mitigation facts, so no narrative was drafted.",
        full_narrative="",
        tone_notes="Abstained: nothing in the record to draft from.",
    )


async def mitigation_narrative_builder(state: SentencingGraphState) -> SentencingGraphState:
    """Mitigation narrative builder node — drafts narrative from fact sheet."""
    started_at = datetime.now(timezone.utc).isoformat()
    audit_records: list[NodeAuditRecord] = list(state.get("audit_records") or [])
    warnings: list[str] = list(state.get("warnings") or [])

    if state.get("scope_status") != "in_scope":
        audit_records.append(
            NodeAuditRecord(
                node_name="mitigation_narrative_builder",
                status="skipped",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                warnings=["Skipped: case is not in scope"],
                output_keys=[],
            )
        )
        state["audit_records"] = audit_records
        return state

    fact_sheet = state.get("mitigation_fact_sheet")
    if not fact_sheet or fact_sheet.get("fact_count", 0) == 0:
        warnings.append("No mitigation facts available — no narrative drafted")
        state["mitigation_narrative"] = _abstention_narrative()
        state["warnings"] = warnings
        audit_records.append(
            NodeAuditRecord(
                node_name="mitigation_narrative_builder",
                status="warning",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                warnings=["No mitigation facts available"],
                output_keys=["mitigation_narrative"],
            )
        )
        state["audit_records"] = audit_records
        return state

    system_prompt, user_prompt = _build_narrative_prompt(state)
    result = await call_model(
        ModelCallRequest(
            prompt=user_prompt,
            system=system_prompt,
            max_tokens=_MAX_TOKENS,
            response_model=NarrativeDraft,
            prompt_id="sentencing_agent.mitigation_narrative",
            prompt_version=compose_version(_SYSTEM, _INPUT),
            agent_id="sentencing_agent",
        )
    )
    narrative = _to_narrative(result.data)
    if not narrative.full_narrative:
        warnings.append("Model returned an empty narrative")

    state["mitigation_narrative"] = narrative
    state["warnings"] = warnings
    audit_records.append(
        NodeAuditRecord(
            node_name="mitigation_narrative_builder",
            status="ok" if not narrative.unsupported_claim_warnings else "warning",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            warnings=warnings,
            output_keys=["mitigation_narrative"],
        )
    )
    state["audit_records"] = audit_records
    return state
