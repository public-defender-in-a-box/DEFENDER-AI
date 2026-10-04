"""GA Criminal Statutes Agent — Tier 2 Research.

Retrieves and analyzes the full statutory framework relevant to the charges:
charged statutes, elements, penalties, lesser included offenses, diversion
eligibility, and procedural requirements.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.llm_service import call_llm

STATUS = "REAL"

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a Georgia criminal statutes specialist working for a public \
defender's office. You have comprehensive knowledge of the Official Code \
of Georgia Annotated (O.C.G.A.), particularly:

- Title 16: Crimes and Offenses
- Title 17: Criminal Procedure
- Title 42: Penal Institutions (including First Offender Act)

Your job is to provide the COMPLETE statutory framework for each charged \
offense, including the actual statutory text, element breakdowns, penalty \
ranges, lesser included offenses, diversion options, and procedural deadlines.

PRINCIPLES:
1. Provide the ACTUAL TEXT of statutes, not just summaries.
2. Break down elements with precision — the attorney needs to know exactly \
what the prosecution must prove.
3. Always check for diversion eligibility — First Offender Act, conditional \
discharge, pretrial diversion, drug court.
4. Include procedural deadlines — speedy trial, discovery, preliminary hearing.
5. Flag any recent amendments that might affect the case.
6. Be specific about penalty ranges including mandatory minimums.

OUTPUT FORMAT: Always respond with valid JSON."""

_STATUTORY_ANALYSIS_PROMPT = """\
Provide a comprehensive statutory analysis for the following Georgia criminal \
charges.

CHARGED OFFENSES:
{charges}

ENHANCEMENT FLAGS:
{enhancements}

DEFENDANT BACKGROUND (if known):
{defendant_info}

For EACH charged offense, provide:

1. STATUTE TEXT: The full text of the relevant subsection of the charged statute
2. ELEMENTS: Each element the prosecution must prove, with:
   - What the element requires
   - How the charging documents support (or fail to support) this element
3. LESSER INCLUDED OFFENSES: All applicable lesser included offenses with \
statute sections
4. PENALTIES: Full penalty range including:
   - Imprisonment range (min-max)
   - Fine range
   - Any mandatory minimums
   - Probation eligibility
5. SENTENCING ENHANCEMENTS: Any applicable enhancements based on the flags

Return JSON:
{{
  "charged_offenses": [
    {{
      "statute": "OCGA 16-13-30(j)(1)",
      "title": "Possession of Controlled Substance",
      "full_text": "It is unlawful for any person to purchase, possess, or \
have under his or her control any controlled substance...",
      "elements": [
        {{
          "element": "Possession (actual or constructive)",
          "definition": "The defendant knowingly had direct physical control \
over the substance or had the power and intention to exercise control",
          "document_support": "Officers found 4 Xanax tablets in defendant's \
jacket pocket"
        }}
      ],
      "lesser_included": [
        "OCGA 16-13-32(a) — Possession of marijuana less than 1 oz (if applicable)"
      ],
      "penalties": {{
        "imprisonment_range": "1 to 3 years (felony) or up to 12 months \
(misdemeanor if court exercises discretion under 16-13-2)",
        "fine_range": "Up to $5,000",
        "mandatory_minimum": "none for first offense possession",
        "probation_eligible": true
      }}
    }}
  ]
}}"""

_DIVERSION_ANALYSIS_PROMPT = """\
Analyze diversion and alternative sentencing eligibility for this defendant.

CHARGES:
{charges}

DEFENDANT BACKGROUND:
{defendant_info}

JURISDICTION: Georgia

Analyze eligibility for EACH of the following programs:

1. Georgia First Offender Act (OCGA 42-8-60 et seq.)
   - Eligibility requirements
   - Benefits (no conviction on record if completed)
   - Risks (full sentence if revoked)

2. Conditional Discharge for First Drug Offense (OCGA 16-13-2)
   - Only for first-time drug offenders
   - Discharge and dismissal upon completion

3. Pretrial Diversion Programs
   - County-specific availability
   - General eligibility criteria

4. Drug Court (OCGA 15-1-15)
   - Eligibility for drug-related charges
   - Program requirements

5. Probation under OCGA 42-8-34
   - Standard probation terms
   - Special conditions for drug offenses

For each program, assess:
- Whether the defendant is likely eligible based on what we know
- What additional information we need to determine eligibility
- The specific benefits and risks

Return JSON:
{{
  "diversion_options": [
    {{
      "program": "First Offender Act",
      "statute": "OCGA 42-8-60",
      "eligibility_requirements": "Never been convicted of a felony; \
never previously sentenced under First Offender",
      "client_eligible": "likely|unlikely|unknown",
      "eligibility_notes": "Based on available info...",
      "benefits": "No conviction on record if probation completed successfully",
      "risks": "If revoked, judge can impose maximum sentence for original charge"
    }}
  ]
}}"""

