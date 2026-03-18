"""Case Law Agent — Tier 2 Research.

Retrieves and analyzes judicial opinions. Searches verified corpus first,
open research second. All results tagged with verification status.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm


class CaseLawAgent(BaseAgent):
    agent_id = "case_law_agent"
    agent_name = "Case Law Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Find controlling authority for each legal issue.

        Input: legal issues, factual pattern, statutory framework
        Output: controlling authority with verification tags
        """
        self.log_action("case_law_research_started")

        # TODO: Search closed corpus before using LLM
        legal_issues = input_data.get("legal_issues", [])
        facts = input_data.get("factual_pattern", "")
        statutes = input_data.get("statutory_framework", [])

        prompt = f"""You are a case law research agent for a public defender in Illinois.

IMPORTANT: Tag ALL citations with verification status.
Corpus citations = VERIFIED. Generated citations = UNVERIFIED.
Surface BOTH favorable and unfavorable precedent honestly.

LEGAL ISSUES:
{legal_issues}

FACTUAL PATTERN:
{facts}

STATUTORY FRAMEWORK:
{statutes}

Return JSON with:
1. "authorities": array with case_name, citation, court, year, holding,
   relevance, favorable (bool), factual_similarity, verification_status,
   distinguishing_factors
2. "circuit_splits": any conflicting authority
3. "recommended_citations": best citations for motions

Return valid JSON only."""

        result = await call_llm(prompt)

        self.log_action("case_law_research_completed")
        return self.wrap_output(result, confidence=0.6)
