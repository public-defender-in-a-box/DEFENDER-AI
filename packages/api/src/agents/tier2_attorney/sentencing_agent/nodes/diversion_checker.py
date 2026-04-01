"""Node 3: Diversion / Deferral Checker — Assesses program availability and eligibility.

Deterministic + local program config lookup. No LLM calls.
Separates availability (does the program exist locally?) from
eligibility (does this defendant qualify?).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..config import PROGRAM_DIRECTORY_PATH
from ..models.inputs import (
    PersonalCircumstances,
    PriorRecord,
    SentencingAgentInput,
    VerificationStatus,
)
from ..models.outputs import DiversionOption, NodeAuditRecord
from ..models.state import SentencingGraphState


def load_program_directory() -> list[dict[str, Any]]:
    """Load the Georgia program directory seed data."""
    with open(PROGRAM_DIRECTORY_PATH) as f:
        return json.load(f)


def conditional_discharge_prelim(history: PriorRecord) -> tuple[str, list[str]]:
    """Assess preliminary eligibility for conditional discharge under O.C.G.A. § 16-13-2(a)."""
    reasons: list[str] = []

    if history.prior_conditional_discharge_used:
        reasons.append("Previously used conditional discharge")
        return "no", reasons

    if history.prior_drug_offenses > 0:
        reasons.append("Prior Georgia drug conviction on record")
        return "no", reasons

    if history.prior_out_of_state_or_federal_drug_convictions > 0:
        reasons.append("Prior out-of-state or federal drug conviction requires attorney review")
        return "no", reasons

    if history.verification_status != VerificationStatus.VERIFIED:
        reasons.append("Criminal history not fully verified")
        return "unknown", reasons

    reasons.append("No verified prior drug conviction and no prior conditional discharge use")
    return "yes", reasons


def _find_local_programs(
    county: str,
    judicial_circuit: str | None,
    program_type: str,
    directory: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find matching programs in the directory by county/circuit and type."""
    matches = []
    for prog in directory:
        if prog["program_type"] != program_type:
            continue
        if prog["county"].lower() == county.lower():
            matches.append(prog)
        elif judicial_circuit and prog.get("judicial_circuit", "").lower() == judicial_circuit.lower():
            matches.append(prog)
    return matches


def check_pretrial_diversion(
    input_data: SentencingAgentInput,
    directory: list[dict[str, Any]],
) -> DiversionOption:
    """Check pretrial diversion availability and preliminary screening."""
    county = input_data.jurisdiction_context.county
    circuit = input_data.jurisdiction_context.judicial_circuit

    # Check override
    override_key = "pretrial_diversion"
    if override_key in input_data.program_availability_overrides:
        avail = (
            "confirmed_available"
            if input_data.program_availability_overrides[override_key]
            else "not_available_in_circuit"
        )
    else:
        local = _find_local_programs(county, circuit, "pretrial_diversion", directory)
        if local:
            best = local[0]
            avail = best.get("availability_status", "unknown")
        else:
            avail = "unknown"

    local = _find_local_programs(county, circuit, "pretrial_diversion", directory)
    best = local[0] if local else None

    return DiversionOption(
        program_name="Pretrial Diversion Program",
        statutory_basis="O.C.G.A. § 15-18-80 et seq.",
        availability_status=avail,
        preliminary_eligibility="unknown",  # Requires prosecutor agreement
        eligibility_factors=[
            "Requires prosecutor agreement for enrollment",
            "Availability varies by judicial circuit",
        ],
        outcome_if_completed=best["completion_outcome"] if best else "Charges dismissed by prosecutor upon successful completion",
        typical_duration=best.get("typical_duration_months") if best else "6-12 months",
        conditions=best.get("conditions", []) if best else ["Varies by program"],
        recommendation_notes="Pretrial diversion requires prosecutor cooperation. Defense counsel should initiate contact with the DA's office.",
        source_ref=best.get("source_note") if best else None,
    )


def check_drug_court(
    input_data: SentencingAgentInput,
    directory: list[dict[str, Any]],
) -> DiversionOption:
    """Check drug court availability and preliminary screening."""
    county = input_data.jurisdiction_context.county
    circuit = input_data.jurisdiction_context.judicial_circuit

    override_key = "drug_court"
    if override_key in input_data.program_availability_overrides:
        avail = (
            "confirmed_available"
            if input_data.program_availability_overrides[override_key]
            else "not_available_in_circuit"
        )
    else:
        local = _find_local_programs(county, circuit, "drug_court", directory)
        if local:
            best = local[0]
            avail = best.get("availability_status", "unknown")
        else:
            avail = "unknown"

    local = _find_local_programs(county, circuit, "drug_court", directory)
    best = local[0] if local else None

    eligibility = "unknown"
    factors = ["Accepts misdemeanor marijuana cases (verify locally)"]
    if best and best.get("accepts_misdemeanor_marijuana") is True:
        factors = ["Program confirmed to accept misdemeanor marijuana cases"]
    elif best and best.get("accepts_misdemeanor_marijuana") is False:
        eligibility = "no"
        factors = ["Program does not accept misdemeanor marijuana cases"]

    return DiversionOption(
        program_name="Drug Court",
        statutory_basis="O.C.G.A. § 15-1-15",
        availability_status=avail,
        preliminary_eligibility=eligibility,
        eligibility_factors=factors,
        outcome_if_completed=best["completion_outcome"] if best else "Varies — may include dismissal or charge reduction",
        typical_duration=best.get("typical_duration_months") if best else "12-18 months",
        conditions=best.get("conditions", []) if best else ["Varies by program"],
        recommendation_notes="Drug court participation is an intensive, judicially supervised treatment alternative.",
        source_ref=best.get("source_note") if best else None,
    )


