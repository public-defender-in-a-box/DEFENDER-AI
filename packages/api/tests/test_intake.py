"""Tests for the Intake models."""

import pytest

from src.models.intake import IntakeMessage, IntakeFactItem, IntakeSummaryOutput


def test_intake_message_model():
    """Test IntakeMessage creation."""
    msg = IntakeMessage(
        id="msg_001",
        timestamp="2024-01-15T10:00:00Z",
        sender="SYSTEM",
        content="Can you tell me what happened?",
        generated_by="INTAKE_CONDUCTOR",
        target_element="arrest_timeline",
    )
    assert msg.sender == "SYSTEM"
    assert msg.generated_by == "INTAKE_CONDUCTOR"


def test_intake_fact_item():
    """Test IntakeFactItem with confidence rating."""
    fact = IntakeFactItem(
        id="fact_001",
        category="ARREST_TIMELINE",
        statement="Client was stopped at approximately 2:30 AM",
        confidence="HIGH",
        source_message_ids=["msg_003"],
    )
    assert fact.confidence == "HIGH"
    assert len(fact.source_message_ids) == 1
