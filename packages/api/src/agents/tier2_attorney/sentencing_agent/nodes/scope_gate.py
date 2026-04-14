"""Node 0: Scope Gate — Determines if a case is within MVP scope.

MVP scope: simple possession of marijuana, one ounce or less, Georgia state court,
no enhancements. Deterministic — no LLM calls.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models.inputs import ConductType, OffenseDetails, SentencingAgentInput
from ..models.outputs import NodeAuditRecord
from ..models.state import SentencingGraphState


def quantity_in_ounces(value: float, unit: str) -> float:
    """Convert a quantity to ounces."""
    if unit == "ounces":
        return value
    if unit == "grams":
        return value / 28.3495
    raise ValueError(f"Unknown quantity unit: {unit}")


def is_mvp_in_scope(offense: OffenseDetails) -> tuple[bool, str | None]:
    """Check whether the offense falls within MVP scope.

    Returns (in_scope, reason_if_not).
    """
    if offense.substance_name is None or offense.substance_name.lower() != "marijuana":
        return False, "MVP handles marijuana simple-possession cases only"

    if offense.conduct_type not in (ConductType.SIMPLE_POSSESSION, ConductType.UNKNOWN):
        return False, "MVP excludes sale/distribution/manufacture/PWID cases"

    if offense.conduct_type == ConductType.UNKNOWN:
        # If unknown but described as simple possession, allow with warning
        desc_lower = offense.charge_description.lower()
        if not any(
            term in desc_lower
            for term in ["simple possession", "possession of marijuana", "possession of less than"]
        ):
            return (
                False,
                "Conduct type unknown and charge description does not indicate simple possession",
            )

    if offense.quantity_value is None:
        return False, "Quantity missing; cannot confirm misdemeanor threshold"

    try:
        qty_oz = quantity_in_ounces(offense.quantity_value, offense.quantity_unit.value)
    except ValueError:
        return False, "Unknown quantity unit; cannot confirm misdemeanor threshold"

    if qty_oz > 1.0:
        return False, "Quantity exceeds misdemeanor threshold (one ounce)"

    if offense.enhancements:
        return False, "Enhancement flags indicate non-MVP offense posture"

    return True, None


def scope_gate(state: SentencingGraphState) -> SentencingGraphState:
    """Scope gate node — validates that the case is within MVP scope."""
    started_at = datetime.now(timezone.utc).isoformat()
    input_data: SentencingAgentInput = state["input"]
    warnings: list[str] = list(state.get("warnings") or [])
    flags: list[str] = list(state.get("flags") or [])
    ethics_flags: list[str] = list(state.get("ethics_flags") or [])

    # Validate jurisdiction
    if input_data.jurisdiction_context.state != "georgia":
        state["scope_status"] = "out_of_scope"
        state["out_of_scope_reason"] = "MVP supports Georgia state court cases only"
        state["warnings"] = warnings
        state["flags"] = flags
        state["ethics_flags"] = ethics_flags
        state["audit_records"] = [
            NodeAuditRecord(
                node_name="scope_gate",
                status="ok",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                warnings=["Out of scope: non-Georgia jurisdiction"],
                output_keys=["scope_status", "out_of_scope_reason"],
            )
        ]
        return state

    if not input_data.jurisdiction_context.county:
        state["scope_status"] = "insufficient_data"
        state["out_of_scope_reason"] = "County is required for diversion and comparable analysis"
        state["warnings"] = warnings + ["Missing county information"]
        state["flags"] = flags
        state["ethics_flags"] = ethics_flags
        state["audit_records"] = [
            NodeAuditRecord(
                node_name="scope_gate",
                status="warning",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                warnings=["Missing county"],
                output_keys=["scope_status", "out_of_scope_reason"],
            )
        ]
        return state

    # Check offense scope
    in_scope, reason = is_mvp_in_scope(input_data.offense_details)

    if not in_scope:
        state["scope_status"] = "out_of_scope"
        state["out_of_scope_reason"] = reason
        state["warnings"] = warnings
        state["flags"] = flags
        state["ethics_flags"] = ethics_flags
        state["audit_records"] = [
            NodeAuditRecord(
                node_name="scope_gate",
                status="ok",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                warnings=[f"Out of scope: {reason}"],
                output_keys=["scope_status", "out_of_scope_reason"],
            )
        ]
        return state

    # Check criminal history verification
    if input_data.criminal_history.verification_status.value == "self_reported":
        warnings.append("Criminal history is self-reported only — confidence will be capped")
        ethics_flags.append(
            "SELF_REPORTED_CRIMINAL_HISTORY: verification recommended before relying on diversion eligibility"
        )

    if input_data.criminal_history.verification_status.value == "unknown":
        warnings.append("Criminal history verification status unknown — treat as unverified")

    # Conduct type warning
    if input_data.offense_details.conduct_type == ConductType.UNKNOWN:
        warnings.append(
            "Conduct type is UNKNOWN — inferred as simple possession from charge description"
        )

    state["scope_status"] = "in_scope"
    state["out_of_scope_reason"] = None
    state["warnings"] = warnings
    state["flags"] = flags
    state["ethics_flags"] = ethics_flags
    state["audit_records"] = [
        NodeAuditRecord(
            node_name="scope_gate",
            status="ok",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            warnings=warnings,
            output_keys=["scope_status"],
        )
    ]
    return state