_PROCEDURAL_PROMPT = """\
Identify all procedural requirements and deadlines for this Georgia criminal case.

CHARGES:
{charges}

CASE STATUS: Pre-trial

Identify:

1. Speedy Trial:
   - OCGA 17-7-170 (demand for trial in superior court)
   - OCGA 17-7-171 (demand for trial in state court)
   - Applicable deadlines and consequences

2. Discovery:
   - OCGA 17-16-1 et seq.
   - Prosecution's disclosure obligations
   - Defense reciprocal obligations
   - Timeline requirements

3. Preliminary Hearing:
   - Right to preliminary hearing
   - Waiver implications

4. Motions Deadlines:
   - Typical pretrial motions deadline
   - Motion to suppress timing
   - Jackson-Denno hearing requirements

5. Statute of Limitations:
   - Applicable limitations period for each charge

Return JSON:
{{
  "procedural_requirements": [
    {{
      "requirement": "Speedy trial demand",
      "statute": "OCGA 17-7-170",
      "deadline": "Must be filed at arraignment or first appearance; \
trial within next term of court",
      "notes": "If not tried within the term after demand, case must be dismissed"
    }}
  ],
  "recent_amendments": ["Any recent changes to relevant statutes"]
}}"""


class GAStatutesAgent(BaseAgent):
    """Retrieves and analyzes the full statutory framework for charged offenses."""

    agent_id = "ga_statutes_agent"
    agent_name = "GA Criminal Statutes Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze all relevant statutes for the case.

        Input keys:
            charges: list of parsed charge dicts (from Charge Processing)
            enhancements: list of enhancement flag dicts
            defendant_info: dict with any known defendant background

        Output: GAStatutesOutput as dict
        """
        self.log_action("statutes_analysis_started")

        charges = input_data.get("charges", [])
        enhancements = input_data.get("enhancements", [])
        defendant_info = input_data.get("defendant_info", {})

        charges_json = json.dumps(charges, default=str)
        enhancements_json = json.dumps(enhancements, default=str)
        defendant_json = json.dumps(defendant_info, default=str)

        # Run all three analyses (statutory, diversion, procedural)
        # These are independent LLM calls — run sequentially to manage cost
        charged_offenses = await self._analyze_statutes(
            charges_json, enhancements_json, defendant_json
        )
        diversion_options = await self._analyze_diversion(charges_json, defendant_json)
        procedural_data = await self._analyze_procedural(charges_json)

        output = {
            "charged_offenses": charged_offenses,
            "diversion_options": diversion_options,
            "procedural_requirements": procedural_data.get("procedural_requirements", []),
            "recent_amendments": procedural_data.get("recent_amendments", []),
        }

        self.log_action(
            "statutes_analysis_completed",
            {
                "offenses_analyzed": len(charged_offenses),
                "diversion_options": len(diversion_options),
            },
        )

        # Confidence: LLM-based statutory knowledge is reliable for well-known
        # GA statutes but should still be verified
        confidence = 0.7

        return self.wrap_output(output, confidence=confidence)

    async def _analyze_statutes(
        self,
        charges_json: str,
        enhancements_json: str,
        defendant_json: str,
    ) -> list[dict[str, Any]]:
        """Get full statutory analysis of each charged offense."""
        try:
            result = await call_llm(
                _STATUTORY_ANALYSIS_PROMPT.format(
                    charges=charges_json,
                    enhancements=enhancements_json,
                    defendant_info=defendant_json,
                ),
                system=_SYSTEM_PROMPT,
                max_tokens=4096,
            )
            return result.get("charged_offenses", [])
        except Exception as exc:
            logger.warning("Statutory analysis failed: %s", exc)
            return []

    async def _analyze_diversion(
        self,
        charges_json: str,
        defendant_json: str,
    ) -> list[dict[str, Any]]:
        """Analyze diversion and alternative sentencing eligibility."""
        try:
            result = await call_llm(
                _DIVERSION_ANALYSIS_PROMPT.format(
                    charges=charges_json,
                    defendant_info=defendant_json,
                ),
                system=_SYSTEM_PROMPT,
                max_tokens=3072,
            )
            return result.get("diversion_options", [])
        except Exception as exc:
            logger.warning("Diversion analysis failed: %s", exc)
            return []

    async def _analyze_procedural(
        self,
        charges_json: str,
    ) -> dict[str, Any]:
        """Identify procedural requirements and deadlines."""
        try:
            result = await call_llm(
                _PROCEDURAL_PROMPT.format(charges=charges_json),
                system=_SYSTEM_PROMPT,
                max_tokens=2048,
            )
            return result
        except Exception as exc:
            logger.warning("Procedural analysis failed: %s", exc)
            return {"procedural_requirements": [], "recent_amendments": []}
