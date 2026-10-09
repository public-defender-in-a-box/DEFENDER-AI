"""Tests for model output validation in the sentencing agent's two model calls.

The two fallback tests (``test_fallback_arguments_work``,
``test_fallback_narrative_has_warning``) were deleted with the fallbacks they tested
(PHASE_1_MODEL_GATEWAY.md §3.2). Parsing is now validation against the response
models the gateway enforces.
"""

from __future__ import annotations

import re

import pytest
from pydantic import ValidationError

from src.models.responses.sentencing import LeniencyArguments, NarrativeDraft

from ..nodes.leniency_argument_builder import _to_departure_arguments
from ..nodes.mitigation_narrative_builder import _abstention_narrative, _to_narrative


def _argument(**overrides: object) -> dict:
    argument = {
        "argument_type": "alternative_sentence",
        "basis": "Straight probation",
        "supporting_facts": ["Employed full-time"],
        "supporting_fact_ids": ["auto-1"],
        "strength": "strong",
        "applicable_authority": ["O.C.G.A. § 42-8-34"],
        "authority_verification_status": "confirmed",
        "notes": "Strong candidate for probation",
    }
    argument.update(overrides)
    return argument


class TestLeniencyArgumentParsing:
    def test_parse_valid_arguments(self):
        results = _to_departure_arguments(
            LeniencyArguments.model_validate({"arguments": [_argument()]})
        )
        assert len(results) == 1
        assert results[0].basis == "Straight probation"
        assert results[0].strength == "strong"

    def test_parse_empty_returns_empty(self):
        assert _to_departure_arguments(LeniencyArguments.model_validate({"arguments": []})) == []

    def test_malformed_argument_is_rejected_not_skipped(self):
        """It used to be skipped silently; now the whole response fails validation."""
        with pytest.raises(ValidationError):
            LeniencyArguments.model_validate({"arguments": [_argument(strength="overwhelming")]})


NARRATIVE = {
    "summary": "Test summary",
    "full_narrative": "Test narrative paragraph.",
    "key_themes": ["employment_stability"],
    "supporting_facts": [{"fact_id": "auto-1", "text": "Employed", "used_in": "p1"}],
    "paragraph_fact_map": [{"paragraph": "Test narrative", "fact_ids": ["auto-1"]}],
    "unsupported_claim_warnings": [],
    "tone_notes": "Professional",
}


class TestNarrativeParsing:
    def test_parse_valid_narrative(self):
        result = _to_narrative(NarrativeDraft.model_validate(NARRATIVE))
        assert result.summary == "Test summary"
        assert result.full_narrative == "Test narrative paragraph."
        assert "employment_stability" in result.key_themes
        assert result.supporting_facts[0]["fact_id"] == "auto-1"
        assert len(result.unsupported_claim_warnings) == 0

    def test_empty_response_is_rejected(self):
        """A missing narrative is a schema failure, not a silently empty narrative."""
        with pytest.raises(ValidationError):
            NarrativeDraft.model_validate({})

    def test_abstention_is_labeled(self):
        result = _abstention_narrative()
        assert result.full_narrative == ""
        assert "no mitigation facts" in result.summary.lower()

    def test_no_invented_citations_in_parse(self):
        """Parsed narrative should not contain citation patterns not in input."""
        raw = {
            **NARRATIVE,
            "full_narrative": "The defendant is employed and has no prior record.",
            "supporting_facts": [],
            "paragraph_fact_map": [],
        }
        result = _to_narrative(NarrativeDraft.model_validate(raw))
        assert not re.search(r"O\.C\.G\.A\.\s*§", result.full_narrative)
