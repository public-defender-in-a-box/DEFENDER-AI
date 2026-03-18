"""Pre-Interview Research Conductor — Tier 1.

Activated after charge processing, before client interview. Builds the legal
foundation so the intake is informed and targeted rather than starting blind.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm


class PreInterviewResearchAgent(BaseAgent):
    agent_id = "pre_interview_research"
    agent_name = "Pre-Interview Research Conductor"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Build pre-interview brief from charge processing output.

        Input: charge_processing output
        Output: targeted question list, preliminary rights flags, legal brief
        """
        self.log_action("pre_interview_research_started")

        charges = input_data.get("charge_processing", {})

        prompt = f"""You are a pre-interview research conductor for a public defender's office.

Based on the following charge processing output, prepare a pre-interview brief.

CHARGES DATA:
{charges}

Generate a JSON object with:
1. "charges_summary": plain-language summary of all charges
2. "targeted_questions": array of questions to ask during client intake, each with:
   - question, relevant_charge_id, relevant_element, priority (MUST_ASK/SHOULD_ASK/IF_TIME)
3. "preliminary_rights_flags": array of potential rights violations to investigate
4. "known_facts_from_documents": array of facts already established from documents
5. "legal_brief": summary of key legal issues

Return valid JSON only."""

        result = await call_llm(prompt)

        self.log_action("pre_interview_research_completed")
        return self.wrap_output(result, confidence=0.75)
