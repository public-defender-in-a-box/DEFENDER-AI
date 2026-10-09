"""The Ethics Monitor is a sensor, not a filter (CLAUDE.md §3.1; PHASE_1 §4).

A CRITICAL flag no longer discards the output or stops the pipeline: the output
merges carrying the flag, and the merge records ``would_have_blocked`` so "how often
would a deployable product have blocked this" stays measurable. LOW-confidence
outputs are no longer exempt from inspection.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from src.agents.tier0.orchestrator import MergeDecision, OrchestratorAgent
from src.models.case_state import PipelineStage
from src.services import measurements
from src.services.model_gateway import AuthError


def _output(data: Any, confidence: str = "HIGH") -> dict[str, Any]:
    return {
        "data": data,
        "confidence": confidence,
        "source": "charge_processing",
        "timestamp": "2026-10-09T00:00:00",
    }


@pytest.fixture
async def orchestrator() -> OrchestratorAgent:
    orch = OrchestratorAgent()
    await orch.run({"case_id": "SYN-SENSOR-001"})
    orch.mark_agent_started("charge_processing")
    return orch


async def test_critical_flag_merges(orchestrator: OrchestratorAgent) -> None:
    # Synthetic SSN-shaped string: the monitor's PII rule marks it CRITICAL.
    output = _output({"charges": [], "note": "Client SSN is 123-45-6789 for records."})
    merge = await orchestrator.receive_agent_output("charge_processing", output)

    assert merge["decision"] == MergeDecision.MERGED_WITH_CRITICAL_FLAG.value
    assert merge["would_have_blocked"] is True
    assert any(f["priority"] == "CRITICAL" for f in merge["flags"])
    # The output is present in CaseState and the pipeline advanced.
    assert orchestrator.case_state.charge_processing is output
    assert orchestrator.case_state.stage == PipelineStage.CHARGES_PROCESSED
    assert orchestrator.get_status().blocked is False
    # The merge records what a deployable product would have done.
    assert orchestrator._merge_history[-1]["would_have_blocked"] is True
    assert orchestrator.case_state.audit_log[-1]["would_have_blocked"] is True
    assert any(
        f["merge_decision"] == "MERGED_WITH_CRITICAL_FLAG"
        for f in orchestrator.case_state.ethical_flags
    )
    (event,) = measurements.events(measurements.MeasurementKind.MERGE_DECISION)
    assert event.payload["would_have_blocked"] is True


async def test_monitor_blocked_flag_alone_is_recorded(orchestrator: OrchestratorAgent) -> None:
    orchestrator._ethics_monitor.run = AsyncMock(  # type: ignore[method-assign]
        return_value={"flags": [], "blocked": True}
    )
    merge = await orchestrator.receive_agent_output("charge_processing", _output({"x": 1}))
    assert merge["decision"] == MergeDecision.MERGED_WITH_CRITICAL_FLAG.value
    assert orchestrator.case_state.charge_processing is not None


async def test_low_confidence_is_ethics_checked(orchestrator: OrchestratorAgent) -> None:
    real_run = orchestrator._ethics_monitor.run
    spy = AsyncMock(side_effect=real_run)
    orchestrator._ethics_monitor.run = spy  # type: ignore[method-assign]

    output = _output({"charges": [], "note": "Client SSN is 123-45-6789."}, confidence="LOW")
    merge = await orchestrator.receive_agent_output("charge_processing", output)

    spy.assert_awaited_once()
    assert merge["would_have_blocked"] is True
    assert merge["decision"] == MergeDecision.MERGED_WITH_CRITICAL_FLAG.value
    assert merge["human_review_required"] is True
    assert orchestrator.case_state.charge_processing["data"]["_low_confidence_flag"] is True


async def test_clean_low_confidence_merges_with_flag(orchestrator: OrchestratorAgent) -> None:
    merge = await orchestrator.receive_agent_output(
        "charge_processing", _output({"charges": []}, confidence="LOW")
    )
    assert merge["decision"] == MergeDecision.MERGED_WITH_FLAG.value
    assert merge["would_have_blocked"] is False


async def test_failure_records_error_type(orchestrator: OrchestratorAgent) -> None:
    failure = await orchestrator.handle_agent_failure(
        "charge_processing", AuthError("The API rejected the key (401)")
    )
    assert failure["decision"] == "FAILED"
    assert failure["error_type"] == "AuthError"
    assert orchestrator.case_state.audit_log[-1]["error_type"] == "AuthError"
    (event,) = measurements.events(measurements.MeasurementKind.AGENT_FAILURE)
    assert event.payload["error_type"] == "AuthError"
    assert event.case_id == "SYN-SENSOR-001"


def test_blocked_ethics_p1_is_gone() -> None:
    assert "BLOCKED_ETHICS_P1" not in MergeDecision.__members__


# ---------------------------------------------------------------------------
# The Tier 2 intake node ran its own blocking check, outside the Orchestrator.
# ---------------------------------------------------------------------------


def _graph_state() -> dict[str, Any]:
    return {
        "case_id": "SYN-SENSOR-002",
        "case_state": {
            "charge_processing": {"data": {"charges": [{"charge_id": "c1"}]}},
            "intake_summary": {
                "facts": [],
                "transcript": [{"id": "msg_001", "content": "I was walking home"}],
                "personal_circumstances": {"employment_status": "Employed"},
                "unanswered_questions": [],
                "priorities_and_concerns": [],
            },
        },
        "current_stage": "INTAKE_IN_PROGRESS",
        "error": None,
    }


def _patch_subagents(fact: Any, collateral: Any, personal: Any) -> Any:
    from contextlib import ExitStack
    from unittest.mock import patch

    stack = ExitStack()
    for path, value in (
        ("src.agents.tier2_intake.fact_gatherer.FactGathererAgent.run", fact),
        ("src.agents.tier2_intake.collateral_agent.CollateralConsequencesAgent.run", collateral),
        (
            "src.agents.tier2_intake.personal_circumstances.PersonalCircumstancesAgent.run",
            personal,
        ),
    ):
        mock = (
            AsyncMock(side_effect=value)
            if isinstance(value, BaseException)
            else AsyncMock(return_value=value)
        )
        stack.enter_context(patch(path, new=mock))
    return stack


async def test_intake_subagent_critical_flag_merges() -> None:
    from src.agents.graph import intake_sub_agents_node

    flagged = _output({"note": "Client SSN is 123-45-6789."})
    clean = _output({"ok": True})
    with _patch_subagents(flagged, clean, clean):
        state = await intake_sub_agents_node(_graph_state())

    assert state["case_state"]["fact_gathering"] is flagged, "merged, not replaced"
    assert any(
        f["merge_decision"] == "MERGED_WITH_CRITICAL_FLAG"
        for f in state["case_state"]["ethical_flags"]
    )
    decisions = {
        e.agent_id: e.payload["would_have_blocked"]
        for e in measurements.events(measurements.MeasurementKind.MERGE_DECISION)
    }
    assert decisions == {
        "fact_gatherer": True,
        "collateral_consequences": False,
        "personal_circumstances": False,
    }


async def test_intake_subagent_model_failure_is_recorded() -> None:
    from src.agents.graph import intake_sub_agents_node

    clean = _output({"ok": True})
    with _patch_subagents(AuthError("401"), clean, clean):
        state = await intake_sub_agents_node(_graph_state())

    slot = state["case_state"]["fact_gathering"]
    assert slot["status"] == "FAILED" and slot["error_type"] == "AuthError"
    assert state["case_state"]["collateral_consequences"] is clean
    (failure,) = measurements.events(measurements.MeasurementKind.AGENT_FAILURE)
    assert failure.agent_id == "fact_gatherer"


async def test_intake_subagent_bug_is_not_swallowed() -> None:
    from src.agents.graph import intake_sub_agents_node

    clean = _output({"ok": True})
    with _patch_subagents(KeyError("charges"), clean, clean), pytest.raises(KeyError):
        await intake_sub_agents_node(_graph_state())
