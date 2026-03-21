"""Pre-Interview Research Conductor — Tier 1.

Activated after charge processing, before client interview. Builds the legal
foundation so the intake is informed and targeted rather than starting blind.

Depends on: Charge Processing output
Produces: targeted question list, preliminary rights flags, known facts,
          legal brief, and sub-agent research requests
"""

import json
import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm

logger = logging.getLogger(__name__)


_SYSTEM_PROMPT = (
    "You are a pre-interview research conductor for a public defender's office "
    "in Georgia. Your job is to analyze charge processing output and build a "
    "comprehensive brief that will inform the client intake interview.\n\n"
    "JURISDICTION KNOWLEDGE:\n"
    "- Georgia State: O.C.G.A. Title 16 (Crimes), Title 17 (Criminal Procedure)\n"
    "- Georgia First Offender Act: O.C.G.A. \u00a7 42-8-60\n"
    "- Georgia recidivist statute: O.C.G.A. \u00a7 17-10-7\n"
    "- Federal: Title 18 U.S.C., USSG, Speedy Trial Act\n"
    "- Brady v. Maryland / Giglio v. United States\n\n"
    "PRINCIPLES:\n"
    "1. You prepare the defense team — you do NOT advise the client directly.\n"
    "2. Flag every potential rights violation for investigation.\n"
    "3. Identify every element the prosecution must prove and craft questions "
    "that probe those elements.\n"
    "4. Note collateral consequence risks early so intake can gather relevant info.\n"
    "5. Assign confidence scores (0.0-1.0) to all assessments.\n\n"
    "OUTPUT FORMAT: Always respond with valid JSON."
)

_PRE_INTERVIEW_PROMPT = """Based on the following charge processing output, prepare a comprehensive pre-interview research brief.

CHARGE PROCESSING OUTPUT:
{charge_data}

Generate a JSON object with:

{{
  "charges_summary": "Plain-language summary of all charges, degrees, and potential penalties for the attorney",

  "targeted_questions": [
    {{
      "question_id": "TQ-001",
      "question": "The question to ask during intake",
      "relevant_charge_id": "charge_1",
      "relevant_element": "What element of the charge this probes",
      "priority": "MUST_ASK | SHOULD_ASK | IF_TIME",
      "rationale": "Why this question matters for the defense",
      "phase": "personal_information | incident_narrative | arrest_and_custody | prior_history | priorities_and_concerns"
    }}
  ],

  "preliminary_rights_flags": [
    {{
      "flag_id": "RF-001",
      "type": "fourth_amendment | fifth_amendment | sixth_amendment | fourteenth_amendment | speedy_trial | brady | other",
      "description": "What potential violation was identified from the documents",
      "basis": "Specific facts from the charge processing output that suggest this",
      "investigation_needed": "What the intake should probe to confirm or deny this flag",
      "severity": "high | medium | low",
      "confidence": 0.0-1.0
    }}
  ],

  "known_facts_from_documents": [
    {{
      "fact_id": "KF-001",
      "fact": "A fact established from the charging documents",
      "source": "Which document/page this comes from",
      "category": "timeline | location | persons | evidence | procedure | statements",
      "verify_with_client": true/false,
      "verification_question": "Question to ask client to verify this fact (if applicable)",
      "confidence": 0.0-1.0
    }}
  ],

  "collateral_consequence_alerts": [
    {{
      "alert_id": "CC-001",
      "category": "immigration | employment | housing | family | financial | professional_license",
      "description": "What collateral consequence risk exists based on these charges",
      "relevant_charge": "charge_1",
      "intake_question": "What to ask the client to assess this risk",
      "severity": "high | medium | low"
    }}
  ],

  "legal_brief": {{
    "key_legal_issues": ["List of key legal issues identified from the charges"],
    "elements_to_prove": [
      {{
        "charge_id": "charge_1",
        "offense": "Name of offense",
        "elements": ["Element 1", "Element 2"],
        "weakest_element": "Which element appears hardest for prosecution to prove and why"
      }}
    ],
    "potential_defenses": ["Defenses suggested by the charging documents alone"],
    "diversion_eligibility": {{
      "first_offender_act": "Assessment based on charges",
      "pretrial_diversion": "Assessment",
      "drug_court": "Assessment if applicable",
      "notes": "Any qualifying or disqualifying factors"
    }},
    "procedural_deadlines": ["Any deadlines identified from the charges"],
    "research_requests": [
      {{
        "request_id": "RR-001",
        "type": "statute_lookup | case_law | sentencing_data | local_practice",
        "description": "What research the statute/case-law agents should do",
        "priority": "high | medium | low",
        "relevant_charge": "charge_1"
      }}
    ]
  }}
}}

IMPORTANT:
- Generate MUST_ASK questions for every element the prosecution must prove
- Flag any Miranda, search/seizure, or right-to-counsel issues from the arrest narrative
- Identify collateral consequences BEFORE intake so the right questions get asked
- Include research requests for any statutory ambiguities or novel legal issues
- Note facts that should be verified with the client (discrepancies are defense gold)"""


