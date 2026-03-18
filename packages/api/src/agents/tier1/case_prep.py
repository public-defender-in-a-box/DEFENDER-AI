"""Case Prep Conductor — Tier 1, Attorney-Facing.

Receives processed intake and all research outputs. Orchestrates the
attorney-side specialist agents and compiles the final case preparation package.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm


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

        prompt = f"""You are a case preparation conductor for a public defender's office.

Synthesize all available information into a comprehensive case preparation memo.

CASE STATE:
{case_state}

Generate a JSON object with:
1. "case_theory": recommended defense theory based on all evidence
2. "preparation_memo": full case preparation memo text
3. "decision_points": array of points requiring attorney judgment, each with:
   - id, description, options, recommendation, human_required (boolean)
4. "attorney_task_list": array of tasks, each with:
   - id, task, priority (URGENT/HIGH/MEDIUM/LOW), deadline, category

Mark all recommendations as requiring human judgment.
Return valid JSON only."""

        result = await call_llm(prompt)

        self.log_action("case_prep_completed")
        return self.wrap_output(result, confidence=0.7)
