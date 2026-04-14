"""Tests for LLM output parsing and validation."""

from __future__ import annotations


from ..nodes.leniency_argument_builder import _fallback_arguments, _parse_llm_response
from ..nodes.mitigation_narrative_builder import _fallback_narrative, _parse_narrative_response


class TestLeniencyArgumentParsing:
    def test_parse_valid_array(self):
        raw = [
            {
                "argument_type": "alternative_sentence",
                "basis": "Straight probation",
                "supporting_facts": ["Employed full-time"],
                "supporting_fact_ids": ["auto-1"],
                "strength": "strong",
                "applicable_authority": ["O.C.G.A. § 42-8-34"],
                "authority_verification_status": "confirmed",
                "notes": "Strong candidate for probation",
            }
        ]
        results = _parse_llm_response(raw)
        assert len(results) == 1
        assert results[0].basis == "Straight probation"
        assert results[0].strength == "strong"

    def test_parse_wrapped_response(self):
        raw = {
            "arguments": [
                {
                    "argument_type": "mitigating_factor",
                    "basis": "No prior record",
                    "supporting_facts": [],
                    "strength": "strong",
                }
            ]
        }
        results = _parse_llm_response(raw)
        assert len(results) == 1

    def test_parse_empty_returns_empty(self):
        assert _parse_llm_response([]) == []
        assert _parse_llm_response({}) == []

    def test_fallback_arguments_work(self):
        candidates = [
            {
                "argument_type": "alternative_sentence",
                "basis": "Fine-only",
                "applicable_authority": ["O.C.G.A. § 17-10-3"],
                "authority_verification_status": "confirmed",
            }
        ]
        results = _fallback_arguments(candidates)
        assert len(results) == 1
        assert "fallback" in results[0].notes.lower() or "without LLM" in results[0].notes


class TestNarrativeParsing:
    def test_parse_valid_narrative(self):
        raw = {
            "summary": "Test summary",
            "full_narrative": "Test narrative paragraph.",
            "key_themes": ["employment_stability"],
            "supporting_facts": [{"fact_id": "auto-1", "text": "Employed"}],
            "paragraph_fact_map": [{"paragraph": "Test narrative", "fact_ids": ["auto-1"]}],
            "unsupported_claim_warnings": [],
            "tone_notes": "Professional",
        }
        result = _parse_narrative_response(raw)
        assert result.summary == "Test summary"
        assert result.full_narrative == "Test narrative paragraph."
        assert "employment_stability" in result.key_themes
        assert len(result.unsupported_claim_warnings) == 0

    def test_parse_empty_narrative(self):
        raw = {}
        result = _parse_narrative_response(raw)
        assert result.summary == ""
        assert result.full_narrative == ""

    def test_fallback_narrative_has_warning(self):
        state = {
            "input": None,  # Not used in this path
            "mitigation_fact_sheet": {
                "facts": [
                    {"fact_id": "auto-1", "text": "Employed full-time"},
                    {"fact_id": "auto-2", "text": "Housing is stable"},
                ],
                "themes": ["employment_stability", "housing_stability"],
                "sensitive_categories": [],
                "fact_count": 2,
            },
        }
        result = _fallback_narrative(state)
        assert "fallback" in result.unsupported_claim_warnings[0].lower()
        assert "Employed full-time" in result.full_narrative

    def test_no_invented_citations_in_parse(self):
        """Parsed narrative should not contain citation patterns not in input."""
        raw = {
            "summary": "Summary",
            "full_narrative": "The defendant is employed and has no prior record.",
            "key_themes": ["employment_stability"],
            "supporting_facts": [],
            "paragraph_fact_map": [],
            "unsupported_claim_warnings": [],
            "tone_notes": "",
        }
        result = _parse_narrative_response(raw)
        # No Georgia statute citations should appear unless provided
        import re

        citation_pattern = r"O\.C\.G\.A\.\s*§"
        assert not re.search(citation_pattern, result.full_narrative)
