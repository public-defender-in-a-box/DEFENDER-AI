"""Node 5: Leniency / Alternative Sentence Builder — LLM-assisted argument generation.

Generates candidate leniency arguments from a deterministic menu,
then uses LLM to explain and strengthen them based on case facts.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.services.llm_service import call_llm

from ..models.outputs import DepartureArgument, NodeAuditRecord
from ..models.state import SentencingGraphState

logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "leniency_arguments.txt"


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
    system_prompt = PROMPT_PATH.read_text()

    input_data = state["input"]
    fact_sheet = state.get("mitigation_fact_sheet")
    guideline_range = state.get("guideline_range")

    user_prompt = f"""
OFFENSE DETAILS:
- Statute: {input_data.offense_details.statute}
- Description: {input_data.offense_details.charge_description}
- Quantity: {input_data.offense_details.quantity_text or "not specified"}

MITIGATION FACT SHEET:
{json.dumps(fact_sheet, default=str, indent=2) if fact_sheet else "No facts available"}

SENTENCING EXPOSURE:
{json.dumps(guideline_range.model_dump(), default=str, indent=2) if guideline_range else "Not calculated"}

CANDIDATE ARGUMENTS:
{json.dumps(candidates, indent=2)}

DIVERSION OPTIONS:
{json.dumps([opt.model_dump() for opt in (state.get("diversion_options") or [])], default=str, indent=2)}

Return valid JSON array matching the required schema."""

    return system_prompt, user_prompt


def _parse_llm_response(raw: dict[str, Any]) -> list[DepartureArgument]:
    """Parse LLM response into DepartureArgument objects."""
    # Handle both direct array and wrapped response
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict) and "arguments" in raw:
        items = raw["arguments"]
    else:
        # Empty dict or unrecognized format — return nothing
        items = []

    results: list[DepartureArgument] = []
    for item in items:
        try:
            results.append(
                DepartureArgument(
                    argument_type=item.get("argument_type", "judicial_discretion_argument"),
                    basis=item.get("basis", ""),
                    supporting_facts=item.get("supporting_facts", []),
                    supporting_fact_ids=item.get("supporting_fact_ids", []),
                    strength=item.get("strength", "moderate"),
                    applicable_authority=item.get("applicable_authority", []),
                    authority_verification_status=item.get(
                        "authority_verification_status", "not_applicable"
                    ),
                    notes=item.get("notes", ""),
                )
            )
        except Exception:
            continue

    return results


def _fallback_arguments(candidates: list[dict[str, Any]]) -> list[DepartureArgument]:
    """Generate fallback arguments without LLM if the call fails."""
    results: list[DepartureArgument] = []
    for cand in candidates:
        results.append(
            DepartureArgument(
                argument_type=cand.get("argument_type", "alternative_sentence"),
                basis=cand.get("basis", ""),
                supporting_facts=[],
                supporting_fact_ids=[],
                strength="moderate",
                applicable_authority=cand.get("applicable_authority", []),
                authority_verification_status=cand.get(
                    "authority_verification_status", "not_applicable"
                ),
                notes="Generated without LLM refinement — attorney review required",
            )
        )
    return results


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

    try:
        system_prompt, user_prompt = _build_llm_prompt(state, candidates)
        raw = await call_llm(user_prompt, system=system_prompt, max_tokens=4096)
        arguments = _parse_llm_response(raw)

        if not arguments:
            warnings.append("LLM returned no valid arguments — using fallback")
            arguments = _fallback_arguments(candidates)

    except Exception as e:
        logger.warning("Leniency argument LLM call failed: %s — using fallback", e)
        warnings.append(f"LLM call failed: {e} — using deterministic fallback arguments")
        arguments = _fallback_arguments(candidates)

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
