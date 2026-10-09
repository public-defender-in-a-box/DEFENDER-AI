"""Tests for the Plea/Trial Assessment Agent."""

from __future__ import annotations

import copy
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.services.model_gateway import TransportError
from src.services.model_gateway.testing import FakeCallModel

from src.agents.tier2_attorney.plea_trial_analyst import PleaTrialAnalyst
from tests.fixtures.plea_trial_case_state import (
    SAMPLE_LLM_PLEA_TRIAL_NO_OFFER_RESPONSE,
    SAMPLE_LLM_PLEA_TRIAL_RESPONSE,
    make_full_case_data,
    make_sample_attorney_assessments,
    make_sample_plea_offer,
)


@pytest.fixture
def agent() -> PleaTrialAnalyst:
    return PleaTrialAnalyst()


@pytest.fixture
def full_case_data() -> dict[str, Any]:
    return make_full_case_data()


@pytest.fixture
def mock_llm_full():
    """Canned model response: the full plea/trial response."""
    with patch(
        "src.agents.tier2_attorney.plea_trial_analyst.call_model",
        new_callable=AsyncMock,
        side_effect=FakeCallModel(copy.deepcopy(SAMPLE_LLM_PLEA_TRIAL_RESPONSE)).respond,
    ) as mock:
        yield mock


@pytest.fixture
def mock_llm_no_offer():
    """Canned model response: trial-only response (no plea offer)."""
    with patch(
        "src.agents.tier2_attorney.plea_trial_analyst.call_model",
        new_callable=AsyncMock,
        side_effect=FakeCallModel(copy.deepcopy(SAMPLE_LLM_PLEA_TRIAL_NO_OFFER_RESPONSE)).respond,
    ) as mock:
        yield mock


@pytest.fixture
def mock_llm_error():
    """The model call fails with a transport error."""
    with patch(
        "src.agents.tier2_attorney.plea_trial_analyst.call_model",
        new_callable=AsyncMock,
        side_effect=TransportError("LLM service unavailable"),
    ) as mock:
        yield mock


# -----------------------------------------------------------------------
# 1. test_full_analysis_structure
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_analysis_structure(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
    mock_llm_full: AsyncMock,
) -> None:
    """Given complete case data with plea offer and attorney assessments,
    verify the output contains all required fields."""
    result = await agent.run(full_case_data)

    assert "data" in result
    assert "confidence" in result
    assert "source" in result
    assert "timestamp" in result

    data = result["data"]
    assert "plea_scenario" in data
    assert "trial_scenario" in data
    assert "comparison_matrix" in data
    assert "risk_factors" in data
    assert data["decision_support_warning"] == (
        "DECISION SUPPORT ONLY — ATTORNEY AND CLIENT DECIDE"
    )
    assert data["privilege_warning"] == "ATTORNEY-CLIENT PRIVILEGED MATERIAL"
    assert data["draft_warning"] == "DRAFT — ATTORNEY REVIEW REQUIRED"
    assert "confidence" in data
    assert "confidence_level" in data
    assert "confidence_reasoning" in data
    assert "flags" in data


# -----------------------------------------------------------------------
# 2. test_decision_support_warning_always_present
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decision_support_warning_always_present(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
    mock_llm_full: AsyncMock,
) -> None:
    """The decision_support_warning must always be present."""
    result = await agent.run(full_case_data)
    data = result["data"]
    assert data["decision_support_warning"] == (
        "DECISION SUPPORT ONLY — ATTORNEY AND CLIENT DECIDE"
    )

    # Also verify the flag is always present
    assert "DECISION_SUPPORT_ONLY" in data["flags"]


# -----------------------------------------------------------------------
# 3. test_missing_plea_offer_flag
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_plea_offer_flag(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
    mock_llm_no_offer: AsyncMock,
) -> None:
    """When no plea offer is provided, MISSING_PLEA_OFFER flag should be set."""
    # Remove plea offer
    full_case_data.pop("plea_offer", None)

    result = await agent.run(full_case_data)
    data = result["data"]

    assert "MISSING_PLEA_OFFER" in data["flags"]
    # Trial analysis should still be present
    assert "trial_scenario" in data
    trial = data["trial_scenario"]
    assert "outcomes" in trial


# -----------------------------------------------------------------------
# 4. test_missing_attorney_inputs_flag
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_attorney_inputs_flag(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
    mock_llm_full: AsyncMock,
) -> None:
    """When attorney assessments are absent, MISSING_ATTORNEY_INPUTS flag should be set."""
    full_case_data.pop("attorney_assessments", None)

    result = await agent.run(full_case_data)
    data = result["data"]

    assert "MISSING_ATTORNEY_INPUTS" in data["flags"]


# -----------------------------------------------------------------------
# 5. test_trial_outcome_probabilities_sum
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trial_outcome_probabilities_sum(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
    mock_llm_full: AsyncMock,
) -> None:
    """Trial outcome probabilities should sum to approximately 1.0."""
    result = await agent.run(full_case_data)
    data = result["data"]

    outcomes = data["trial_scenario"]["outcomes"]
    total = sum(o["probability"] for o in outcomes)
    assert abs(total - 1.0) <= 0.1, f"Probabilities sum to {total}, expected ~1.0"


