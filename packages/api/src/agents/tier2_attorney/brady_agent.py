"""Brady Compliance Agent — Tier 2 Attorney Prep.

Analyzes disclosed discovery against what should exist. Builds a map of the
expected evidence universe and identifies gaps the attorney should demand.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.motions import BradyAnalysisOutput
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "STUB"

# The naive single-prompt baseline (PHASE_1_MODEL_GATEWAY.md §9.5).
_PROMPT = load_prompt("brady_agent.analysis", "v1")
# The system prompt this call used as call_llm's default.
_SYSTEM = load_prompt("shared.json_assistant", "v1")
_MAX_TOKENS = 16000


class BradyComplianceAgent(BaseAgent):
    agent_id = "brady_agent"
    agent_name = "Brady Compliance Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Identify Brady/Giglio gaps in disclosed discovery.

        Input: discovery package, charging docs, intake facts, officer roster
        Output: gap analysis, Giglio checklist, draft demand letter
        """
        self.log_action("brady_analysis_started")

        discovery = input_data.get("discovery", "")
        charges = input_data.get("charging_allegations", "")
        facts = input_data.get("intake_facts", "")
        officers = input_data.get("officer_roster", [])

        call = await call_model(
            ModelCallRequest(
                prompt=_PROMPT.text.format(
                    charges=charges,
                    discovery=discovery,
                    facts=facts,
                    officers=officers,
                ),
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=BradyAnalysisOutput,
                prompt_id=_PROMPT.id,
                prompt_version=compose_version(_SYSTEM, _PROMPT),
                agent_id=self.agent_id,
            )
        )
        result = call.data.model_dump(mode="json")

        self.log_action("brady_analysis_completed")
        return self.wrap_output(result, confidence=0.7)
