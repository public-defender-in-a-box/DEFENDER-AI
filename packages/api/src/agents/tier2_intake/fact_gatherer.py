"""Fact Gathering Agent — Tier 2 Intake Specialist.

Conducts the core factual interview. Questions are dynamically generated
based on charge elements.

NOTE: For MVP, this is integrated into the Intake Conductor rather than
operating as a separate conversational agent.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm


class FactGathererAgent(BaseAgent):
    agent_id = "fact_gatherer"
    agent_name = "Fact Gathering Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate fact-gathering questions based on charge elements.

        Input: targeted question list, charge elements
        Output: structured fact timeline, witness roster, evidence inventory
        """
        self.log_action("fact_gathering_started")

        questions = input_data.get("targeted_questions", [])
        client_responses = input_data.get("client_responses", {})

        prompt = f"""You are a fact-gathering specialist for a public defender.

Extract structured facts from the client's responses.

TARGETED QUESTIONS:
{questions}

CLIENT RESPONSES:
{client_responses}

Return JSON with:
1. "timeline": chronological events with timestamp, event, source, confidence
2. "witnesses": name, contact_info, relationship, observed_events
3. "evidence_inventory": description, type, location, preservation_status
4. "scene_description": description of the scene

Return valid JSON only."""

        result = await call_llm(prompt)

        self.log_action("fact_gathering_completed")
        return self.wrap_output(result, confidence=0.7)
