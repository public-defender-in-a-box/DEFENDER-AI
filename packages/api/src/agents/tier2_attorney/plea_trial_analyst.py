"""Plea / Trial Assessment Agent — Tier 2 Attorney Prep.

Structured decision-support tool for the plea vs. trial calculus.
ALL outputs marked: DECISION SUPPORT ONLY — ATTORNEY AND CLIENT DECIDE.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm


class PleaTrialAnalystAgent(BaseAgent):
    agent_id = "plea_trial_analyst"
    agent_name = "Plea / Trial Assessment Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate structured plea vs. trial comparison.

        Input: plea offer, sentencing guidelines, attorney assessments,
               collateral consequences, suppression viability
        Output: comparison matrix, risk factors — DECISION SUPPORT ONLY
        """
        self.log_action("plea_trial_analysis_started")

        plea_offer = input_data.get("plea_offer", {})
        sentencing = input_data.get("sentencing_guidelines", {})
        collateral = input_data.get("collateral_consequences", {})
        suppression = input_data.get("suppression_viability", {})

        prompt = f"""You are a plea/trial assessment agent for a public defender.

CRITICAL: ALL outputs must be prefixed with "DECISION SUPPORT ONLY —
ATTORNEY AND CLIENT DECIDE". This is decision support, not a recommendation.

PLEA OFFER:
{plea_offer}

SENTENCING GUIDELINES:
{sentencing}

COLLATERAL CONSEQUENCES:
{collateral}

SUPPRESSION MOTION VIABILITY:
{suppression}

Return JSON with:
1. "plea_scenario": charges, sentencing_range, collateral_consequences
2. "trial_scenario": charges, acquittal_probability, sentencing_if_convicted,
   collateral_consequences
3. "comparison_matrix": side-by-side comparison of key factors
4. "risk_factors": array of risk considerations
5. "recommendation": MUST start with "DECISION SUPPORT ONLY — "

Return valid JSON only."""

        result = await call_llm(prompt)

        self.log_action("plea_trial_analysis_completed")
        return self.wrap_output(result, confidence=0.6)
