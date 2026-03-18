"""Motion Drafter Agent — Tier 2 Attorney Prep.

Generates preliminary motion drafts based on intake facts and legal research.
Drafts are 70% complete — attorney reviews, edits, and files.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm


class MotionDrafterAgent(BaseAgent):
    agent_id = "motion_drafter"
    agent_name = "Motion Drafter Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate draft motions based on case analysis.

        Input: rights violations, case law, statutes, intake facts
        Output: draft motions marked DRAFT — ATTORNEY REVIEW REQUIRED
        """
        self.log_action("motion_drafting_started")

        rights = input_data.get("rights_violations", {})
        case_law = input_data.get("case_law", {})
        statutes = input_data.get("statutes", {})
        facts = input_data.get("intake_facts", {})
        jurisdiction = input_data.get("jurisdiction", "IL")

        prompt = f"""You are a motion drafting agent for a public defender in {jurisdiction}.

Based on the case analysis, draft applicable motions.

RIGHTS VIOLATION ANALYSIS:
{rights}

VERIFIED CASE LAW:
{case_law}

STATUTORY FRAMEWORK:
{statutes}

INTAKE FACTS:
{facts}

For each applicable motion, generate JSON with:
"motions": array with:
  - id, type (SUPPRESS/DISMISS/BAIL_REDUCTION/DISCOVERY/LIMINE/OTHER)
  - title, draft (full motion text with jurisdiction formatting)
  - status: "DRAFT"
  - filing_deadline (if calculable)
  - supporting_authority (array of citations)

CRITICAL: All drafts MUST include the header "DRAFT — ATTORNEY REVIEW REQUIRED"
Use only VERIFIED citations where possible. Tag UNVERIFIED ones clearly.

Return valid JSON only."""

        result = await call_llm(prompt)

        self.log_action("motion_drafting_completed")
        return self.wrap_output(result, confidence=0.65)
