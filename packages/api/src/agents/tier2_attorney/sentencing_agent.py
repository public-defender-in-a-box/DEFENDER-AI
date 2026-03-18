"""Sentencing & Mitigation Agent — Tier 2 Attorney Prep.

Calculates sentencing exposure and builds mitigation narrative. Activated both
pre-trial (for plea assessment) and post-conviction (for sentencing advocacy).
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm


class SentencingAgent(BaseAgent):
    agent_id = "sentencing_agent"
    agent_name = "Sentencing & Mitigation Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Calculate sentencing exposure and build mitigation narrative.

        Input: offense details, criminal history, personal circumstances
        Output: guideline range, departure arguments, mitigation narrative
        """
        self.log_action("sentencing_analysis_started")

        offense = input_data.get("offense_details", {})
        criminal_history = input_data.get("criminal_history", "")
        circumstances = input_data.get("personal_circumstances", {})
        jurisdiction = input_data.get("jurisdiction", "IL")

        prompt = f"""You are a sentencing and mitigation specialist for a public defender
in {jurisdiction}.

OFFENSE DETAILS:
{offense}

CRIMINAL HISTORY:
{criminal_history}

PERSONAL CIRCUMSTANCES:
{circumstances}

Return JSON with:
1. "guideline_range": minimum_months, maximum_months, offense_level,
   criminal_history_category
2. "departure_arguments": array with direction (DOWNWARD/UPWARD), basis, strength
3. "mitigation_narrative": draft narrative for sentencing
4. "alternatives": array with type, description, eligibility
   (probation, community service, treatment programs)
5. "comparable_sentences": array with case_summary, sentence, similarity
6. "memo_framework": outline for sentencing memorandum

Return valid JSON only."""

        result = await call_llm(prompt)

        self.log_action("sentencing_analysis_completed")
        return self.wrap_output(result, confidence=0.65)
