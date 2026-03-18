"""Case Orchestrator — Tier 0 Master Agent.

Central conductor. Receives case assignment, maintains global case state,
manages sequencing and handoffs between all branches.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.case_state import CaseState, PipelineStage


class OrchestratorAgent(BaseAgent):
    agent_id = "orchestrator"
    agent_name = "Case Orchestrator"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Initialize a case and manage the pipeline.

        Input: charging documents + attorney config
        Output: initialized CaseState
        """
        self.log_action("case_initialized", {"input_keys": list(input_data.keys())})

        case_state = CaseState(
            id=input_data.get("case_id", ""),
            attorney_id=input_data.get("attorney_id", ""),
            jurisdiction=input_data.get("jurisdiction", "IL"),
            attorney_config=input_data.get("attorney_config", {}),
        )
        case_state.advance_stage(PipelineStage.CREATED)

        return case_state.model_dump(mode="json")
