"""Rights Violation Scanner — Tier 2 Intake Specialist.

Identifies potential constitutional violations from both the arrest report
(pre-interview) and the client's narrative (during interview). Two-pass system.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm


class RightsScannerAgent(BaseAgent):
    agent_id = "rights_scanner"
    agent_name = "Rights Violation Scanner"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Scan for constitutional violations in arrest/client narrative.

        Input: arrest report and/or client narrative
        Output: rights violation flags, discrepancy report, suppression viability
        """
        self.log_action("rights_scan_started", {
            "pass": input_data.get("pass_number", 1),
        })

        arrest_report = input_data.get("arrest_report", "")
        client_narrative = input_data.get("client_narrative", "")
        officer_conduct = input_data.get("officer_conduct", "")

        prompt = f"""You are a constitutional rights violation scanner for a public defender.

Analyze the following for potential 4th, 5th, 6th, and 14th Amendment violations.

ARREST REPORT:
{arrest_report}

CLIENT NARRATIVE:
{client_narrative}

OFFICER CONDUCT DETAILS:
{officer_conduct}

Return JSON with:
1. "violations": array with id, amendment (4TH/5TH/6TH/14TH), category,
   description, confidence, supporting_facts
2. "discrepancy_report": array comparing officer vs client account with
   topic, officer_account, client_account, significance
3. "suppression_viability": score (0-100), confidence, basis, risks

Key areas to check:
- 4th: warrant, probable cause, consent, search scope
- 5th: Miranda, voluntariness, custodial interrogation
- 6th: right to counsel, lineup procedures
- 14th: selective prosecution, discriminatory enforcement

Return valid JSON only."""

        result = await call_llm(prompt)

        self.log_action("rights_scan_completed")
        return self.wrap_output(result, confidence=0.7)
