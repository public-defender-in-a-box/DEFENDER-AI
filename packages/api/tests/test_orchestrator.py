"""Tests for the Case Orchestrator."""

import pytest

from src.models.case_state import CaseState, PipelineStage


def test_case_state_creation():
    """Test that CaseState initializes with correct defaults."""
    state = CaseState(id="test_001")
    assert state.stage == PipelineStage.CREATED
    assert state.jurisdiction == "IL"
    assert state.charge_processing is None


def test_case_state_advance_stage():
    """Test pipeline stage advancement with history tracking."""
    state = CaseState(id="test_001")
    state.advance_stage(PipelineStage.CHARGES_PROCESSING)
    assert state.stage == PipelineStage.CHARGES_PROCESSING
    assert len(state.stage_history) == 1

    state.advance_stage(PipelineStage.CHARGES_PROCESSED)
    assert state.stage == PipelineStage.CHARGES_PROCESSED
    assert len(state.stage_history) == 2
    assert state.stage_history[0].exited_at is not None
