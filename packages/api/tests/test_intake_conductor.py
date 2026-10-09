"""Intake Conductor and intake route through the gateway (PHASE_1_MODEL_GATEWAY.md §9.3)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.agents.tier1.intake_conductor import INTERVIEW_PHASES, IntakeConductorAgent
from src.routes import intake as intake_route
from src.services import measurements
from src.services.model_gateway import SchemaMismatchError, TransportError
from src.services.model_gateway.testing import FakeCallModel

_IC = "src.agents.tier1.intake_conductor.call_model"
_ROUTE = "src.routes.intake.call_model"

QUESTIONS = {
    "phase": "incident_narrative",
    "questions": [
        {
            "question_id": "Q-IN-001",
            "question_text": "In your own words, what happened that night?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Client's account first",
            "follow_up_triggers": [],
            "related_charges": [1],
            "feeds_subagent": "fact_gatherer",
            "options": [],
        }
    ],
    "phase_instructions": "Let the client narrate.",
    "ethical_notes": "Offer breaks.",
}

PROCESSED = {
    "question_id": "Q-IN-001",
    "phase": "incident_narrative",
    "extracted_facts": [
        {
            "fact_id": "IF-IN-001",
            "category": "incident",
            "summary": "Client says he was parked, not driving",
            "detail": "I was just sitting in my car",
            "confidence": 0.8,
            "source": "client_statement",
            "client_certainty": "certain",
            "related_charges": [1],
            "feeds_subagent": "rights_violation_scanner",
        },
        {
            "fact_id": "IF-IN-002",
            "category": "incident",
            "summary": "Unsure of the time",
            "detail": "maybe around eleven",
            "confidence": 0.3,
            "source": "client_statement",
            "client_certainty": "uncertain",
            "related_charges": [],
            "feeds_subagent": "fact_gatherer",
        },
    ],
    "inconsistencies_with_charges": [],
    "ethical_flags": [],
    "follow_up_questions": [],
    "subagent_triggers": [
        {
            "target_agent": "rights_violation_scanner",
            "trigger_reason": "Stop circumstances disputed",
            "context_to_pass": "Parked, not driving",
            "priority": "high",
        }
    ],
}

ANALYSIS = {
    "inconsistencies": [],
    "corroborations": [],
    "gaps": [],
    "new_defense_angles": [
        {
            "description": "No traffic violation if the car was parked",
            "basis": "Client says he was parked",
            "type": "constitutional_violation",
            "confidence": 0.6,
        }
    ],
}

CHARGE_DATA = {"defendant": {"name": "SYNTHETIC CLIENT"}, "charges": []}


def _input() -> dict:
    responses = {phase: [] for phase in INTERVIEW_PHASES}
    responses["incident_narrative"] = [
        {
            "question_id": "Q-IN-001",
            "question_text": "In your own words, what happened that night?",
            "client_response": "I was just sitting in my car, maybe around eleven.",
        }
    ]
    return {"charge_data": CHARGE_DATA, "matter_id": "SYN-IC-001", "responses": responses}


async def test_intake_golden_output() -> None:
    fake = FakeCallModel(
        by_prompt={
            "intake_conductor.question_generation": QUESTIONS,
            "intake_conductor.response_processing": PROCESSED,
            "intake_conductor.inconsistency_analysis": ANALYSIS,
        }
    )
    with patch(_IC, new=fake):
        result = await IntakeConductorAgent().run(_input())

    data = result["data"]
    assert result["source"] == "intake_conductor"
    assert [f["fact_id"] for f in data["extracted_facts"]] == ["IF-IN-001", "IF-IN-002"]
    assert data["extracted_facts"][1]["review_required"] is True
    assert "review_required" not in data["extracted_facts"][0]
    assert data["subagent_triggers"][0]["target_agent"] == "rights_violation_scanner"
    assert data["new_defense_angles"][0]["type"] == "constitutional_violation"
    assert data["processing_metadata"]["phases_completed"] == INTERVIEW_PHASES
    assert fake.prompt_ids.count("intake_conductor.question_generation") == 5
    assert fake.prompt_ids.count("intake_conductor.response_processing") == 1


async def test_question_generation_failure_raises() -> None:
    """No default-question fallback on a failed call (§3)."""
    with patch(_IC, new=FakeCallModel(TransportError("connection reset"))):
        with pytest.raises(TransportError):
            await IntakeConductorAgent().run(_input())


async def test_malformed_processing_fails_loudly() -> None:
    broken = {**PROCESSED, "extracted_facts": [{"fact_id": "IF-IN-001"}]}
    fake = FakeCallModel(
        by_prompt={
            "intake_conductor.question_generation": QUESTIONS,
            "intake_conductor.response_processing": broken,
        }
    )
    with patch(_IC, new=fake), pytest.raises(SchemaMismatchError):
        await IntakeConductorAgent().run(_input())


async def test_turn_message_passes_through() -> None:
    fake = FakeCallModel({"combined_message": "Thanks for sharing. Where were you headed?"})
    with patch(_ROUTE, new=fake):
        msg = await intake_route._generate_turn_message("home", "q", "Where were you headed?")
    assert msg == "Thanks for sharing. Where were you headed?"
    assert fake.requests[0].prompt_id == "intake_route.turn_message"


async def test_turn_message_extra_question_is_replaced() -> None:
    fake = FakeCallModel({"combined_message": "Okay? Where were you headed? Why?"})
    with patch(_ROUTE, new=fake):
        msg = await intake_route._generate_turn_message("home", "q", "Where were you headed?")
    assert msg == "Thank you. Where were you headed?"


async def test_turn_message_failure_is_recorded() -> None:
    """The one retained fallback: fixed text, and the failed call is still measured."""
    msg = await intake_route._generate_turn_message("home", "q", "Where were you headed?")
    assert msg == "Thank you. Where were you headed?"
    (event,) = measurements.events(measurements.MeasurementKind.MODEL_CALL)
    assert event.agent_id == "intake_route"
    assert event.payload["outcome"] == "CassetteMissError"
