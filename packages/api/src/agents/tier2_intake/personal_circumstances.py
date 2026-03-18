"""Personal Circumstances Agent — Tier 2 Intake Specialist.

Gathers information relevant to bail, sentencing mitigation, and diversion
eligibility. Not about the facts of the case — about the person.

NOTE: For MVP, this operates as a structured form rather than a full
conversational agent.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm


class PersonalCircumstancesAgent(BaseAgent):
    agent_id = "personal_circumstances"
    agent_name = "Personal Circumstances Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze personal circumstances for bail, mitigation, diversion.

        Input: client personal background responses
        Output: bail profile, mitigation narrative, diversion eligibility
        """
        self.log_action("personal_circumstances_started")

        background = input_data.get("client_background", {})

        prompt = f"""You are a personal circumstances analyst for a public defender.

Based on the client's background, assess bail arguments, mitigation potential,
and diversion eligibility.

CLIENT BACKGROUND:
{background}

Return JSON with:
1. "bail_profile": community_ties (array), flight_risk_factors (array), recommendation
2. "mitigation_narrative": draft narrative for sentencing purposes
3. "diversion_eligibility": array with program, eligible (bool), basis
4. "treatment_needs": array of identified treatment needs

Return valid JSON only."""

        result = await call_llm(prompt)

        self.log_action("personal_circumstances_completed")
        return self.wrap_output(result, confidence=0.8)
