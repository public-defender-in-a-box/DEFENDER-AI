"""Shared fixtures for sentencing agent tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..models.inputs import (
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

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> dict:
    with open(FIXTURES_DIR / name) as f:
        return json.load(f)


@pytest.fixture
def in_scope_input() -> SentencingAgentInput:
    """Valid in-scope marijuana simple possession case."""
    return SentencingAgentInput(**_load_fixture("in_scope_case.json"))


@pytest.fixture
def out_of_scope_controlled_substance_input() -> SentencingAgentInput:
    """Out-of-scope controlled substance case (cocaine)."""
    return SentencingAgentInput(**_load_fixture("out_of_scope_controlled_substance.json"))


@pytest.fixture
def missing_quantity_input() -> SentencingAgentInput:
    """Missing quantity case."""
    return SentencingAgentInput(**_load_fixture("missing_quantity_case.json"))


@pytest.fixture
def over_one_ounce_input() -> SentencingAgentInput:
    """Marijuana quantity exceeding one ounce — out of scope."""
    return SentencingAgentInput(
        case_id="test-over-oz",
        case_phase=CasePhase.PRETRIAL,
        jurisdiction_context=JurisdictionContext(county="Clarke", judicial_circuit="Western"),
        offense_details=OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(2)",
            charge_description="Possession of marijuana, more than one ounce",
            conduct_type=ConductType.SIMPLE_POSSESSION,
            substance_name="marijuana",
            quantity_value=2.0,
            quantity_unit=QuantityUnit.OUNCES,
        ),
        criminal_history=PriorRecord(has_prior_convictions=False),
        personal_circumstances=PersonalCircumstances(),
    )


@pytest.fixture
def pwid_input() -> SentencingAgentInput:
    """Possession with intent to distribute — out of scope."""
    return SentencingAgentInput(
        case_id="test-pwid",
        case_phase=CasePhase.PRETRIAL,
        jurisdiction_context=JurisdictionContext(county="Fulton"),
        offense_details=OffenseDetails(
            statute="O.C.G.A. § 16-13-30",
            charge_description="Possession of marijuana with intent to distribute",
            conduct_type=ConductType.PWID,
            substance_name="marijuana",
            quantity_value=0.5,
            quantity_unit=QuantityUnit.OUNCES,
        ),
        criminal_history=PriorRecord(has_prior_convictions=False),
        personal_circumstances=PersonalCircumstances(),
    )


@pytest.fixture
def enhancement_input() -> SentencingAgentInput:
    """Case with school-zone enhancement — out of scope."""
    return SentencingAgentInput(
        case_id="test-enhance",
        case_phase=CasePhase.PRETRIAL,
        jurisdiction_context=JurisdictionContext(county="Clarke"),
        offense_details=OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana in school zone",
            conduct_type=ConductType.SIMPLE_POSSESSION,
            substance_name="marijuana",
            quantity_value=0.3,
            quantity_unit=QuantityUnit.OUNCES,
            enhancements=["school_zone"],
        ),
        criminal_history=PriorRecord(has_prior_convictions=False),
        personal_circumstances=PersonalCircumstances(),
    )


@pytest.fixture
def prior_drug_conviction_input() -> SentencingAgentInput:
    """Case with prior drug conviction — conditional discharge ineligible."""
    return SentencingAgentInput(
        case_id="test-prior-drug",
        case_phase=CasePhase.PRETRIAL,
        jurisdiction_context=JurisdictionContext(county="Fulton", judicial_circuit="Atlanta"),
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
            has_prior_convictions=True,
            prior_drug_offenses=1,
            prior_misdemeanors=1,
        ),
        personal_circumstances=PersonalCircumstances(
            employment_status="employed",
            housing_stable=True,
        ),
    )


@pytest.fixture
def self_reported_history_input() -> SentencingAgentInput:
    """Case with self-reported criminal history."""
    return SentencingAgentInput(
        case_id="test-self-report",
        case_phase=CasePhase.PRETRIAL,
        jurisdiction_context=JurisdictionContext(county="Clarke", judicial_circuit="Western"),
        offense_details=OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana",
            conduct_type=ConductType.SIMPLE_POSSESSION,
            substance_name="marijuana",
            quantity_value=0.4,
            quantity_unit=QuantityUnit.OUNCES,
        ),
        criminal_history=PriorRecord(
            verification_status=VerificationStatus.SELF_REPORTED,
            has_prior_convictions=False,
        ),
        personal_circumstances=PersonalCircumstances(),
    )


@pytest.fixture
def veteran_input() -> SentencingAgentInput:
    """Case with military veteran."""
    return SentencingAgentInput(
        case_id="test-veteran",
        case_phase=CasePhase.PRETRIAL,
        jurisdiction_context=JurisdictionContext(county="Clarke", judicial_circuit="Western"),
        offense_details=OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana, less than one ounce",
            conduct_type=ConductType.SIMPLE_POSSESSION,
            substance_name="marijuana",
            quantity_value=0.3,
            quantity_unit=QuantityUnit.OUNCES,
        ),
        criminal_history=PriorRecord(
            verification_status=VerificationStatus.VERIFIED,
            has_prior_convictions=False,
        ),
        personal_circumstances=PersonalCircumstances(
            military_service=True,
            military_details="US Army, honorably discharged",
        ),
    )


@pytest.fixture
def grams_input() -> SentencingAgentInput:
    """Case with quantity in grams (should convert to ounces)."""
    return SentencingAgentInput(
        case_id="test-grams",
        case_phase=CasePhase.PRETRIAL,
        jurisdiction_context=JurisdictionContext(county="Chatham", judicial_circuit="Eastern"),
        offense_details=OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana",
            conduct_type=ConductType.SIMPLE_POSSESSION,
            substance_name="marijuana",
            quantity_value=10.0,
            quantity_unit=QuantityUnit.GRAMS,
        ),
        criminal_history=PriorRecord(
            verification_status=VerificationStatus.VERIFIED,
            has_prior_convictions=False,
        ),
        personal_circumstances=PersonalCircumstances(),
    )
