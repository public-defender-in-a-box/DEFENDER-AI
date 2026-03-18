"""Collateral Consequences Agent — Tier 2 Intake Specialist.

Identifies non-criminal consequences of conviction. Often more important to
the client than the sentence itself. Critical for plea negotiations.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm


class CollateralConsequencesAgent(BaseAgent):
    agent_id = "collateral_agent"
    agent_name = "Collateral Consequences Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Identify collateral consequences based on charges and circumstances.

        Input: charged offenses, client personal circumstances
        Output: consequences inventory, plea strategy impact, Padilla flag
        """
        self.log_action("collateral_analysis_started")

        charges = input_data.get("charges", [])
        circumstances = input_data.get("personal_circumstances", {})

        prompt = f"""You are a collateral consequences specialist for a public defender.

Analyze the following charges for non-criminal consequences of conviction.
This analysis is critical for plea negotiations.

CHARGES:
{charges}

CLIENT CIRCUMSTANCES:
{circumstances}

Return JSON with:
1. "consequences": array with category (IMMIGRATION/EMPLOYMENT/HOUSING/
   EDUCATION/FAMILY/CIVIL_RIGHTS), description, severity (SEVERE/MODERATE/MINOR),
   charge_specific (bool), affects_plea_strategy (bool)
2. "padilla_flag": true if client is non-citizen (Padilla v. Kentucky obligation)
3. "plea_strategy_impact": how consequences should influence plea negotiations

Check: immigration, employment/licensing, housing, education/financial aid,
family/custody, firearm rights, voting rights, sex offender registration.

Return valid JSON only."""

        result = await call_llm(prompt)

        self.log_action("collateral_analysis_completed")
        return self.wrap_output(result, confidence=0.75)
