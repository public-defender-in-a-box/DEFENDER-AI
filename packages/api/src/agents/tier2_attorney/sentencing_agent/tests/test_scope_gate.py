"""Tests for the scope gate node."""

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
)
from ..nodes.scope_gate import is_mvp_in_scope, quantity_in_ounces, scope_gate


class TestQuantityConversion:
    def test_ounces_passthrough(self):
        assert quantity_in_ounces(0.5, "ounces") == 0.5

    def test_grams_to_ounces(self):
        result = quantity_in_ounces(28.3495, "grams")
        assert abs(result - 1.0) < 0.001

    def test_unknown_unit_raises(self):
        with pytest.raises(ValueError):
            quantity_in_ounces(1.0, "kilograms")


class TestIsMvpInScope:
    def test_simple_possession_marijuana_in_scope(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana",
            conduct_type=ConductType.SIMPLE_POSSESSION,
            substance_name="marijuana",
            quantity_value=0.5,
            quantity_unit=QuantityUnit.OUNCES,
        )
        in_scope, reason = is_mvp_in_scope(offense)
        assert in_scope is True
        assert reason is None

    def test_grams_under_one_ounce_in_scope(self):
        """10 grams ≈ 0.35 oz — should be in scope."""
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana",
            conduct_type=ConductType.SIMPLE_POSSESSION,
            substance_name="marijuana",
            quantity_value=10.0,
            quantity_unit=QuantityUnit.GRAMS,
        )
        in_scope, reason = is_mvp_in_scope(offense)
        assert in_scope is True

    def test_rejects_non_marijuana(self):
        """Cocaine possession — out of scope."""
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30(a)",
            charge_description="Possession of cocaine",
            conduct_type=ConductType.SIMPLE_POSSESSION,
            substance_name="cocaine",
            quantity_value=2.0,
            quantity_unit=QuantityUnit.GRAMS,
        )
        in_scope, reason = is_mvp_in_scope(offense)
        assert in_scope is False
        assert "marijuana" in reason.lower()

    def test_rejects_over_one_ounce(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(2)",
            charge_description="Possession of marijuana, more than one ounce",
            conduct_type=ConductType.SIMPLE_POSSESSION,
            substance_name="marijuana",
            quantity_value=2.0,
            quantity_unit=QuantityUnit.OUNCES,
        )
        in_scope, reason = is_mvp_in_scope(offense)
        assert in_scope is False
        assert "threshold" in reason.lower()

    def test_rejects_pwid(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30",
            charge_description="PWID marijuana",
            conduct_type=ConductType.PWID,
            substance_name="marijuana",
            quantity_value=0.5,
            quantity_unit=QuantityUnit.OUNCES,
        )
        in_scope, reason = is_mvp_in_scope(offense)
        assert in_scope is False
        assert (
            "sale" in reason.lower()
            or "distribution" in reason.lower()
            or "PWID" in reason
            or "excludes" in reason.lower()
        )

    def test_rejects_sale(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30",
            charge_description="Sale of marijuana",
            conduct_type=ConductType.SALE,
            substance_name="marijuana",
            quantity_value=0.5,
            quantity_unit=QuantityUnit.OUNCES,
        )
        in_scope, reason = is_mvp_in_scope(offense)
        assert in_scope is False

    def test_rejects_distribution(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30",
            charge_description="Distribution of marijuana",
            conduct_type=ConductType.DISTRIBUTION,
            substance_name="marijuana",
            quantity_value=0.5,
            quantity_unit=QuantityUnit.OUNCES,
        )
        in_scope, reason = is_mvp_in_scope(offense)
        assert in_scope is False

    def test_rejects_manufacture(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30",
            charge_description="Manufacture of marijuana",
            conduct_type=ConductType.MANUFACTURE,
            substance_name="marijuana",
            quantity_value=0.5,
            quantity_unit=QuantityUnit.OUNCES,
        )
        in_scope, reason = is_mvp_in_scope(offense)
        assert in_scope is False

    def test_rejects_missing_quantity(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana",
            conduct_type=ConductType.SIMPLE_POSSESSION,
            substance_name="marijuana",
            quantity_value=None,
            quantity_unit=QuantityUnit.UNKNOWN,
        )
        in_scope, reason = is_mvp_in_scope(offense)
        assert in_scope is False
        assert "quantity" in reason.lower()

    def test_rejects_enhancements(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Simple possession of marijuana in school zone",
            conduct_type=ConductType.SIMPLE_POSSESSION,
            substance_name="marijuana",
            quantity_value=0.3,
            quantity_unit=QuantityUnit.OUNCES,
            enhancements=["school_zone"],
        )
        in_scope, reason = is_mvp_in_scope(offense)
        assert in_scope is False
        assert "enhancement" in reason.lower()

    def test_rejects_no_substance(self):
        offense = OffenseDetails(
            statute="O.C.G.A. § 16-13-30(j)(1)",
            charge_description="Possession",
            conduct_type=ConductType.SIMPLE_POSSESSION,
            substance_name=None,
            quantity_value=0.5,
            quantity_unit=QuantityUnit.OUNCES,
        )
        in_scope, reason = is_mvp_in_scope(offense)
        assert in_scope is False


