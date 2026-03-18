"""Statute Agent — Tier 2 Research.

Retrieves and analyzes statutory law. Operates primarily from the verified
closed corpus with open research fallback for recent amendments.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm


class StatuteAgent(BaseAgent):
    agent_id = "statute_agent"
    agent_name = "Statute Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Pull statutory elements, penalties, and related provisions.

        Input: statutory sections from Charge Processing, enhancement flags
        Output: elements breakdown, penalty ranges, diversion eligibility
        """
        self.log_action("statute_analysis_started")

        # TODO: Query closed corpus first, then fall back to LLM
        charges = input_data.get("charges", [])
        enhancements = input_data.get("enhancements", [])

        prompt = f"""You are a statute analysis agent for a public defender in Illinois.

Analyze the following charges and provide detailed statutory analysis.

CHARGES:
{charges}

ENHANCEMENT FLAGS:
{enhancements}

For each statute, provide JSON with:
1. "statutes": array with statute_section, full_text, elements_breakdown,
   related_statutes, sentencing_guidelines, mandatory_minimums,
   diversion_eligibility, verification_status
2. "procedural_statutes": relevant procedural requirements
3. "enhancement_statutes": applicable enhancement provisions

Return valid JSON only."""

        result = await call_llm(prompt)

        self.log_action("statute_analysis_completed")
        return self.wrap_output(result, confidence=0.75)
