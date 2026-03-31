"""Tests for the Motion Drafter Agent.

All LLM calls are mocked — tests run without an API key.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.tier2_attorney.motion_drafter import MotionDrafterAgent
from src.models.motions import DraftMotion, MotionDrafterOutput, MotionType
from tests.fixtures.sample_case_state import (
    SAMPLE_LLM_BAIL_RESPONSE,
    SAMPLE_LLM_DISCOVERY_RESPONSE,
    SAMPLE_LLM_SUPPRESS_RESPONSE,
    make_minimal_case_state,
    make_sample_case_state,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_call_llm_side_effect(prompt: str, **kwargs) -> dict:
    """Return the appropriate mock response based on the prompt content."""
    prompt_lower = prompt.lower()
    if "suppress" in prompt_lower:
        return SAMPLE_LLM_SUPPRESS_RESPONSE
    elif "discovery" in prompt_lower or "brady" in prompt_lower:
        return SAMPLE_LLM_DISCOVERY_RESPONSE
    elif "bail" in prompt_lower:
        return SAMPLE_LLM_BAIL_RESPONSE
    # Default fallback
    return SAMPLE_LLM_DISCOVERY_RESPONSE


@pytest.fixture
def agent() -> MotionDrafterAgent:
    return MotionDrafterAgent()


@pytest.fixture
def full_case_data() -> dict:
    """Full case state data as input_data for the agent."""
    state = make_sample_case_state()
    return {
        "case_id": state["case_id"],
        "case_number": state["case_number"],
        "jurisdiction": state["jurisdiction"],
        "charges": state["charges"],
        "rights_violations": state["rights_violations"],
        "intake_summary": state["intake_summary"],
        "legal_research": state["legal_research"],
        "brady_analysis": state["brady_analysis"],
    }


@pytest.fixture
def minimal_case_data() -> dict:
    """Minimal case state with no rights violations."""
    state = make_minimal_case_state()
    return {
        "case_id": state["case_id"],
        "case_number": state["case_number"],
        "jurisdiction": state["jurisdiction"],
        "charges": state["charges"],
        "rights_violations": state["rights_violations"],
        "intake_summary": state["intake_summary"],
        "legal_research": state["legal_research"],
        "brady_analysis": state["brady_analysis"],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@patch("src.agents.tier2_attorney.motion_drafter.call_llm", new_callable=AsyncMock)
async def test_determines_applicable_motions(
    mock_llm: AsyncMock, agent: MotionDrafterAgent, full_case_data: dict
) -> None:
    """Given full case state, suppress + discovery + bail should be generated."""
    mock_llm.side_effect = _mock_call_llm_side_effect

    result = await agent.run(full_case_data)
    output_data = result["data"]

    generated_types = {m["motion_type"] for m in output_data["motions"]}
    # Suppress (rights violation viability 0.75) and discovery (always) must be present
    assert MotionType.SUPPRESS.value in generated_types
    assert MotionType.DISCOVERY_BRADY.value in generated_types
    # Bail reduction because client is in custody
    assert MotionType.BAIL_REDUCTION.value in generated_types


@pytest.mark.asyncio
@patch("src.agents.tier2_attorney.motion_drafter.call_llm", new_callable=AsyncMock)
async def test_suppress_motion_structure(
    mock_llm: AsyncMock, agent: MotionDrafterAgent, full_case_data: dict
) -> None:
    """Verify a suppression motion has all required sections and warnings."""
    mock_llm.side_effect = _mock_call_llm_side_effect

    result = await agent.run(full_case_data)
    output_data = result["data"]

    suppress_motions = [
        m for m in output_data["motions"] if m["motion_type"] == MotionType.SUPPRESS.value
    ]
    assert len(suppress_motions) == 1

    motion = suppress_motions[0]
    # Validate as DraftMotion model
    dm = DraftMotion(**motion)

    assert len(dm.sections) >= 3  # Introduction, facts, argument, conclusion
    assert dm.draft_warning == "DRAFT — ATTORNEY REVIEW REQUIRED"
    assert dm.privilege_warning == "ATTORNEY-CLIENT PRIVILEGED MATERIAL"
    assert dm.prayer_for_relief

    # At least one citation somewhere
    all_citations = []
    for s in dm.sections:
        all_citations.extend(s.citations)
    assert len(all_citations) > 0


@pytest.mark.asyncio
@patch("src.agents.tier2_attorney.motion_drafter.call_llm", new_callable=AsyncMock)
async def test_confidence_scoring(
    mock_llm: AsyncMock, agent: MotionDrafterAgent, full_case_data: dict
) -> None:
    """Verify confidence scoring logic."""
    mock_llm.side_effect = _mock_call_llm_side_effect

    result = await agent.run(full_case_data)
    output_data = result["data"]

    for motion in output_data["motions"]:
        dm = DraftMotion(**motion)
        assert 0.0 <= dm.confidence <= 1.0
        assert dm.confidence_level in ("HIGH", "MEDIUM", "LOW")

        # With full data, confidence should be at least MEDIUM
        assert (
            dm.confidence >= 0.6
        ), f"{dm.motion_type} has unexpectedly low confidence: {dm.confidence}"


@pytest.mark.asyncio
@patch("src.agents.tier2_attorney.motion_drafter.call_llm", new_callable=AsyncMock)
async def test_missing_upstream_data_flag(
    mock_llm: AsyncMock, agent: MotionDrafterAgent, minimal_case_data: dict
) -> None:
    """When rights_violations is empty, suppress is skipped."""
    mock_llm.side_effect = _mock_call_llm_side_effect

    result = await agent.run(minimal_case_data)
    output_data = result["data"]

    generated_types = {m["motion_type"] for m in output_data["motions"]}
    assert MotionType.SUPPRESS.value not in generated_types

    # Should be in motions_not_generated
    skipped_types = {m["motion_type"] for m in output_data["motions_not_generated"]}
    assert MotionType.SUPPRESS.value in skipped_types

    # Check reason mentions missing rights violations
    suppress_skip = next(
        m
        for m in output_data["motions_not_generated"]
        if m["motion_type"] == MotionType.SUPPRESS.value
    )
    assert (
        "rights violation" in suppress_skip["reason"].lower()
        or "no rights" in suppress_skip["reason"].lower()
    )


@pytest.mark.asyncio
@patch("src.agents.tier2_attorney.motion_drafter.call_llm", new_callable=AsyncMock)
async def test_unverified_citation_flag(
    mock_llm: AsyncMock, agent: MotionDrafterAgent, full_case_data: dict
) -> None:
    """When a motion includes UNVERIFIED citations, the flag is present."""
    mock_llm.side_effect = _mock_call_llm_side_effect

    result = await agent.run(full_case_data)
    output_data = result["data"]

    # The suppress motion mock has an [UNVERIFIED] citation (State v. Allen)
    suppress_motions = [
        m for m in output_data["motions"] if m["motion_type"] == MotionType.SUPPRESS.value
    ]
    assert len(suppress_motions) == 1

    motion = suppress_motions[0]
    assert "UNVERIFIED_CITATIONS" in motion["flags"]


@pytest.mark.asyncio
@patch("src.agents.tier2_attorney.motion_drafter.call_llm", new_callable=AsyncMock)
async def test_draft_warning_always_present(
    mock_llm: AsyncMock, agent: MotionDrafterAgent, full_case_data: dict
) -> None:
    """Every generated motion must have the draft warning."""
    mock_llm.side_effect = _mock_call_llm_side_effect

    result = await agent.run(full_case_data)
    output_data = result["data"]

    for motion_data in output_data["motions"]:
        dm = DraftMotion(**motion_data)
        assert dm.draft_warning == "DRAFT — ATTORNEY REVIEW REQUIRED"
        assert dm.privilege_warning == "ATTORNEY-CLIENT PRIVILEGED MATERIAL"


@pytest.mark.asyncio
@patch("src.agents.tier2_attorney.motion_drafter.call_llm", new_callable=AsyncMock)
async def test_all_motions_have_confidence(
    mock_llm: AsyncMock, agent: MotionDrafterAgent, full_case_data: dict
) -> None:
    """Every DraftMotion must have non-null confidence and confidence_level."""
    mock_llm.side_effect = _mock_call_llm_side_effect

    result = await agent.run(full_case_data)
    output_data = result["data"]

    assert len(output_data["motions"]) > 0
    for motion_data in output_data["motions"]:
        dm = DraftMotion(**motion_data)
        assert dm.confidence is not None
        assert dm.confidence_level is not None
        assert dm.confidence_level in ("HIGH", "MEDIUM", "LOW")
        assert dm.confidence_reasoning


@pytest.mark.asyncio
@patch("src.agents.tier2_attorney.motion_drafter.call_llm", new_callable=AsyncMock)
async def test_golden_output_structure(
    mock_llm: AsyncMock, agent: MotionDrafterAgent, full_case_data: dict
) -> None:
    """Golden output test: verify structural properties of the full output."""
    mock_llm.side_effect = _mock_call_llm_side_effect

    result = await agent.run(full_case_data)
    output_data = result["data"]

    # Validate as MotionDrafterOutput
    output = MotionDrafterOutput(**output_data)

    # Structural checks (not string-equality)
    assert output.agent_name == "motion_drafter"
    assert len(output.motions) >= 2  # At least suppress + discovery

    generated_types = {m.motion_type for m in output.motions}
    assert MotionType.SUPPRESS in generated_types
    assert MotionType.DISCOVERY_BRADY in generated_types
    assert MotionType.BAIL_REDUCTION in generated_types

    # Overall confidence should be reasonable
    assert 0.5 <= output.overall_confidence <= 1.0
    assert output.overall_confidence_level in ("HIGH", "MEDIUM", "LOW")

    # UNVERIFIED_CITATIONS flag should appear somewhere (suppress mock has one)
    all_flags = []
    for m in output.motions:
        all_flags.extend(m.flags)
    assert "UNVERIFIED_CITATIONS" in all_flags

    # FACT_DISCREPANCY flag should appear (there's a critical inconsistency)
    assert "FACT_DISCREPANCY" in all_flags

    # Motions not generated should explain why
    skipped_types = {m["motion_type"] for m in output.motions_not_generated}
    # Dismiss and limine should be skipped for the sample fixture
    assert MotionType.DISMISS.value in skipped_types
    assert MotionType.LIMINE.value in skipped_types

    for skipped in output.motions_not_generated:
        assert "reason" in skipped
        assert len(skipped["reason"]) > 0


@pytest.mark.asyncio
@patch("src.agents.tier2_attorney.motion_drafter.call_llm", new_callable=AsyncMock)
async def test_discovery_always_generated(
    mock_llm: AsyncMock, agent: MotionDrafterAgent, minimal_case_data: dict
) -> None:
    """Discovery/Brady demand should always be generated, even with minimal data."""
    mock_llm.side_effect = _mock_call_llm_side_effect

    result = await agent.run(minimal_case_data)
    output_data = result["data"]

    generated_types = {m["motion_type"] for m in output_data["motions"]}
    assert MotionType.DISCOVERY_BRADY.value in generated_types


@pytest.mark.asyncio
@patch("src.agents.tier2_attorney.motion_drafter.call_llm", new_callable=AsyncMock)
async def test_llm_failure_handled_gracefully(
    mock_llm: AsyncMock, agent: MotionDrafterAgent, full_case_data: dict
) -> None:
    """If the LLM call fails, the agent should not crash."""
    mock_llm.side_effect = Exception("API unavailable")

    result = await agent.run(full_case_data)
    output_data = result["data"]

    # No motions generated but agent didn't crash
    assert output_data["motions"] == []
    assert len(output_data["warnings"]) > 0


@pytest.mark.asyncio
@patch("src.agents.tier2_attorney.motion_drafter.call_llm", new_callable=AsyncMock)
async def test_output_wrapped_with_confidence(
    mock_llm: AsyncMock, agent: MotionDrafterAgent, full_case_data: dict
) -> None:
    """Verify the output uses BaseAgent.wrap_output format."""
    mock_llm.side_effect = _mock_call_llm_side_effect

    result = await agent.run(full_case_data)

    assert "data" in result
    assert "confidence" in result
    assert "source" in result
    assert result["source"] == "motion_drafter"
    assert "timestamp" in result
