"""Statute Agent — Tier 2 Research.

Retrieves and analyzes statutory law. Operates primarily from the verified
closed corpus with open research fallback for recent amendments.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.responses.stubs import StatuteResearch
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "STUB"

# The naive single-prompt baseline (PHASE_1_MODEL_GATEWAY.md §9.5).
_PROMPT = load_prompt("statute_agent.analysis", "v1")
# The system prompt this call used as call_llm's default.
_SYSTEM = load_prompt("shared.json_assistant", "v1")
_MAX_TOKENS = 16000


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

        call = await call_model(
            ModelCallRequest(
                prompt=_PROMPT.text.format(
                    charges=charges,
                    enhancements=enhancements,
                ),
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=StatuteResearch,
                prompt_id=_PROMPT.id,
                prompt_version=compose_version(_SYSTEM, _PROMPT),
                agent_id=self.agent_id,
            )
        )
        result = call.data.model_dump(mode="json")

        self.log_action("statute_analysis_completed")
        return self.wrap_output(result, confidence=0.75)
