"""Tests for the Charge Processing Agent."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.agents.tier0.orchestrator import OrchestratorAgent
from src.agents.tier1.charge_processing import ChargeProcessingAgent
from src.models.charges import ChargeProcessingInput, ChargeProcessingOutput
from src.routes import _store, upload
from src.services import measurements
from src.services.model_gateway import AuthError, SchemaMismatchError
from src.services.model_gateway.testing import FakeCallModel


def test_charge_processing_input_model():
    """Test that ChargeProcessingInput validates correctly."""
    input_data = ChargeProcessingInput(
        document_text="Sample complaint text",
        document_type="COMPLAINT",
        jurisdiction="IL",
    )
    assert input_data.document_type == "COMPLAINT"
    assert input_data.jurisdiction == "IL"


def test_charge_processing_output_model():
    """Test that ChargeProcessingOutput serializes correctly."""
    output = ChargeProcessingOutput(
        charges=[],
        factual_allegations=[],
        enhancements=[],
        persons_of_interest=[],
        procedural_flags=[],
        raw_document_summary="Test summary",
    )
    data = output.model_dump()
    assert data["raw_document_summary"] == "Test summary"
    assert isinstance(data["charges"], list)


# ---------------------------------------------------------------------------
# Agent behavior through the gateway (PHASE_1_MODEL_GATEWAY.md §3, §10)
# ---------------------------------------------------------------------------


ACCUSATION = (Path(__file__).parent / "fixtures" / "sample_accusation.txt").read_text()
_CP = "src.agents.tier1.charge_processing.call_model"

_DEFENDANT = {
    "name": "MARCUS JEROME WILLIAMS",
    "aliases": [],
    "date_of_birth": "08/22/1995",
    "address": "456 Auburn Ave NE, Apt 3B, Atlanta, GA 30312",
    "prior_record_mentioned": False,
    "prior_record_details": None,
    "custody_status": "unknown",
    "confidence": 0.95,
    "source_reference": "p. 1",
}


def _charge(count: int, code: str, description: str, confidence: float) -> dict:
    return {
        "count_number": count,
        "charge_description": description,
        "statute": {"code": code, "title": description, "full_text_reference": code},
        "degree": "misdemeanor",
        "classification": "Misdemeanor",
        "elements": [
            {
                "element": "knowing conduct",
                "factual_support_in_charging_document": "alleged in count",
                "confidence": 0.9,
            }
        ],
        "penalty_range": {
            "minimum": "none",
            "maximum": "12 months",
            "mandatory_minimum": None,
            "notes": "",
        },
        "enhancements": [],
        "lesser_included_offenses": [],
        "date_of_alleged_offense": "2024-02-03",
        "location_of_alleged_offense": "Atlanta, Fulton County",
        "confidence": confidence,
        "source_reference": "p. 1",
    }


EXTRACTION = {
    "defendant": _DEFENDANT,
    "charges": [
        _charge(1, "O.C.G.A. § 16-13-30(a)", "Possession of marijuana under one ounce", 0.95),
        _charge(2, "O.C.G.A. § 16-10-24(a)", "Misdemeanor obstruction", 0.4),
    ],
    "factual_allegations": [],
    "persons_of_interest": [
        {
            "person_id": "PER-001",
            "name": "Derek Thompson",
            "role": "officer",
            "badge_number": "5892",
            "agency": "APD Zone 5",
            "involvement_summary": "Conducted the stop",
            "documents_appearing_in": ["doc_1"],
            "potential_impeachment_notes": None,
            "confidence": 0.9,
        }
    ],
    "evidence_items": [],
    "misconduct_flags": [],
    "procedural_flags": [],
}

ELIGIBILITY = {"potentially_eligible": True, "basis": "no priors stated", "confidence": 0.6}
CROSS = {
    "jurisdiction": {"level": "state", "court": "State Court of Fulton County", "confidence": 0.9},
    "inconsistencies": [],
    "additional_misconduct_flags": [],
    "diversion_eligibility": {
        "first_offender_act_eligible": {**ELIGIBILITY, "disqualifying_factors": []},
        "pretrial_diversion_eligible": {**ELIGIBILITY, "notes": ""},
        "drug_court_eligible": ELIGIBILITY,
        "federal_pretrial_diversion": {**ELIGIBILITY, "potentially_eligible": False},
    },
    "consolidated_defendant": _DEFENDANT,
}


def _input(document_type: str = "accusation") -> dict:
    return {
        "document_text": ACCUSATION,
        "document_type": document_type,
        "jurisdiction": "GA",
        "matter_id": "SYN-CP-001",
    }


async def test_charge_processing_golden_output() -> None:
    fake = FakeCallModel(EXTRACTION, CROSS)
    with patch(_CP, new=fake):
        result = await ChargeProcessingAgent().run(_input())

    assert fake.prompt_ids == ["charge_processing.extract", "charge_processing.cross_document"]
    assert {r.prompt_version for r in fake.requests} == {
        "system.v1+extract.v1",
        "system.v1+cross_document.v1",
    }
    assert ACCUSATION in fake.requests[0].prompt  # retrieve first: the source text is passed

    data = result["data"]
    assert result["source"] == "charge_processing"
    assert [c["statute"]["code"] for c in data["charges"]] == [
        "O.C.G.A. § 16-13-30(a)",
        "O.C.G.A. § 16-10-24(a)",
    ]
    assert data["jurisdiction"]["court"] == "State Court of Fulton County"
    assert data["defendant"]["name"] == "MARCUS JEROME WILLIAMS"
    # Confidence triage: the 0.4 charge is flagged, nothing else is.
    assert data["charges"][1]["review_required"] is True
    assert "review_required" not in data["charges"][0]
    assert data["processing_metadata"]["review_required_count"] == 1


async def test_unknown_document_type_is_classified() -> None:
    classification = {"document_type": "accusation", "confidence": 0.97, "rationale": "caption"}
    fake = FakeCallModel(classification, EXTRACTION, CROSS)
    with patch(_CP, new=fake):
        result = await ChargeProcessingAgent().run(_input(document_type="UNKNOWN"))
    assert fake.prompt_ids[0] == "charge_processing.classify"
    assert result["data"]["documents_processed"][0]["document_type"] == "accusation"


async def test_auth_error_propagates() -> None:
    """The exact bug from §3: a 401 used to merge as a zero-charge success."""
    with patch(_CP, new=FakeCallModel(AuthError("The API rejected the key (401)"))):
        with pytest.raises(AuthError):
            await ChargeProcessingAgent().run(_input())

    # Through the upload pipeline: recorded as FAILED with its type, nothing merged.
    orchestrator = OrchestratorAgent()
    await orchestrator.run({"case_id": "SYN-CP-AUTH"})
    _store.case_store["SYN-CP-AUTH"] = orchestrator
    try:
        with patch(_CP, new=FakeCallModel(AuthError("The API rejected the key (401)"))):
            await upload._run_pipeline("SYN-CP-AUTH", ACCUSATION, "accusation", "GA")
    finally:
        del _store.case_store["SYN-CP-AUTH"]

    assert orchestrator.case_state.charge_processing is None, "no zero-charge success merged"
    assert orchestrator.get_status().blocked is True
    (failure,) = measurements.events(measurements.MeasurementKind.AGENT_FAILURE)
    assert failure.agent_id == "charge_processing"
    assert failure.payload["error_type"] == "AuthError"
    assert not measurements.events(measurements.MeasurementKind.MERGE_DECISION)


async def test_malformed_extraction_fails_loudly() -> None:
    broken = {**EXTRACTION, "charges": [{"count_number": "one"}]}
    with patch(_CP, new=FakeCallModel(broken)):
        with pytest.raises(SchemaMismatchError):
            await ChargeProcessingAgent().run(_input())
