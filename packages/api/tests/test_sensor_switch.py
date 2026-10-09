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