# -----------------------------------------------------------------------
# 6. test_probability_normalization
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_probability_normalization(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
) -> None:
    """If LLM returns probabilities summing to 1.3, agent normalizes and flags."""
    bad_response = copy.deepcopy(SAMPLE_LLM_PLEA_TRIAL_RESPONSE)
    # Inflate probabilities to sum to 1.3
    bad_response["trial_scenario"]["outcomes"][0]["probability"] = 0.50
    bad_response["trial_scenario"]["outcomes"][1]["probability"] = 0.55
    bad_response["trial_scenario"]["outcomes"][2]["probability"] = 0.25

    with patch(
        "src.agents.tier2_attorney.plea_trial_analyst.call_model",
        new_callable=AsyncMock,
        side_effect=FakeCallModel(bad_response).respond,
    ):
        result = await agent.run(full_case_data)

    data = result["data"]

    # Should have a probability normalization flag
    prob_flags = [f for f in data["flags"] if "PROBABILITY_SUM_ERROR" in f]
    assert len(prob_flags) > 0, "Expected PROBABILITY_SUM_ERROR flag"

    # After normalization, probabilities should sum to ~1.0
    outcomes = data["trial_scenario"]["outcomes"]
    total = sum(o["probability"] for o in outcomes)
    assert abs(total - 1.0) <= 0.01, f"After normalization, sum is {total}"


# -----------------------------------------------------------------------
# 7. test_bias_check_flag
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bias_check_flag(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
) -> None:
    """When every comparison dimension favors PLEA, BIAS_CHECK flag should be added."""
    biased_response = copy.deepcopy(SAMPLE_LLM_PLEA_TRIAL_RESPONSE)
    # Make every dimension favor PLEA
    for dim in biased_response["comparison_matrix"]["dimensions"]:
        dim["advantage"] = "PLEA"

    with patch(
        "src.agents.tier2_attorney.plea_trial_analyst.call_model",
        new_callable=AsyncMock,
        side_effect=FakeCallModel(biased_response).respond,
    ):
        result = await agent.run(full_case_data)

    data = result["data"]
    assert "BIAS_CHECK" in data["flags"]


# -----------------------------------------------------------------------
# 8. test_suppression_motion_impact
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suppression_motion_impact(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
    mock_llm_full: AsyncMock,
) -> None:
    """When draft_motions contains a suppression motion with high viability,
    verify the SUPPRESSION_MOTION_CRITICAL flag logic works."""
    # Our fixture already has a suppression motion with viability 0.75
    result = await agent.run(full_case_data)
    data = result["data"]

    assert "SUPPRESSION_MOTION_CRITICAL" in data["flags"]

    # Trial scenario should reference suppression impact
    trial = data["trial_scenario"]
    assert trial.get("suppression_motion_impact")


@pytest.mark.asyncio
async def test_suppression_motion_low_viability(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
    mock_llm_full: AsyncMock,
) -> None:
    """When suppression motion viability is below 0.7, the flag should NOT be set."""
    full_case_data["draft_motions"] = [
        {
            "motion_type": "SUPPRESS",
            "title": "Motion to Suppress",
            "status": "DRAFT",
            "confidence": 0.4,
            "viability": 0.4,
        }
    ]

    result = await agent.run(full_case_data)
    data = result["data"]

    assert "SUPPRESSION_MOTION_CRITICAL" not in data["flags"]


# -----------------------------------------------------------------------
# 9. test_confidence_scoring
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confidence_scoring_full_data(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
    mock_llm_full: AsyncMock,
) -> None:
    """With full data and attorney inputs, confidence should be MEDIUM or HIGH."""
    result = await agent.run(full_case_data)
    data = result["data"]

    assert data["confidence_level"] in ("MEDIUM", "HIGH")
    assert data["confidence"] >= 0.6


@pytest.mark.asyncio
async def test_confidence_scoring_minimal_data(
    agent: PleaTrialAnalyst,
    mock_llm_full: AsyncMock,
) -> None:
    """With minimal data and no attorney inputs, confidence should be lower."""
    minimal_data: dict[str, Any] = {
        "id": "test_case_minimal",
        "jurisdiction": "GA",
        "charges": [{"statute": "O.C.G.A. § 16-13-30(a)"}],
    }

    result = await agent.run(minimal_data)
    data = result["data"]

    # With only 1 of 7 sources present and no attorney inputs,
    # confidence = 0.60 + 0.05 = 0.65 (LOW-MEDIUM range)
    assert data["confidence"] < 0.85


# -----------------------------------------------------------------------
# 10. test_attorney_inputs_recorded
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_attorney_inputs_recorded(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
    mock_llm_full: AsyncMock,
) -> None:
    """When attorney assessments are provided, they should appear in attorney_inputs_used."""
    result = await agent.run(full_case_data)
    data = result["data"]

    assert "attorney_inputs_used" in data
    inputs_used = data["attorney_inputs_used"]
    assert "estimated_acquittal_probability" in inputs_used
    assert inputs_used["estimated_acquittal_probability"] == 0.35
    assert "judge_sentencing_tendency" in inputs_used
    assert inputs_used["judge_sentencing_tendency"] == "MODERATE"


