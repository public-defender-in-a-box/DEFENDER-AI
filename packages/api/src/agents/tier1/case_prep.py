"""Case Prep Conductor — Tier 1, Attorney-Facing.

Receives processed intake and all research outputs. Orchestrates the
attorney-side specialist agents and compiles the final case preparation package.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.responses.stubs import CasePrepMemo
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "STUB"

# The naive single-prompt baseline (PHASE_1_MODEL_GATEWAY.md §9.5).
_PROMPT = load_prompt("case_prep_conductor.memo", "v1")
# The system prompt this call used as call_llm's default.
_SYSTEM = load_prompt("shared.json_assistant", "v1")
_MAX_TOKENS = 16000


class CasePrepAgent(BaseAgent):
    agent_id = "case_prep_conductor"
    agent_name = "Case Prep Conductor"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Synthesize all agent outputs into case preparation memo.

        Input: full case_state with all prior agent outputs
        Output: case prep memo, decision points, attorney task list
        """
        self.log_action("case_prep_started")

        case_state = input_data.get("case_state", {})

        call = await call_model(
            ModelCallRequest(
                prompt=_PROMPT.text.format(
                    case_state=case_state,
                ),
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=CasePrepMemo,
                prompt_id=_PROMPT.id,
                prompt_version=compose_version(_SYSTEM, _PROMPT),
                agent_id=self.agent_id,
            )
        )
        result = call.data.model_dump(mode="json")

        self.log_action("case_prep_completed")
        return self.wrap_output(result, confidence=0.7)
