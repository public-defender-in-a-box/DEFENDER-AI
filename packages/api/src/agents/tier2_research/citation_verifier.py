"""Citation Verification Agent — Tier 2 Research.

Mechanical verification of all legal citations. Performs concrete, binary
verification tasks on every citation before it reaches the attorney.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm

STATUS = "STUB"


class CitationVerifierAgent(BaseAgent):
    agent_id = "citation_verifier"
    agent_name = "Citation Verification Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Verify all citations from Case Law and Statute agents.

        Input: citations to verify
        Output: verification status per citation, Shepard's signals
        """
        self.log_action("citation_verification_started")

        citations = input_data.get("citations", [])

        # TODO: Implement actual verification against legal databases
        # For MVP, use LLM to flag obviously problematic citations

        prompt = f"""You are a citation verification agent.

Verify the following legal citations. For each, determine:
- Does this case/statute likely exist?
- Is the citation format correct?
- Any known issues (overruled, superseded)?

CITATIONS TO VERIFY:
{citations}

Return JSON with:
1. "verified_citations": array with citation, status (CONFIRMED/UNCONFIRMED/OVERRULED/SUPERSEDED),
   shepard_signal, notes
2. "statute_alerts": any amendment alerts

IMPORTANT: When in doubt, mark as UNCONFIRMED rather than CONFIRMED.
Return valid JSON only."""

        result = await call_llm(prompt)

        self.log_action("citation_verification_completed")
        return self.wrap_output(result, confidence=0.5)
