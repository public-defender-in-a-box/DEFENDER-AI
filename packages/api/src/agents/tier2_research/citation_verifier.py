"""Citation Verification Agent — Tier 2 Research.

Mechanical verification of all legal citations. Performs concrete, binary
verification tasks on every citation before it reaches the attorney.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.responses.stubs import CitationCheck
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "STUB"

# The naive single-prompt baseline (PHASE_1_MODEL_GATEWAY.md §9.5).
_PROMPT = load_prompt("citation_verifier.verify", "v1")
# The system prompt this call used as call_llm's default.
_SYSTEM = load_prompt("shared.json_assistant", "v1")
_MAX_TOKENS = 16000


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

        call = await call_model(
            ModelCallRequest(
                prompt=_PROMPT.text.format(
                    citations=citations,
                ),
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=CitationCheck,
                prompt_id=_PROMPT.id,
                prompt_version=compose_version(_SYSTEM, _PROMPT),
                agent_id=self.agent_id,
            )
        )
        result = call.data.model_dump(mode="json")

        self.log_action("citation_verification_completed")
        return self.wrap_output(result, confidence=0.5)
