"""Intake Conductor — Tier 1, Client-Facing.

Manages the client interview. Adapts to charge type, client demographics,
and accessibility needs. Trauma-informed, plain language, multilingual capable.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm


class IntakeConductorAgent(BaseAgent):
    agent_id = "intake_conductor"
    agent_name = "Intake Conductor"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate the next intake question based on conversation state.

        Input: pre_interview_brief, conversation_history, client_response
        Output: next question or intake summary
        """
        self.log_action("intake_message_processing")

        brief = input_data.get("pre_interview_brief", {})
        history = input_data.get("conversation_history", [])
        client_response = input_data.get("client_response", "")

        prompt = f"""You are an intake conductor for a public defender's office.
You are conducting a client interview. Be trauma-informed, use plain language,
and adapt pacing to the client's needs.

IMPORTANT: You INFORM the client, you do NOT give legal advice.
Include this disclaimer if discussing anything about the case.

PRE-INTERVIEW BRIEF:
{brief}

CONVERSATION SO FAR:
{history}

CLIENT'S LATEST RESPONSE:
{client_response}

Generate the next appropriate question or response. Return JSON:
{{
  "response": "your response to the client",
  "generated_by": "INTAKE_CONDUCTOR",
  "target_element": "what this question aims to establish",
  "should_route_to": null or "FACT_GATHERER" or "RIGHTS_SCANNER" or "COLLATERAL_AGENT" or "PERSONAL_CIRCUMSTANCES",
  "intake_complete": false
}}

Return valid JSON only."""

        result = await call_llm(prompt)

        self.log_action("intake_message_generated")
        return result
