#!/usr/bin/env python3
# ruff: noqa: E402
"""Smoke test — runs a quick deterministic-only check of the sentencing agent."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.agents.tier2_attorney.sentencing_agent.models.inputs import (
    CasePhase,
    ConductType,
    JurisdictionContext,
    OffenseDetails,
    PersonalCircumstances,
    PriorRecord,
    QuantityUnit,
    SentencingAgentInput,
    VerificationStatus,
)
from src.agents.tier2_attorney.sentencing_agent.nodes.scope_gate import scope_gate
from src.agents.tier2_attorney.sentencing_agent.nodes.authority_loader import (
    authority_loader,
)
from src.agents.tier2_attorney.sentencing_agent.nodes.exposure_calculator import (
    exposure_calculator,
)
from src.agents.tier2_attorney.sentencing_agent.nodes.diversion_checker import (
    diversion_checker,
)
from src.agents.tier2_attorney.sentencing_agent.nodes.mitigation_fact_sheet import (
    mitigation_fact_sheet_node,
)
from src.agents.tier2_attorney.sentencing_agent.nodes.comparable_sentence_lookup import (
    comparable_sentence_lookup,
)


def main():
    print("=== Sentencing Agent Smoke Test ===\n")

    # Build test input
    input_data = SentencingAgentInput(
        case_id="smoke-test-001",
        case_phase=CasePhase.PRETRIAL,
        jurisdiction_context=JurisdictionContext(county="Clarke", judicial_circuit="Western"),
        offense_details=OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana, less than one ounce",
            conduct_type=ConductType.SIMPLE_POSSESSION,
            substance_name="marijuana",
            quantity_value=0.5,
            quantity_unit=QuantityUnit.OUNCES,
        ),
        criminal_history=PriorRecord(
            verification_status=VerificationStatus.VERIFIED,
            has_prior_convictions=False,
        ),
        personal_circumstances=PersonalCircumstances(
            employment_status="employed",
            employment_details="Warehouse associate",
            housing_stable=True,
            community_ties="Active in local community center",
        ),
    )

    state = {
        "input": input_data,
        "scope_status": "insufficient_data",
        "out_of_scope_reason": None,
        "authority_bundle": {},
        "guideline_range": None,
        "diversion_options": [],
        "mitigation_fact_sheet": None,
        "departure_arguments": [],
        "mitigation_narrative": None,
        "comparable_sentences": [],
        "sentencing_memo": None,
        "flags": [],
        "warnings": [],
        "ethics_flags": [],
        "attorney_decision_points": [],
        "alternative_sentences": [],
        "audit_records": [],
    }

    # Run deterministic nodes
    print("1. Scope Gate...")
    state = scope_gate(state)
    print(f"   Status: {state['scope_status']}")
    assert state["scope_status"] == "in_scope", "Scope gate failed!"

    print("2. Authority Loader...")
    state = authority_loader(state)
    bundle = state["authority_bundle"]
    print(f"   Loaded {bundle['loaded_count']}/{bundle['expected_count']} statutes")

    print("3. Exposure Calculator...")
    state = exposure_calculator(state)
    gr = state["guideline_range"]
    print(f"   Range: {gr.statutory_minimum}-{gr.statutory_maximum} days, $0-${gr.fine_maximum}")

    print("4. Diversion Checker...")
    state = diversion_checker(state)
    print(f"   Options: {len(state['diversion_options'])}")
    for opt in state["diversion_options"]:
        print(
            f"   - {opt.program_name}: avail={opt.availability_status}, elig={opt.preliminary_eligibility}"
        )

    print("5. Mitigation Fact Sheet...")
    state = mitigation_fact_sheet_node(state)
    fs = state["mitigation_fact_sheet"]
    print(f"   Facts: {fs['fact_count']}, Themes: {fs['themes']}")

    print("6. Comparable Sentence Lookup...")
    state = comparable_sentence_lookup(state)
    print(f"   Comparables: {len(state['comparable_sentences'])}")

    print(f"\n   Warnings: {state['warnings']}")
    print(f"   Ethics flags: {state['ethics_flags']}")
    print(f"   Decision points: {state['attorney_decision_points']}")

    print("\n=== Smoke Test PASSED ===")


if __name__ == "__main__":
    main()
