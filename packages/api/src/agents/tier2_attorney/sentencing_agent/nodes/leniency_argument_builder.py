"""Node 5: Leniency / Alternative Sentence Builder — LLM-assisted argument generation.

Generates candidate leniency arguments from a deterministic menu,
then uses LLM to explain and strengthen them based on case facts.

A failed model call fails the node (PHASE_1_MODEL_GATEWAY.md §0.4): the labeled
deterministic fallback that used to stand in for the model's arguments is removed.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from src.models.responses.sentencing import LeniencyArguments
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

from ..models.outputs import DepartureArgument, NodeAuditRecord
from ..models.state import SentencingGraphState

logger = logging.getLogger(__name__)

# Prompts: src/prompts/sentencing_agent/
_SYSTEM = load_prompt("sentencing_agent.leniency_arguments", "v1")
_INPUT = load_prompt("sentencing_agent.leniency_input", "v1")
# Thinking tokens count toward max_tokens on current models (Phase 1 §2).
_MAX_TOKENS = 16000


def _build_deterministic_candidates(state: SentencingGraphState) -> list[dict[str, Any]]:
    """Build deterministic candidate arguments from the available data."""
    candidates: list[dict[str, Any]] = []
    input_data = state["input"]
    diversion_options = state.get("diversion_options") or []
    fact_sheet = state.get("mitigation_fact_sheet")
    guideline_range = state.get("guideline_range")

    themes = fact_sheet.get("themes", []) if fact_sheet else []

    # Always available for misdemeanor
    candidates.append(
        {
            "argument_type": "alternative_sentence",
            "basis": "Straight probation",
            "applicable_authority": ["O.C.G.A. § 42-8-34"],
            "authority_verification_status": "confirmed",
        }
    )

    candidates.append(
        {
            "argument_type": "alternative_sentence",
            "basis": "Suspended sentence",
            "applicable_authority": ["O.C.G.A. § 42-8-34"],
            "authority_verification_status": "confirmed",
        }
    )

    candidates.append(
        {
            "argument_type": "alternative_sentence",
            "basis": "Fine-only disposition",
            "applicable_authority": ["O.C.G.A. § 16-13-2(b)", "O.C.G.A. § 17-10-3"],
            "authority_verification_status": "confirmed",
        }
    )

    candidates.append(
        {
            "argument_type": "alternative_sentence",
            "basis": "Community service",
            "applicable_authority": ["O.C.G.A. § 17-10-3"],
            "authority_verification_status": "confirmed",
        }
    )

    # Weekend service if applicable
    if guideline_range and guideline_range.weekend_service_possible:
        candidates.append(
            {
                "argument_type": "alternative_sentence",
                "basis": "Weekend service (if jail is 180 days or less)",
                "applicable_authority": ["O.C.G.A. § 17-10-3"],
                "authority_verification_status": "confirmed",
            }
        )

    # Time served
    if input_data.pretrial_custody_days > 0:
        candidates.append(
            {
                "argument_type": "alternative_sentence",
                "basis": f"Time served ({input_data.pretrial_custody_days} days pretrial custody)",
                "applicable_authority": [],
                "authority_verification_status": "not_applicable",
            }
        )

    # Conditional discharge if eligible
    for opt in diversion_options:
        if opt.program_name == "Conditional Discharge" and opt.preliminary_eligibility == "yes":
            candidates.append(
                {
                    "argument_type": "alternative_sentence",
                    "basis": "Conditional discharge — first offense, no prior drug convictions",
                    "applicable_authority": ["O.C.G.A. § 16-13-2(a)", "O.C.G.A. § 35-3-37"],
                    "authority_verification_status": "confirmed",
                }
            )

    # Treatment-focused if relevant
    if "treatment_engagement" in themes:
        candidates.append(
            {
                "argument_type": "mitigating_factor",
                "basis": "Treatment engagement and rehabilitation efforts",
                "applicable_authority": [],
                "authority_verification_status": "not_applicable",
            }
        )

    # Employment stability
    if "employment_stability" in themes:
        candidates.append(
            {
                "argument_type": "mitigating_factor",
                "basis": "Stable employment",
                "applicable_authority": [],
                "authority_verification_status": "not_applicable",
            }
        )

    # Caregiving
    if "caregiving" in themes:
        candidates.append(
            {
                "argument_type": "mitigating_factor",
                "basis": "Caregiving responsibilities",
                "applicable_authority": [],
                "authority_verification_status": "not_applicable",
            }
        )

    # No prior record
    if "low_public_safety_risk" in themes:
        candidates.append(
            {
                "argument_type": "mitigating_factor",
                "basis": "No prior criminal record — low public safety risk",
                "applicable_authority": [],
                "authority_verification_status": "not_applicable",
            }
        )

    return candidates


def _build_llm_prompt(
    state: SentencingGraphState, candidates: list[dict[str, Any]]
) -> tuple[str, str]:
    """Build the system and user prompts for leniency argument generation."""
    input_data = state["input"]
    fact_sheet = state.get("mitigation_fact_sheet")
    guideline_range = state.get("guideline_range")

    user_prompt = _INPUT.text.format(
        statute=input_data.offense_details.statute,
        charge_description=input_data.offense_details.charge_description,
        quantity=input_data.offense_details.quantity_text or "not specified",
        fact_sheet=(
            json.dumps(fact_sheet, default=str, indent=2) if fact_sheet else "No facts available"
        ),
        exposure=(
            json.dumps(guideline_range.model_dump(), default=str, indent=2)
            if guideline_range
            else "Not calculated"
        ),
        candidates=json.dumps(candidates, indent=2),
        diversion_options=json.dumps(
            [opt.model_dump() for opt in (state.get("diversion_options") or [])],
            default=str,
            indent=2,
        ),
    )
    return _SYSTEM.text, user_prompt


def _to_departure_arguments(response: LeniencyArguments) -> list[DepartureArgument]:
    """Convert the validated response; field-for-field, so it cannot drop an item."""
    return [DepartureArgument(**argument.model_dump()) for argument in response.arguments]


async def leniency_argument_builder(state: SentencingGraphState) -> SentencingGraphState:
    """Leniency argument builder node — generates and explains alternative sentence arguments."""
    started_at = datetime.now(timezone.utc).isoformat()
    audit_records: list[NodeAuditRecord] = list(state.get("audit_records") or [])
    warnings: list[str] = list(state.get("warnings") or [])

    if state.get("scope_status") != "in_scope":
        audit_records.append(
            NodeAuditRecord(
                node_name="leniency_argument_builder",
                status="skipped",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                warnings=["Skipped: case is not in scope"],
                output_keys=[],
            )
        )
        state["audit_records"] = audit_records
        return state

    candidates = _build_deterministic_candidates(state)

    system_prompt, user_prompt = _build_llm_prompt(state, candidates)
    result = await call_model(
        ModelCallRequest(
            prompt=user_prompt,
            system=system_prompt,
            max_tokens=_MAX_TOKENS,
            response_model=LeniencyArguments,
            prompt_id="sentencing_agent.leniency_arguments",
            prompt_version=compose_version(_SYSTEM, _INPUT),
            agent_id="sentencing_agent",
        )
    )
    arguments = _to_departure_arguments(result.data)
    if not arguments:
        # A valid answer (no menu item is supported by the facts), recorded as such.
        warnings.append("Model returned no leniency arguments")

    state["departure_arguments"] = arguments
    state["warnings"] = warnings
    audit_records.append(
        NodeAuditRecord(
            node_name="leniency_argument_builder",
            status="ok",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            warnings=warnings,
            output_keys=["departure_arguments"],
        )
    )
    state["audit_records"] = audit_records
    return state
