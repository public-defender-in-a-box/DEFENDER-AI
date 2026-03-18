"""Tests for the Charge Processing Agent."""

import pytest

from src.models.charges import ChargeProcessingInput, ChargeProcessingOutput


def test_charge_processing_input_model():
    """Test that ChargeProcessingInput validates correctly."""
    input_data = ChargeProcessingInput(
        document_text="Sample complaint text",
        document_type="COMPLAINT",
        jurisdiction="IL",
    )
    assert input_data.document_type == "COMPLAINT"
    assert input_data.jurisdiction == "IL"


def test_charge_processing_output_model():
    """Test that ChargeProcessingOutput serializes correctly."""
    output = ChargeProcessingOutput(
        charges=[],
        factual_allegations=[],
        enhancements=[],
        persons_of_interest=[],
        procedural_flags=[],
        raw_document_summary="Test summary",
    )
    data = output.model_dump()
    assert data["raw_document_summary"] == "Test summary"
    assert isinstance(data["charges"], list)