def check_veterans_court(
    input_data: SentencingAgentInput,
    directory: list[dict[str, Any]],
) -> DiversionOption | None:
    """Check veterans court — only if military service is indicated."""
    personal = input_data.personal_circumstances
    if not personal.military_service:
        return None

    county = input_data.jurisdiction_context.county
    circuit = input_data.jurisdiction_context.judicial_circuit

    override_key = "veterans_court"
    if override_key in input_data.program_availability_overrides:
        avail = (
            "confirmed_available"
            if input_data.program_availability_overrides[override_key]
            else "not_available_in_circuit"
        )
    else:
        local = _find_local_programs(county, circuit, "veterans_court", directory)
        if local:
            best = local[0]
            avail = best.get("availability_status", "unknown")
        else:
            avail = "unknown"

    local = _find_local_programs(county, circuit, "veterans_court", directory)
    best = local[0] if local else None

    return DiversionOption(
        program_name="Veterans Treatment Court",
        statutory_basis="O.C.G.A. § 15-1-17",
        availability_status=avail,
        preliminary_eligibility="unknown",
        eligibility_factors=[
            "Military service indicated — veteran or active-duty status required",
            "Local program acceptance criteria must be verified",
        ],
        outcome_if_completed=best["completion_outcome"] if best else "Varies — may include dismissal, reduction, or sentence modification",
        typical_duration=best.get("typical_duration_months") if best else "12-24 months",
        conditions=best.get("conditions", []) if best else ["VA treatment engagement", "Regular court appearances"],
        recommendation_notes="Veterans court is appropriate for defendants with military service. Verify eligibility with the local program.",
        source_ref=best.get("source_note") if best else None,
    )


def diversion_checker(state: SentencingGraphState) -> SentencingGraphState:
    """Diversion checker node — assesses program availability and eligibility."""
    started_at = datetime.now(timezone.utc).isoformat()
    audit_records: list[NodeAuditRecord] = list(state.get("audit_records") or [])
    warnings: list[str] = list(state.get("warnings") or [])
    attorney_decision_points: list[str] = list(state.get("attorney_decision_points") or [])

    if state.get("scope_status") != "in_scope":
        audit_records.append(
            NodeAuditRecord(
                node_name="diversion_checker",
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
    options: list[DiversionOption] = []

    try:
        directory = load_program_directory()
    except Exception:
        directory = []
        warnings.append("Could not load program directory — diversion availability will be unknown")

    # 1. Conditional discharge (statewide, statutory)
    cd_elig, cd_reasons = conditional_discharge_prelim(input_data.criminal_history)
    options.append(
        DiversionOption(
            program_name="Conditional Discharge",
            statutory_basis="O.C.G.A. § 16-13-2(a)",
            availability_status="confirmed_available",  # Statewide statutory
            preliminary_eligibility=cd_elig,
            eligibility_factors=cd_reasons,
            outcome_if_completed=(
                "Court may dismiss charges without entering a judgment of guilt. "
                "Possible record restriction / sealing review under O.C.G.A. § 35-3-37."
            ),
            typical_duration="Up to 3 years probation (court discretion)",
            conditions=["Reasonable conditions set by court", "Drug testing typical"],
            recommendation_notes=(
                "Conditional discharge is one-time only and requires court discretion. "
                "Record relief is not automatic — requires separate sealing/restriction petition."
            ),
            source_ref="O.C.G.A. § 16-13-2(a)",
        )
    )

    if cd_elig == "yes":
        attorney_decision_points.append(
            "Client appears preliminarily eligible for conditional discharge — confirm with verified criminal history"
        )
    elif cd_elig == "unknown":
        attorney_decision_points.append(
            "Conditional discharge eligibility uncertain — criminal history verification needed"
        )

    # 2. Pretrial diversion
    ptd = check_pretrial_diversion(input_data, directory)
    options.append(ptd)
    if ptd.availability_status == "unknown":
        attorney_decision_points.append("Pretrial diversion availability unknown — verify with local DA's office")

    # 3. Drug court
    dc = check_drug_court(input_data, directory)
    options.append(dc)
    if dc.availability_status == "unknown":
        attorney_decision_points.append("Drug court availability unknown — verify with local court")

    # 4. Veterans court (only if military service)
    vc = check_veterans_court(input_data, directory)
    if vc is not None:
        options.append(vc)
        attorney_decision_points.append("Veteran status indicated — explore veterans court eligibility")

    state["diversion_options"] = options
    state["warnings"] = warnings
    state["attorney_decision_points"] = attorney_decision_points
    audit_records.append(
        NodeAuditRecord(
            node_name="diversion_checker",
            status="ok",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            warnings=warnings,
            output_keys=["diversion_options"],
        )
    )
    state["audit_records"] = audit_records
    return state
