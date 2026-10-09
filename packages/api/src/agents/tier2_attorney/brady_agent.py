"""Brady Compliance Agent — Tier 2 Attorney Prep.

Analyzes disclosed discovery against what should exist. Builds a map of the
expected evidence universe and identifies gaps the attorney should demand.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm

STATUS = "STUB"


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

        prompt = f"""You are a Brady compliance analyst for a public defender.

Cross-reference disclosed discovery against what should exist based on
the charges and client's account.

DISCLOSED DISCOVERY:
{discovery}

CHARGING DOCUMENT ALLEGATIONS:
{charges}

CLIENT'S ACCOUNT:
{facts}

OFFICERS INVOLVED:
{officers}

Return JSON with:
1. "gaps": array with id, category (MISSING_REPORT/MISSING_FORENSIC/GIGLIO/
   CI_FILE/INCONSISTENT_STATEMENT/OTHER), description, expected_evidence, basis
2. "giglio_checklist": array with officer, disciplinary_record_requested (bool), status
3. "draft_demand_letter": text of a targeted Brady demand letter

Focus on: missing reports, absent forensic evidence, officer disciplinary
records, CI indicators, prior inconsistent statements.

Return valid JSON only."""

        result = await call_llm(prompt)

        self.log_action("brady_analysis_completed")
        return self.wrap_output(result, confidence=0.7)