class TestScopeGateNode:
    def _make_state(self, input_data):
        return {
            "input": input_data,
            "scope_status": "insufficient_data",
            "out_of_scope_reason": None,
            "warnings": [],
            "flags": [],
            "ethics_flags": [],
            "audit_records": [],
        }

    def test_in_scope_case(self, in_scope_input):
        state = self._make_state(in_scope_input)
        result = scope_gate(state)
        assert result["scope_status"] == "in_scope"
        assert result["out_of_scope_reason"] is None

    def test_out_of_scope_substance(self, out_of_scope_controlled_substance_input):
        state = self._make_state(out_of_scope_controlled_substance_input)
        result = scope_gate(state)
        assert result["scope_status"] == "out_of_scope"
        assert result["out_of_scope_reason"] is not None

    def test_missing_quantity(self, missing_quantity_input):
        state = self._make_state(missing_quantity_input)
        result = scope_gate(state)
        assert result["scope_status"] == "out_of_scope"
        assert "quantity" in result["out_of_scope_reason"].lower()

    def test_over_one_ounce(self, over_one_ounce_input):
        state = self._make_state(over_one_ounce_input)
        result = scope_gate(state)
        assert result["scope_status"] == "out_of_scope"

    def test_pwid_out_of_scope(self, pwid_input):
        state = self._make_state(pwid_input)
        result = scope_gate(state)
        assert result["scope_status"] == "out_of_scope"

    def test_enhancement_out_of_scope(self, enhancement_input):
        state = self._make_state(enhancement_input)
        result = scope_gate(state)
        assert result["scope_status"] == "out_of_scope"
        assert "enhancement" in result["out_of_scope_reason"].lower()

    def test_self_reported_history_warning(self, self_reported_history_input):
        state = self._make_state(self_reported_history_input)
        result = scope_gate(state)
        assert result["scope_status"] == "in_scope"
        assert any("self-reported" in w.lower() for w in result["warnings"])
        assert any("SELF_REPORTED" in f for f in result["ethics_flags"])

    def test_non_georgia_out_of_scope(self):
        input_data = SentencingAgentInput(
            case_id="test-federal",
            case_phase=CasePhase.PRETRIAL,
            jurisdiction_context=JurisdictionContext(state="georgia", county=""),
            offense_details=OffenseDetails(
                statute="O.C.G.A. § 16-13-30(j)(1)",
                charge_description="Simple possession of marijuana",
                conduct_type=ConductType.SIMPLE_POSSESSION,
                substance_name="marijuana",
                quantity_value=0.5,
                quantity_unit=QuantityUnit.OUNCES,
            ),
            criminal_history=PriorRecord(has_prior_convictions=False),
            personal_circumstances=PersonalCircumstances(),
        )
        state = self._make_state(input_data)
        result = scope_gate(state)
        assert result["scope_status"] == "insufficient_data"

    def test_grams_conversion_in_scope(self, grams_input):
        state = self._make_state(grams_input)
        result = scope_gate(state)
        assert result["scope_status"] == "in_scope"

    def test_audit_record_created(self, in_scope_input):
        state = self._make_state(in_scope_input)
        result = scope_gate(state)
        assert len(result["audit_records"]) == 1
        assert result["audit_records"][0].node_name == "scope_gate"
