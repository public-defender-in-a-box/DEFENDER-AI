"""Tests for the Motion Drafter Agent."""

from __future__ import annotations

import copy
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.tier2_attorney.motion_drafter import MotionDrafterAgent
from tests.fixtures.sample_case_state import (
    SAMPLE_LLM_BAIL_RESPONSE,
    SAMPLE_LLM_DISCOVERY_RESPONSE,
    SAMPLE_LLM_SUPPRESS_RESPONSE,
    make_minimal_case_state,
    make_sample_case_state,
)


@pytest.fixture
def agent() -> MotionDrafterAgent:
    return MotionDrafterAgent()


@pytest.fixture
def case_state() -> dict[str, Any]:
    return make_sample_case_state()


@pytest.fixture
def minimal_case_state() -> dict[str, Any]:
    return make_minimal_case_state()


@pytest.fixture
def mock_llm_suppress():
    """Mock call_llm returning a suppression motion."""
    with patch(
        "src.agents.tier2_attorney.motion_drafter.call_llm",
        new_callable=AsyncMock,
        return_value=copy.deepcopy(SAMPLE_LLM_SUPPRESS_RESPONSE),
    ) as mock:
        yield mock


@pytest.fixture
def mock_llm_discovery():
    """Mock call_llm returning a discovery motion."""
    with patch(
        "src.agents.tier2_attorney.motion_drafter.call_llm",
        new_callable=AsyncMock,
        return_value=copy.deepcopy(SAMPLE_LLM_DISCOVERY_RESPONSE),
    ) as mock:
        yield mock


@pytest.fixture
def mock_llm_bail():
    """Mock call_llm returning a bail reduction motion."""
    with patch(
        "src.agents.tier2_attorney.motion_drafter.call_llm",
        new_callable=AsyncMock,
        return_value=copy.deepcopy(SAMPLE_LLM_BAIL_RESPONSE),
    ) as mock:
        yield mock


@pytest.fixture
def mock_llm_error():
    """Mock call_llm that raises an exception."""
    with patch(
        "src.agents.tier2_attorney.motion_drafter.call_llm",
        new_callable=AsyncMock,
        side_effect=Exception("LLM service unavailable"),
    ) as mock:
        yield mock


# -----------------------------------------------------------------------
# 1. Basic output structure
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_output_wrapped_correctly(
    agent: MotionDrafterAgent,
    case_state: dict[str, Any],
    mock_llm_suppress: AsyncMock,
) -> None:
    """Verify the output uses BaseAgent.wrap_output format."""
    result = await agent.run(case_state)

    assert "data" in result
    assert "confidence" in result
    assert "source" in result
    assert "timestamp" in result
    assert result["source"] == "motion_drafter"


# -----------------------------------------------------------------------
# 2. Suppression motion draft
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_suppress_motion_draft(
    agent: MotionDrafterAgent,
    case_state: dict[str, Any],
    mock_llm_suppress: AsyncMock,
) -> None:
    """Given rights violations, a suppress motion should be drafted."""
    result = await agent.run(case_state)
    data = result["data"]

    motions = data["motions"]
    assert len(motions) == 1
    motion = motions[0]
    assert motion["type"] == "SUPPRESS"
    assert motion["status"] == "DRAFT"
    assert "DRAFT — ATTORNEY REVIEW REQUIRED" in motion["draft"]
    assert len(motion["supporting_authority"]) > 0


# -----------------------------------------------------------------------
# 3. Discovery motion draft
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_discovery_motion_draft(
    agent: MotionDrafterAgent,
    case_state: dict[str, Any],
    mock_llm_discovery: AsyncMock,
) -> None:
    """A discovery motion should contain Brady references."""
    result = await agent.run(case_state)
    data = result["data"]

    motions = data["motions"]
    assert len(motions) == 1
    motion = motions[0]
    assert motion["type"] == "DISCOVERY"
    assert "DRAFT — ATTORNEY REVIEW REQUIRED" in motion["draft"]


# -----------------------------------------------------------------------
# 4. Bail reduction motion draft
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bail_motion_draft(
    agent: MotionDrafterAgent,
    case_state: dict[str, Any],
    mock_llm_bail: AsyncMock,
) -> None:
    """A bail reduction motion should reference personal circumstances."""
    result = await agent.run(case_state)
    data = result["data"]

    motions = data["motions"]
    assert len(motions) == 1
    motion = motions[0]
    assert motion["type"] == "BAIL_REDUCTION"
    assert "DRAFT — ATTORNEY REVIEW REQUIRED" in motion["draft"]


