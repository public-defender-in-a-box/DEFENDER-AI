"""Tests for the exposure calculator node."""

from __future__ import annotations

import pytest

from ..models.inputs import OffenseDetails, PriorRecord
from ..nodes.exposure_calculator import calculate_guideline_range, exposure_calculator


class TestCalculateGuidelineRange:
    def test_basic_range(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana",
        )
        history = PriorRecord(has_prior_convictions=False)
        result = calculate_guideline_range(offense, history, pretrial_custody_days=0)

        assert result.statutory_minimum == 0
        assert result.statutory_maximum == 365
        assert result.fine_minimum == 0.0
        assert result.fine_maximum == 1000.0
        assert result.has_mandatory_minimum is False
        assert result.probation_possible is True
        assert result.suspended_sentence_possible is True

    def test_weekend_service_threshold(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana",
        )
        history = PriorRecord(has_prior_convictions=False)
        result = calculate_guideline_range(offense, history, 0)

        assert result.weekend_service_possible is True
        assert result.weekend_service_threshold_days == 180

    def test_time_served_credit(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana",
        )
        history = PriorRecord(has_prior_convictions=False)
        result = calculate_guideline_range(offense, history, pretrial_custody_days=5)

        assert result.time_served_credit_days == 5

    def test_special_fee_note(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana",
        )
        history = PriorRecord(has_prior_convictions=False)
        result = calculate_guideline_range(offense, history, 0)

        assert len(result.special_fees) > 0
        fee = result.special_fees[0]
        assert fee["amount"] == 25.0
        assert "42-8-34" in fee["basis"]

    def test_data_basis_includes_key_statutes(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana",
        )
        history = PriorRecord(has_prior_convictions=False)
        result = calculate_guideline_range(offense, history, 0)

        assert "O.C.G.A. § 16-13-2(b)" in result.data_basis
        assert "O.C.G.A. § 17-10-3" in result.data_basis
        assert "O.C.G.A. § 42-8-34" in result.data_basis

    def test_weekend_service_note(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana",
        )
        history = PriorRecord(has_prior_convictions=False)
        result = calculate_guideline_range(offense, history, 0)

        assert any("weekend" in n.lower() for n in result.notes)


class TestExposureCalculatorNode:
    def _make_state(self, input_data, scope="in_scope"):
        return {
            "input": input_data,
            "scope_status": scope,
            "audit_records": [],
        }

    def test_in_scope_produces_range(self, in_scope_input):
        state = self._make_state(in_scope_input)
        result = exposure_calculator(state)
        assert result["guideline_range"] is not None
        assert result["guideline_range"].statutory_maximum == 365

    def test_out_of_scope_skips(self, out_of_scope_controlled_substance_input):
        state = self._make_state(out_of_scope_controlled_substance_input, scope="out_of_scope")
        result = exposure_calculator(state)
        assert result.get("guideline_range") is None
        assert result["audit_records"][-1].status == "skipped"
