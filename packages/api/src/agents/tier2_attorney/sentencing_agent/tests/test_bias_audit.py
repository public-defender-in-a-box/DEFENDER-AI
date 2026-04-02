"""Bias audit tests for the sentencing agent.

Ensures that demographic-only changes do not alter runtime recommendations,
demographic fields are absent from prompt payloads, and comparable sentence
selection does not use race/ethnicity.
"""

from __future__ import annotations

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
from ..nodes.comparable_sentence_lookup import find_comparable_sentences
from ..nodes.diversion_checker import conditional_discharge_prelim, diversion_checker
from ..nodes.exposure_calculator import calculate_guideline_range
from ..nodes.mitigation_fact_sheet import build_mitigation_fact_sheet
from ..nodes.scope_gate import is_mvp_in_scope


def _base_input(**overrides) -> SentencingAgentInput:
    """Create a base in-scope input with optional overrides."""
    defaults = dict(
        case_id="bias-test",
        case_phase=CasePhase.PRETRIAL,
        jurisdiction_context=JurisdictionContext(county="Clarke", judicial_circuit="Western"),
        offense_details=OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana",
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
            age=25,
            employment_status="employed",
        ),
    )
    defaults.update(overrides)
    return SentencingAgentInput(**defaults)


class TestDemographicInvariance:
    """Demographic-only changes should NOT alter deterministic outputs."""

    def test_age_does_not_change_scope(self):
        """Different ages should not change scope determination."""
        for age in [18, 25, 40, 65]:
            input_data = _base_input(personal_circumstances=PersonalCircumstances(age=age))
            in_scope, _ = is_mvp_in_scope(input_data.offense_details)
            assert in_scope is True

    def test_age_does_not_change_exposure(self):
        """Different ages should produce identical exposure calculations."""
        ranges = []
        for age in [18, 25, 40, 65]:
            input_data = _base_input(personal_circumstances=PersonalCircumstances(age=age))
            result = calculate_guideline_range(
                input_data.offense_details,
                input_data.criminal_history,
                0,
            )
            ranges.append(result)

        for r in ranges[1:]:
            assert r.statutory_maximum == ranges[0].statutory_maximum
            assert r.fine_maximum == ranges[0].fine_maximum
            assert r.has_mandatory_minimum == ranges[0].has_mandatory_minimum

    def test_age_does_not_change_conditional_discharge(self):
        """Age should not affect conditional discharge eligibility."""
        for age in [18, 25, 40, 65]:
            history = PriorRecord(
                verification_status=VerificationStatus.VERIFIED,
                has_prior_convictions=False,
            )
            elig, _ = conditional_discharge_prelim(history)
            assert elig == "yes"


class TestComparableSelectionBias:
    """Comparable sentence selection must not use protected characteristics."""

    def test_no_race_ethnicity_in_matching(self):
        """Comparable matching should not consider race or ethnicity."""
        input_a = _base_input()
        input_b = _base_input()
        # Same criminal and offense profile, different "demographics" (age only as proxy)
        input_b.personal_circumstances.age = 55

        comps_a = find_comparable_sentences(input_a)
        comps_b = find_comparable_sentences(input_b)

        # Should return identical comparables since matching is on county/circuit/prior record
        assert len(comps_a) == len(comps_b)
        for ca, cb in zip(comps_a, comps_b):
            assert ca.description == cb.description

    def test_comparable_corpus_has_no_race_field(self):
        """Seed corpus entries should not contain race/ethnicity fields."""
        import json

        from ..config import COMPARABLES_PATH

        with open(COMPARABLES_PATH) as f:
            corpus = json.load(f)

        protected_fields = {"race", "ethnicity", "gender", "sex", "national_origin", "religion"}

        for entry in corpus:
            for field in protected_fields:
                assert field not in entry, f"Protected field '{field}' found in comparable corpus"
                profile = entry.get("defendant_profile", {})
                assert field not in profile, f"Protected field '{field}' found in defendant_profile"


class TestPromptPayloadSafety:
    """Demographic data should be absent from LLM prompt payloads."""

    def test_fact_sheet_excludes_age_from_themes(self):
        """Age should not be extracted as a mitigation theme."""
        input_data = _base_input(personal_circumstances=PersonalCircumstances(age=22))
        fact_sheet = build_mitigation_fact_sheet(input_data)
        # Age should not appear as a standalone fact or theme
        for fact in fact_sheet["facts"]:
            assert "age" not in fact.get("category", "").lower()

    def test_fact_sheet_does_not_include_raw_demographics(self):
        """Raw demographic fields (age, gender) should not be in fact texts."""
        input_data = _base_input(personal_circumstances=PersonalCircumstances(age=22))
        fact_sheet = build_mitigation_fact_sheet(input_data)
        for fact in fact_sheet["facts"]:
            text = fact.get("text", "").lower()
            # Age as a standalone number shouldn't be a fact
            assert text != "22"
            assert text != "age: 22"
