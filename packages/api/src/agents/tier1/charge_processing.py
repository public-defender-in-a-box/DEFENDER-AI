"""Charge Processing Agent — Tier 1, Step Zero.

First agent activated. Parses charging documents before anything else runs.
Establishes the legal framework for the entire case.
"""

from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm


CHARGE_PROCESSING_PROMPT = """You are a legal document parsing agent for a public defender's office.

Analyze the following charging document and extract structured information.

Document type: {document_type}
Jurisdiction: {jurisdiction}

DOCUMENT TEXT:
{document_text}

Extract and return a JSON object with:
1. "charges": array of charges, each with:
   - charge_id (sequential, e.g., "charge_1")
   - statute_section (the statutory citation)
   - offense_title (name of the offense)
   - degree (e.g., "Class 4 Felony", "Class A Misdemeanor")
   - elements (array of elements the prosecution must prove)
   - penalty_range (minimum_months, maximum_months, fine_min, fine_max, mandatory_minimum, probation_eligible)
   - enhancements (array of enhancement objects with type, description, statute_section, additional_penalty)
   - procedural_requirements (array of strings)

2. "factual_allegations": array of allegations, each with:
   - id, allegation text, related_charge_ids, related_elements, date_of_allegation, location

3. "persons_of_interest": array with name, role (OFFICER/WITNESS/VICTIM/CO_DEFENDANT), badge_number, agency, details

4. "procedural_flags": array of procedural deadlines or requirements

5. "raw_document_summary": brief plain-language summary

Return valid JSON only."""


class ChargeProcessingAgent(BaseAgent):
    agent_id = "charge_processing"
    agent_name = "Charge Processing Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Parse charging documents into structured charge objects.

        Input: document_text, document_type, jurisdiction
        Output: ChargeProcessingOutput
        """
        self.log_action(
            "charge_processing_started",
            {
                "document_type": input_data.get("document_type"),
                "jurisdiction": input_data.get("jurisdiction"),
                "text_length": len(input_data.get("document_text", "")),
            },
        )

        prompt = CHARGE_PROCESSING_PROMPT.format(
            document_type=input_data.get("document_type", "COMPLAINT"),
            jurisdiction=input_data.get("jurisdiction", "IL"),
            document_text=input_data.get("document_text", ""),
        )

        result = await call_llm(prompt)

        self.log_action("charge_processing_completed")
        return self.wrap_output(result, confidence=0.8)
