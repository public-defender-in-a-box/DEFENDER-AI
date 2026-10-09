"""Case Law Agent — Tier 2 Research.

Retrieves and analyzes judicial opinions. Searches verified corpus first,
open research second. All results tagged with verification status.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.responses.stubs import CaseLawResearch
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "STUB"

# The naive single-prompt baseline (PHASE_1_MODEL_GATEWAY.md §9.5).
_PROMPT = load_prompt("case_law_agent.research", "v1")
# The system prompt this call used as call_llm's default.
_SYSTEM = load_prompt("shared.json_assistant", "v1")
_MAX_TOKENS = 16000


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

        call = await call_model(
            ModelCallRequest(
                prompt=_PROMPT.text.format(
                    facts=facts,
                    legal_issues=legal_issues,
                    statutes=statutes,
                ),
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=CaseLawResearch,
                prompt_id=_PROMPT.id,
                prompt_version=compose_version(_SYSTEM, _PROMPT),
                agent_id=self.agent_id,
            )
        )
        result = call.data.model_dump(mode="json")

        self.log_action("case_law_research_completed")
        return self.wrap_output(result, confidence=0.6)