# -----------------------------------------------------------------------
# 5. Case state field names are used correctly
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_case_state_fields(
    agent: MotionDrafterAgent,
    case_state: dict[str, Any],
    mock_llm_suppress: AsyncMock,
) -> None:
    """Verify the sample case state has the expected motion-drafter schema."""
    assert case_state["case_id"] == "test_case_GA_2024_001"
    assert case_state["case_number"] == "24-CR-12345"

    charge = case_state["charges"][0]
    assert "statute_section" in charge
    assert "offense_title" in charge
    assert "degree" in charge
    assert "elements" in charge
    assert "penalty_range" in charge
    assert "procedural_requirements" in charge
    assert "factual_allegations" in charge
    assert "officers" in charge
    assert "witnesses" in charge

    intake = case_state["intake"]
    assert "client_account" in intake
    assert "facts" in intake
    assert "inconsistencies" in intake
    assert intake["personal_circumstances"]["custody_status"] == "IN_CUSTODY"

    research = case_state["legal_research"]
    assert "statutes" in research
    assert "case_law" in research
    assert research["statutes"][0]["verification_status"] == "VERIFIED"
    assert research["case_law"][0]["verification_status"] == "UNVERIFIED"

    brady = case_state["brady"]
    assert "gaps" in brady
    assert "giglio_checklist" in brady
    assert "missing_reports" in brady


# -----------------------------------------------------------------------
# 6. Minimal case state
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_minimal_case_state_fields(
    agent: MotionDrafterAgent,
    minimal_case_state: dict[str, Any],
    mock_llm_suppress: AsyncMock,
) -> None:
    """Verify minimal case state has correct identity fields."""
    assert minimal_case_state["case_id"] == "test_case_GA_2024_002"
    assert minimal_case_state["case_number"] == "24-CR-99999"
    assert minimal_case_state["charges"] == []
    assert minimal_case_state["intake"] == {}
    assert minimal_case_state["legal_research"]["statutes"] == []
    assert minimal_case_state["legal_research"]["case_law"] == []
    assert minimal_case_state["brady"]["gaps"] == []
    assert minimal_case_state["brady"]["giglio_checklist"] == []
    assert minimal_case_state["brady"]["missing_reports"] == []


# -----------------------------------------------------------------------
# 7. Minimal case state still produces output
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_minimal_case_state_produces_output(
    agent: MotionDrafterAgent,
    minimal_case_state: dict[str, Any],
    mock_llm_suppress: AsyncMock,
) -> None:
    """Even with minimal data, agent should produce a valid wrapped output."""
    result = await agent.run(minimal_case_state)

    assert "data" in result
    assert "confidence" in result
    assert result["source"] == "motion_drafter"


# -----------------------------------------------------------------------
# 8. All mock motion drafts include DRAFT warning
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_all_drafts_have_attorney_review_warning(
    agent: MotionDrafterAgent,
    case_state: dict[str, Any],
) -> None:
    """Every motion draft must start with DRAFT — ATTORNEY REVIEW REQUIRED."""
    for response in [
        SAMPLE_LLM_SUPPRESS_RESPONSE,
        SAMPLE_LLM_DISCOVERY_RESPONSE,
        SAMPLE_LLM_BAIL_RESPONSE,
    ]:
        with patch(
            "src.agents.tier2_attorney.motion_drafter.call_llm",
            new_callable=AsyncMock,
            return_value=copy.deepcopy(response),
        ):
            result = await agent.run(case_state)
            for motion in result["data"]["motions"]:
                assert motion["draft"].startswith("DRAFT — ATTORNEY REVIEW REQUIRED")


# -----------------------------------------------------------------------
# 9. Citations tagged with verification status
# -----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_citations_tagged_with_verification(
    agent: MotionDrafterAgent,
    case_state: dict[str, Any],
    mock_llm_suppress: AsyncMock,
) -> None:
    """Supporting authority should tag citations as VERIFIED or UNVERIFIED."""
    result = await agent.run(case_state)
    motion = result["data"]["motions"][0]

    for citation in motion["supporting_authority"]:
        assert "[VERIFIED]" in citation or "[UNVERIFIED]" in citation
