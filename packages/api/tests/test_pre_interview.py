"""Pre-Interview Research Conductor through the gateway (PHASE_1_MODEL_GATEWAY.md §9.5)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agents.tier1.pre_interview import PreInterviewResearchAgent
from src.services.model_gateway import RefusalError
from src.services.model_gateway.testing import FakeCallModel

_PI = "src.agents.tier1.pre_interview.call_model"

BRIEF = {
    "charges_summary": "One misdemeanor possession count and one obstruction count.",
    "targeted_questions": [
        {
            "question_id": "TQ-001",
            "question": "Did the officer say why he stopped you?",
            "relevant_charge_id": "charge_1",
            "relevant_element": "lawful discharge of duties",
            "priority": "MUST_ASK",
            "rationale": "Obstruction requires a lawful stop",
            "phase": "arrest_and_custody",
        }
    ],
    "preliminary_rights_flags": [
        {
            "flag_id": "RF-001",
            "type": "fourth_amendment",
            "description": "Stop justified only by a taillight",
            "basis": "Accusation narrative",
            "investigation_needed": "Was the taillight actually out?",
            "severity": "medium",
            "confidence": 0.6,
        }
    ],
    "known_facts_from_documents": [],
    "collateral_consequence_alerts": [],
    "legal_brief": {
        "key_legal_issues": ["Lawfulness of the stop"],
        "elements_to_prove": [],
        "potential_defenses": ["Unlawful detention"],
        "diversion_eligibility": {
            "first_offender_act": "Possibly eligible",
            "pretrial_diversion": "Unknown",
            "drug_court": "Not applicable",
            "notes": "",
        },
        "procedural_deadlines": [],
        "research_requests": [],
    },
}

CHARGES = {
    "data": {
        "charges": [{"count_number": 1, "elements": [{"element": "possession"}]}],
        "defendant": {"name": "SYNTHETIC CLIENT"},
    },
    "confidence": "HIGH",
}


async def test_pre_interview_golden_output() -> None:
    fake = FakeCallModel(BRIEF)
    with patch(_PI, new=fake):
        result = await PreInterviewResearchAgent().run({"charge_processing": CHARGES})

    data = result["data"]
    assert result["source"] == "pre_interview_research"
    assert data["targeted_questions"][0]["priority"] == "MUST_ASK"
    assert data["preliminary_rights_flags"][0]["type"] == "fourth_amendment"
    assert data["legal_brief"]["diversion_eligibility"]["first_offender_act"] == "Possibly eligible"
    assert fake.requests[0].prompt_version == "system.v1+brief.v1"
    assert '"SYNTHETIC CLIENT"' in fake.requests[0].prompt


async def test_failure_is_not_an_empty_brief() -> None:
    with patch(_PI, new=FakeCallModel(RefusalError("refused"))), pytest.raises(RefusalError):
        await PreInterviewResearchAgent().run({"charge_processing": CHARGES})
