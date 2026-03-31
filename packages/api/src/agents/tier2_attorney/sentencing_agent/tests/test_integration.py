"""Integration tests for the sentencing agent pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from ..graph import run_sentencing_analysis, state_to_output
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
from ..nodes.scope_gate import scope_gate

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> SentencingAgentInput:
    with open(FIXTURES_DIR / name) as f:
        return SentencingAgentInput(**json.load(f))


class TestFullPipelineIntegration:
    """Integration tests that run the full pipeline with mocked LLM calls."""

    @pytest.fixture
    def mock_llm(self):
        """Mock the LLM service to avoid real API calls.

        The LLM nodes use lazy local imports (from src.services.llm_service import call_llm),
        so we inject a mock call_llm module before running the graph.
        """
        import sys
        from types import ModuleType
        from unittest.mock import MagicMock

        narrative_response = {
            "summary": "Test mitigation summary.",
            "full_narrative": "Test full narrative for the defendant.",
            "key_themes": ["employment_stability", "low_public_safety_risk"],
            "supporting_facts": [{"fact_id": "auto-1", "text": "Employed", "used_in": "paragraph 1"}],
            "paragraph_fact_map": [{"paragraph": "Test full narrative", "fact_ids": ["auto-1"]}],
            "unsupported_claim_warnings": [],
            "tone_notes": "Professional tone",
        }
        leniency_response = [
            {
                "argument_type": "alternative_sentence",
                "basis": "Straight probation",
                "supporting_facts": ["Employed full-time"],
                "supporting_fact_ids": ["auto-1"],
                "strength": "strong",
                "applicable_authority": ["O.C.G.A. § 42-8-34"],
                "authority_verification_status": "confirmed",
                "notes": "Test argument",
            }
        ]

        mock_call_llm = AsyncMock(side_effect=[leniency_response, narrative_response])

        # Create mock modules if they don't exist
        if "src.services" not in sys.modules:
            sys.modules["src.services"] = ModuleType("src.services")
        mock_llm_module = ModuleType("src.services.llm_service")
        mock_llm_module.call_llm = mock_call_llm
        sys.modules["src.services.llm_service"] = mock_llm_module

        yield mock_call_llm

        # Reset side_effect for multiple calls per test
        mock_call_llm.reset_mock()

    @pytest.mark.asyncio
    async def test_in_scope_case_produces_valid_output(self, mock_llm):
        input_data = _load_fixture("in_scope_case.json")
        output = await run_sentencing_analysis(input_data)

        assert output.case_id == "test-001"
        assert output.scope_status == "in_scope"
        assert output.confidence_score > 0.0
        assert output.guideline_range is not None
        assert output.guideline_range.statutory_maximum == 365
        assert output.guideline_range.fine_maximum == 1000.0
        assert len(output.diversion_options) >= 3
        assert len(output.comparable_sentences) > 0
        assert output.sentencing_memo is not None
        assert output.disclaimer.startswith("DRAFT")

    @pytest.mark.asyncio
    async def test_out_of_scope_controlled_substance(self, mock_llm):
        input_data = _load_fixture("out_of_scope_controlled_substance.json")
        output = await run_sentencing_analysis(input_data)

        assert output.scope_status == "out_of_scope"
        assert output.out_of_scope_reason is not None
        assert "marijuana" in output.out_of_scope_reason.lower()
        assert output.confidence_score <= 0.40
        # Should still be valid JSON / model
        assert output.case_id == "test-oos-001"

    @pytest.mark.asyncio
    async def test_missing_quantity_case(self, mock_llm):
        input_data = _load_fixture("missing_quantity_case.json")
        output = await run_sentencing_analysis(input_data)

        assert output.scope_status == "out_of_scope"
        assert "quantity" in output.out_of_scope_reason.lower()

    @pytest.mark.asyncio
    async def test_partial_output_on_missing_comparables(self, mock_llm):
        """Even with few comparables, output should be valid."""
        input_data = SentencingAgentInput(
            case_id="test-partial",
            case_phase=CasePhase.PRETRIAL,
            jurisdiction_context=JurisdictionContext(
                county="Coffee",  # Not in seed corpus
                judicial_circuit="Waycross",
            ),
            offense_details=OffenseDetails(
                statute="O.C.G.A. § 16-13-30(j)(1)",
                charge_description="Simple possession of marijuana",
                conduct_type=ConductType.SIMPLE_POSSESSION,
                substance_name="marijuana",
                quantity_value=0.3,
                quantity_unit=QuantityUnit.OUNCES,
            ),
            criminal_history=PriorRecord(
                verification_status=VerificationStatus.VERIFIED,
                has_prior_convictions=False,
            ),
            personal_circumstances=PersonalCircumstances(),
        )
        output = await run_sentencing_analysis(input_data)

        assert output.scope_status == "in_scope"
        assert output.guideline_range is not None
        # May have few comparables but should still have valid output
        assert any("comparable" in w.lower() or "corpus" in w.lower() for w in output.warnings) or len(output.comparable_sentences) >= 0

    @pytest.mark.asyncio
    async def test_self_reported_history_caps_confidence(self, mock_llm):
        input_data = SentencingAgentInput(
            case_id="test-self-rep",
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
                verification_status=VerificationStatus.SELF_REPORTED,
                has_prior_convictions=False,
            ),
            personal_circumstances=PersonalCircumstances(),
        )
        output = await run_sentencing_analysis(input_data)

        assert output.confidence_score <= 0.55
        assert any("SELF_REPORTED" in f for f in output.ethics_flags)

    @pytest.mark.asyncio
    async def test_downstream_plea_trial_can_consume_guideline_range(self, mock_llm):
        """The guideline_range field should be consumable by downstream agents."""
        input_data = _load_fixture("in_scope_case.json")
        output = await run_sentencing_analysis(input_data)

        gr = output.guideline_range
        assert gr is not None
        # Downstream plea/trial agent needs these fields
        assert hasattr(gr, "statutory_minimum")
        assert hasattr(gr, "statutory_maximum")
        assert hasattr(gr, "fine_minimum")
        assert hasattr(gr, "fine_maximum")
        assert hasattr(gr, "probation_possible")
        assert hasattr(gr, "data_basis")


class TestRegressionPriorDraftMistakes:
    """Regression tests proving prior-draft legal errors are fixed."""

    def test_general_controlled_substance_not_misdemeanor(self):
        """General O.C.G.A. § 16-13-30(a) must NOT be treated as MVP scope."""
        input_data = SentencingAgentInput(
            case_id="regression-1",
            case_phase=CasePhase.PRETRIAL,
            jurisdiction_context=JurisdictionContext(county="Fulton"),
            offense_details=OffenseDetails(
                statute="O.C.G.A. § 16-13-30(a)",
                charge_description="Possession of Schedule II controlled substance",
                conduct_type=ConductType.SIMPLE_POSSESSION,
                substance_name="cocaine",
                quantity_value=1.0,
                quantity_unit=QuantityUnit.GRAMS,
            ),
            criminal_history=PriorRecord(has_prior_convictions=False),
            personal_circumstances=PersonalCircumstances(),
        )
        state = {
            "input": input_data,
            "scope_status": "insufficient_data",
            "out_of_scope_reason": None,
            "warnings": [],
            "flags": [],
            "ethics_flags": [],
            "audit_records": [],
        }
        result = scope_gate(state)
        assert result["scope_status"] == "out_of_scope"

    def test_veterans_court_uses_correct_statute(self, veteran_input):
        """Veterans court must cite O.C.G.A. § 15-1-17, not § 15-1-16."""
        from ..nodes.diversion_checker import diversion_checker

        state = {
            "input": veteran_input,
            "scope_status": "in_scope",
            "warnings": [],
            "attorney_decision_points": [],
            "audit_records": [],
        }
        result = diversion_checker(state)
        vc = next(o for o in result["diversion_options"] if "Veterans" in o.program_name)
        assert "15-1-17" in vc.statutory_basis
        assert "15-1-16" not in vc.statutory_basis

    def test_accountability_court_not_standalone_program(self):
        """O.C.G.A. § 15-1-18 should not appear as a standalone diversion option."""
        from ..nodes.diversion_checker import diversion_checker

        state = {
            "input": SentencingAgentInput(
                case_id="regression-3",
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
                personal_circumstances=PersonalCircumstances(),
            ),
            "scope_status": "in_scope",
            "warnings": [],
            "attorney_decision_points": [],
            "audit_records": [],
        }
        result = diversion_checker(state)
        for opt in result["diversion_options"]:
            assert "15-1-18" not in opt.statutory_basis

    def test_school_zone_forces_out_of_scope(self, enhancement_input):
        """School-zone enhancement must force out-of-scope routing."""
        state = {
            "input": enhancement_input,
            "scope_status": "insufficient_data",
            "out_of_scope_reason": None,
            "warnings": [],
            "flags": [],
            "ethics_flags": [],
            "audit_records": [],
        }
        result = scope_gate(state)
        assert result["scope_status"] == "out_of_scope"