class PreInterviewResearchAgent(BaseAgent):
    agent_id = "pre_interview_research"
    agent_name = "Pre-Interview Research Conductor"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Build a pre-interview brief from charge processing output.

        Input keys:
            charge_processing: dict — ConfidenceRated output from Charge Processing

        Output: ConfidenceRated dict with targeted questions, rights flags,
            known facts, collateral alerts, and legal brief.
        """
        self.log_action("pre_interview_research_started")

        charge_processing = input_data.get("charge_processing", {})
        # Unwrap ConfidenceRated if needed
        if "data" in charge_processing and "confidence" in charge_processing:
            charge_data = charge_processing["data"]
        else:
            charge_data = charge_processing

        charge_str = json.dumps(charge_data, indent=2, default=str)
        if len(charge_str) > 80_000:
            charge_str = charge_str[:80_000] + "\n... [TRUNCATED]"

        prompt = _PRE_INTERVIEW_PROMPT.format(charge_data=charge_str)

        try:
            result = await call_llm(prompt, system=_SYSTEM_PROMPT, max_tokens=8192)
        except Exception:
            logger.exception("Pre-interview research generation failed")
            result = {
                "charges_summary": "Error generating summary — review charge processing output directly.",
                "targeted_questions": [],
                "preliminary_rights_flags": [],
                "known_facts_from_documents": [],
                "collateral_consequence_alerts": [],
                "legal_brief": {
                    "key_legal_issues": [],
                    "elements_to_prove": [],
                    "potential_defenses": [],
                    "diversion_eligibility": {},
                    "procedural_deadlines": [],
                    "research_requests": [],
                },
            }

        # Compute confidence from the quality of charge processing input
        # and the completeness of the generated brief
        confidence = self._compute_confidence(charge_data, result)

        self.log_action(
            "pre_interview_research_completed",
            {
                "targeted_questions": len(result.get("targeted_questions", [])),
                "rights_flags": len(result.get("preliminary_rights_flags", [])),
                "known_facts": len(result.get("known_facts_from_documents", [])),
                "collateral_alerts": len(result.get("collateral_consequence_alerts", [])),
                "overall_confidence": confidence,
            },
        )

        return self.wrap_output(result, confidence=confidence)

    def _compute_confidence(
        self,
        charge_data: dict[str, Any],
        result: dict[str, Any],
    ) -> float:
        """Derive confidence from input quality and output completeness."""
        score = 0.5  # baseline

        # Input quality: charges present and extracted
        charges = charge_data.get("charges", [])
        if charges:
            score += 0.15
            # Check if elements were extracted
            if any(c.get("elements") for c in charges):
                score += 0.05

        # Defendant identified
        defendant = charge_data.get("defendant", {})
        if defendant.get("name") and defendant["name"] != "UNKNOWN":
            score += 0.05

        # Output completeness
        if result.get("targeted_questions"):
            score += 0.05
        if result.get("preliminary_rights_flags"):
            score += 0.05
        if result.get("known_facts_from_documents"):
            score += 0.05
        if result.get("legal_brief", {}).get("elements_to_prove"):
            score += 0.05
        if result.get("collateral_consequence_alerts"):
            score += 0.05

        return min(round(score, 3), 0.95)