@pytest.mark.asyncio
async def test_attorney_inputs_not_provided_recorded(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
    mock_llm_full: AsyncMock,
) -> None:
    """When attorney assessments are NOT provided, a note should be recorded."""
    full_case_data.pop("attorney_assessments", None)

    result = await agent.run(full_case_data)
    data = result["data"]

    assert "attorney_inputs_used" in data
    assert "_note" in data["attorney_inputs_used"]


# -----------------------------------------------------------------------
# 11. test_llm_failure_handled_gracefully
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_llm_failure_fails_the_agent(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
    mock_llm_error: AsyncMock,
) -> None:
    """A failed model call fails the agent (Phase 1 §3). It used to return a
    zero-confidence "Analysis failed" output carrying the decision-support warning,
    which the Orchestrator would merge."""
    with pytest.raises(TransportError):
        await agent.run(full_case_data)


# -----------------------------------------------------------------------
# 12. test_output_wrapped_correctly
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_output_wrapped_correctly(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
    mock_llm_full: AsyncMock,
) -> None:
    """Verify the output uses BaseAgent.wrap_output format."""
    result = await agent.run(full_case_data)

    # wrap_output format: data, confidence, source, timestamp
    assert "data" in result
    assert "confidence" in result
    assert "source" in result
    assert "timestamp" in result

    assert result["source"] == "plea_trial_analyst"
    assert result["confidence"] in ("HIGH", "MEDIUM", "LOW", "UNRATED")
    assert isinstance(result["data"], dict)


# -----------------------------------------------------------------------
# Additional edge case tests
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trial_may_be_warranted_flag(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
) -> None:
    """If 4+ dimensions favor TRIAL, TRIAL_MAY_BE_WARRANTED flag should be set."""
    trial_favored = copy.deepcopy(SAMPLE_LLM_PLEA_TRIAL_RESPONSE)
    # Set 5 dimensions to favor TRIAL
    for i, dim in enumerate(trial_favored["comparison_matrix"]["dimensions"]):
        if i < 5:
            dim["advantage"] = "TRIAL"

    with patch(
        "src.agents.tier2_attorney.plea_trial_analyst.call_model",
        new_callable=AsyncMock,
        side_effect=FakeCallModel(trial_favored).respond,
    ):
        result = await agent.run(full_case_data)

    data = result["data"]
    assert "TRIAL_MAY_BE_WARRANTED" in data["flags"]


@pytest.mark.asyncio
async def test_significant_collateral_consequences_flag(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
) -> None:
    """If plea triggers HIGH-severity collateral consequences, flag it."""
    high_collateral = copy.deepcopy(SAMPLE_LLM_PLEA_TRIAL_RESPONSE)
    high_collateral["plea_scenario"]["collateral_consequences_detail"] = [
        {
            "category": "immigration",
            "description": "Deportation risk — aggravated felony",
            "severity": "HIGH",
        }
    ]

    with patch(
        "src.agents.tier2_attorney.plea_trial_analyst.call_model",
        new_callable=AsyncMock,
        side_effect=FakeCallModel(high_collateral).respond,
    ):
        result = await agent.run(full_case_data)

    data = result["data"]
    assert "SIGNIFICANT_COLLATERAL_CONSEQUENCES" in data["flags"]


@pytest.mark.asyncio
async def test_missing_collateral_data_flag(
    agent: PleaTrialAnalyst,
    full_case_data: dict[str, Any],
    mock_llm_full: AsyncMock,
) -> None:
    """When collateral consequences data is not available, flag it."""
    full_case_data.pop("collateral_consequences", None)

    result = await agent.run(full_case_data)
    data = result["data"]

    assert "MISSING_COLLATERAL_DATA" in data["flags"]


@pytest.mark.asyncio
async def test_field_name_normalization(
    agent: PleaTrialAnalyst,
    mock_llm_full: AsyncMock,
) -> None:
    """Agent should accept alternative field names from CaseState."""
    alt_data: dict[str, Any] = {
        "id": "test_case_alt",
        "jurisdiction": "GA",
        "charge_processing": {"charges": [{"statute": "O.C.G.A. § 16-13-30(a)"}]},
        "rights_violation_analysis": [{"violation_type": "FOURTH_AMENDMENT"}],
        "intake": {"defendant_name": "Jane Doe"},
        "case_law_research": {"cases": []},
        "brady": {"material": []},
        "plea_offer": make_sample_plea_offer(),
        "attorney_assessments": make_sample_attorney_assessments(),
    }

    result = await agent.run(alt_data)
    assert "data" in result
    assert result["data"]["decision_support_warning"] == (
        "DECISION SUPPORT ONLY — ATTORNEY AND CLIENT DECIDE"
    )
