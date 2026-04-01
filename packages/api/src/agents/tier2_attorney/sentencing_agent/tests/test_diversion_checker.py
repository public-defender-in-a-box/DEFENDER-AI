"""Tests for the diversion checker node."""

from __future__ import annotations

import pytest

from ..models.inputs import PriorRecord, VerificationStatus
from ..nodes.diversion_checker import conditional_discharge_prelim, diversion_checker


class TestConditionalDischargePrelim:
    def test_no_priors_eligible(self):
        history = PriorRecord(
            verification_status=VerificationStatus.VERIFIED,
            has_prior_convictions=False,
            prior_drug_offenses=0,
            prior_conditional_discharge_used=False,
            prior_out_of_state_or_federal_drug_convictions=0,
        )
        eligibility, reasons = conditional_discharge_prelim(history)
        assert eligibility == "yes"
        assert any("no verified prior" in r.lower() for r in reasons)

    def test_prior_drug_conviction_ineligible(self):
        history = PriorRecord(
            verification_status=VerificationStatus.VERIFIED,
            has_prior_convictions=True,
            prior_drug_offenses=1,
        )
        eligibility, reasons = conditional_discharge_prelim(history)
        assert eligibility == "no"
        assert any("prior" in r.lower() and "drug" in r.lower() for r in reasons)

    def test_prior_conditional_discharge_ineligible(self):
        history = PriorRecord(
            verification_status=VerificationStatus.VERIFIED,
            has_prior_convictions=False,
            prior_conditional_discharge_used=True,
        )
        eligibility, reasons = conditional_discharge_prelim(history)
        assert eligibility == "no"
        assert any("previously used" in r.lower() for r in reasons)

    def test_out_of_state_drug_conviction_ineligible(self):
        history = PriorRecord(
            verification_status=VerificationStatus.VERIFIED,
            has_prior_convictions=True,
            prior_out_of_state_or_federal_drug_convictions=1,
        )
        eligibility, reasons = conditional_discharge_prelim(history)
        assert eligibility == "no"

    def test_self_reported_unknown(self):
        history = PriorRecord(
            verification_status=VerificationStatus.SELF_REPORTED,
            has_prior_convictions=False,
        )
        eligibility, reasons = conditional_discharge_prelim(history)
        assert eligibility == "unknown"
        assert any("not fully verified" in r.lower() for r in reasons)

    def test_unverified_unknown(self):
        history = PriorRecord(
            verification_status=VerificationStatus.UNKNOWN,
            has_prior_convictions=False,
        )
        eligibility, reasons = conditional_discharge_prelim(history)
        assert eligibility == "unknown"


class TestDiversionCheckerNode:
    def _make_state(self, input_data, scope="in_scope"):
        return {
            "input": input_data,
            "scope_status": scope,
            "warnings": [],
            "attorney_decision_points": [],
            "audit_records": [],
        }

    def test_in_scope_produces_options(self, in_scope_input):
        state = self._make_state(in_scope_input)
        result = diversion_checker(state)
        options = result["diversion_options"]
        assert len(options) >= 3  # Conditional discharge + PTD + drug court

        # Conditional discharge should always be present
        cd = next((o for o in options if "Conditional" in o.program_name), None)
        assert cd is not None
        assert cd.availability_status == "confirmed_available"

    def test_conditional_discharge_eligibility(self, in_scope_input):
        state = self._make_state(in_scope_input)
        result = diversion_checker(state)
        cd = next(o for o in result["diversion_options"] if "Conditional" in o.program_name)
        # First-time offender with verified history
        assert cd.preliminary_eligibility == "yes"

    def test_prior_drug_conviction_ineligible_cd(self, prior_drug_conviction_input):
        state = self._make_state(prior_drug_conviction_input)
        result = diversion_checker(state)
        cd = next(o for o in result["diversion_options"] if "Conditional" in o.program_name)
        assert cd.preliminary_eligibility == "no"

    def test_availability_vs_eligibility_not_conflated(self, in_scope_input):
        """Drug court availability should not be conflated with eligibility."""
        state = self._make_state(in_scope_input)
        result = diversion_checker(state)
        dc = next(o for o in result["diversion_options"] if "Drug Court" in o.program_name)
        # These should be independent fields
        assert dc.availability_status is not None
        assert dc.preliminary_eligibility is not None
        # They should not necessarily be the same value
        assert hasattr(dc, "availability_status")
        assert hasattr(dc, "preliminary_eligibility")

    def test_veteran_gets_veterans_court(self, veteran_input):
        state = self._make_state(veteran_input)
        result = diversion_checker(state)
        vc = next((o for o in result["diversion_options"] if "Veterans" in o.program_name), None)
        assert vc is not None
        assert "15-1-17" in vc.statutory_basis

    def test_non_veteran_no_veterans_court(self, in_scope_input):
        state = self._make_state(in_scope_input)
        result = diversion_checker(state)
        vc = next((o for o in result["diversion_options"] if "Veterans" in o.program_name), None)
        assert vc is None

    def test_out_of_scope_skips(self, out_of_scope_controlled_substance_input):
        state = self._make_state(out_of_scope_controlled_substance_input, scope="out_of_scope")
        result = diversion_checker(state)
        assert result.get("diversion_options") is None or result.get("diversion_options") == []

    def test_attorney_decision_points_generated(self, in_scope_input):
        state = self._make_state(in_scope_input)
        result = diversion_checker(state)
        assert len(result["attorney_decision_points"]) > 0
