"""Collateral Consequences Agent — Tier 2 Intake Specialist.

Identifies non-criminal consequences of conviction based on the client's charges
and personal circumstances. These consequences are often more important to the
client than the sentence itself and are critical for plea negotiations.

Key legal authority:
- Padilla v. Kentucky, 559 U.S. 356 (2010) — counsel MUST advise non-citizen
  clients of immigration consequences of a guilty plea
- O.C.G.A. § 42-1-12 (Georgia Sex Offender Registry)
- O.C.G.A. § 16-11-131 (Firearms restrictions for felons)
- O.C.G.A. § 42-8-60 (First Offender Act — may avoid collateral consequences)
- 8 U.S.C. § 1227(a)(2) (Deportable offenses)
- 8 U.S.C. § 1101(a)(43) (Aggravated felony definition)
- 21 U.S.C. § 862 (Drug conviction consequences for federal benefits)

Depends on: Charge Processing (charges), Intake Conductor (personal circumstances).
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.intake import (
    CollateralConsequence,
    CollateralConsequencesOutput,
    PadillaAssessment,
)
from src.services.llm_service import call_llm

STATUS = "REAL"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a collateral consequences specialist for a Georgia public defender's "
    "office. You identify ALL non-criminal consequences of conviction for each "
    "charged offense, considering the client's specific personal circumstances.\n\n"
    "JURISDICTION: Georgia (O.C.G.A.), with federal consequences where applicable.\n\n"
    "CRITICAL LEGAL OBLIGATIONS:\n"
    "1. PADILLA v. KENTUCKY (2010): Defense counsel MUST advise non-citizen clients "
    "about immigration consequences of a guilty plea. Failure = ineffective "
    "assistance of counsel (IAC). You MUST flag this.\n"
    "2. Collateral consequences are NOT optional analysis — they are constitutionally "
    "required information for plea negotiations.\n"
    "3. Some consequences attach to ARREST, not just conviction.\n"
    "4. Georgia First Offender Act (O.C.G.A. § 42-8-60) may avoid some collateral "
    "consequences — always assess eligibility.\n\n"
    "CATEGORIES TO ANALYZE:\n"
    "- IMMIGRATION: deportation, inadmissibility, aggravated felony, CIMT, bars to "
    "naturalization (8 U.S.C. §§ 1101, 1182, 1227)\n"
    "- EMPLOYMENT: job loss, occupational licensing bars, professional disqualification, "
    "background check impact\n"
    "- HOUSING: public housing ineligibility (24 C.F.R. § 960.204), private housing "
    "background check barriers\n"
    "- EDUCATION: financial aid ineligibility (drug offenses), school discipline, "
    "college admission impact\n"
    "- FAMILY: custody/visitation impact, child protective services involvement, "
    "domestic violence implications\n"
    "- CIVIL_RIGHTS: voting (Georgia: felon disenfranchisement during sentence), "
    "jury service, firearm rights (O.C.G.A. § 16-11-131)\n"
    "- PROFESSIONAL_LICENSE: Georgia licensing board restrictions by offense type\n"
    "- SEX_OFFENDER: registration requirements (O.C.G.A. § 42-1-12), residency "
    "restrictions, community notification\n"
    "- FINANCIAL: fines, restitution, surcharges, asset forfeiture, credit impact\n\n"
    "OUTPUT: Always respond with valid JSON matching the requested schema."
)

_ANALYSIS_PROMPT_TEMPLATE = """Analyze collateral consequences for this Georgia criminal case.

CHARGES:
{charges_json}

CLIENT PERSONAL CIRCUMSTANCES:
{circumstances_json}

CLIENT STATED PRIORITIES (from intake):
{priorities_json}

For each charge, identify ALL collateral consequences across every category.
Return a single JSON object with:

1. "consequences": Array of consequences. Each must include:
   - "id": unique ID (e.g. "cc_001")
   - "category": "IMMIGRATION" | "EMPLOYMENT" | "HOUSING" | "EDUCATION" | "FAMILY" | "CIVIL_RIGHTS" | "PROFESSIONAL_LICENSE" | "SEX_OFFENDER" | "FINANCIAL"
   - "description": clear explanation of the consequence
   - "severity": "SEVERE" | "MODERATE" | "MINOR"
   - "charge_specific": true if tied to a specific charge
   - "related_charge_ids": which charges trigger this consequence
   - "affects_plea_strategy": true if this should influence plea negotiations
   - "georgia_statute": O.C.G.A. citation if applicable
   - "federal_statute": Federal citation if applicable
   - "mitigation_possible": true if there's a way to avoid or reduce this consequence
   - "mitigation_strategy": how to mitigate (e.g. First Offender Act, lesser included offense plea)

2. "padilla_assessment": Padilla v. Kentucky compliance check:
   - "non_citizen": true/false based on client circumstances
   - "immigration_status": "LPR" | "VISA_HOLDER" | "UNDOCUMENTED" | "DACA" | "TPS" | "ASYLEE" | "REFUGEE" | "UNKNOWN" | "CITIZEN"
   - "deportation_risk": "CERTAIN" | "LIKELY" | "POSSIBLE" | "UNLIKELY" | "UNKNOWN"
   - "aggravated_felony_risk": true/false (8 U.S.C. § 1101(a)(43))
   - "crime_involving_moral_turpitude": true/false
   - "controlled_substance_offense": true/false
   - "firearm_offense": true/false
   - "domestic_violence_offense": true/false
   - "advisory_required": true if Padilla advisory must be given
   - "advisory_summary": specific immigration advice counsel must provide

3. "plea_strategy_impact": Narrative of how collateral consequences should
   influence plea strategy. Include charge-specific bargaining points.

4. "priority_consequences": Array of consequence IDs for the most critical
   consequences — these should be flagged for immediate attorney attention.

5. "client_stated_priorities": Echo back the client's stated priorities
   and note which consequences directly affect them.

IMPORTANT: For immigration consequences, always flag whether the offense
qualifies as an "aggravated felony" under 8 U.S.C. § 1101(a)(43), even if
the Georgia offense is a misdemeanor — federal immigration law uses its own
definitions.

Return valid JSON only."""


class CollateralConsequencesAgent(BaseAgent):
    """Tier 2 Intake Specialist — identifies non-criminal consequences of conviction.

    Analyzes charges against client circumstances to produce a comprehensive
    collateral consequences inventory. Includes Padilla v. Kentucky compliance
    assessment for non-citizen clients.
    """

    agent_id = "collateral_agent"
    agent_name = "Collateral Consequences Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Identify collateral consequences based on charges and circumstances.

        Args:
            input_data: Dict containing:
                - charges: parsed charges from Charge Processing Agent
                - personal_circumstances: client background from intake
                - client_priorities: stated priorities from intake (optional)
                - intake_summary: full intake summary (optional)

        Returns:
            Wrapped output with CollateralConsequencesOutput data and confidence.
        """
        self.log_action(
            "collateral_analysis_started",
            {
                "has_charges": bool(input_data.get("charges")),
                "has_circumstances": bool(input_data.get("personal_circumstances")),
            },
        )

        charges = input_data.get("charges", [])
        circumstances = input_data.get("personal_circumstances", {})
        priorities = input_data.get("client_priorities", [])

        # Extract priorities from intake summary if not provided directly
        if not priorities and input_data.get("intake_summary"):
            summary = input_data["intake_summary"]
            if isinstance(summary, dict):
                priorities = summary.get("priorities_and_concerns", [])

        if not charges:
            self.log_action("collateral_analysis_skipped", {"reason": "no_charges"})
            empty_padilla = PadillaAssessment(
                non_citizen=False,
                advisory_required=False,
            )
            empty_output = CollateralConsequencesOutput(
                consequences=[],
                padilla_assessment=empty_padilla,
                plea_strategy_impact="No charges available for collateral analysis.",
                priority_consequences=[],
                client_stated_priorities=priorities if isinstance(priorities, list) else [],
            )
            return self.wrap_output(empty_output.model_dump(), confidence=0.0)

        prompt = _ANALYSIS_PROMPT_TEMPLATE.format(
            charges_json=json.dumps(charges, indent=2, default=str),
            circumstances_json=json.dumps(circumstances, indent=2, default=str),
            priorities_json=json.dumps(priorities, indent=2, default=str),
        )

        try:
            result = await call_llm(prompt, system=_SYSTEM_PROMPT, max_tokens=8192)
        except Exception as e:
            logger.error("Collateral consequences LLM call failed: %s", e)
            self.log_action("collateral_analysis_llm_error", {"error": str(e)})
            raise

        output = self._structure_output(result, priorities)
        confidence = self._calculate_confidence(output, circumstances)

        self.log_action(
            "collateral_analysis_completed",
            {
                "consequences_found": len(output.consequences),
                "severe_consequences": sum(
                    1 for c in output.consequences if c.severity == "SEVERE"
                ),
                "padilla_required": output.padilla_assessment.advisory_required,
                "priority_count": len(output.priority_consequences),
                "confidence": confidence,
            },
        )

        return self.wrap_output(output.model_dump(), confidence=confidence)

    def _structure_output(
        self, raw: dict[str, Any], priorities: list[Any]
    ) -> CollateralConsequencesOutput:
        """Validate and structure LLM output into Pydantic models."""
        consequences = []
        for cc in raw.get("consequences", []):
            try:
                consequences.append(
                    CollateralConsequence(
                        id=cc.get("id", f"cc_{uuid.uuid4().hex[:6]}"),
                        category=cc.get("category", "EMPLOYMENT"),
                        description=cc.get("description", ""),
                        severity=cc.get("severity", "MODERATE"),
                        charge_specific=cc.get("charge_specific", False),
                        related_charge_ids=cc.get("related_charge_ids", []),
                        affects_plea_strategy=cc.get("affects_plea_strategy", False),
                        georgia_statute=cc.get("georgia_statute", ""),
                        federal_statute=cc.get("federal_statute", ""),
                        mitigation_possible=cc.get("mitigation_possible", False),
                        mitigation_strategy=cc.get("mitigation_strategy", ""),
                    )
                )
            except Exception as e:
                logger.warning("Skipping malformed consequence: %s", e)

        # Padilla assessment
        padilla_raw = raw.get("padilla_assessment", {})
        padilla = PadillaAssessment(
            non_citizen=padilla_raw.get("non_citizen", False),
            immigration_status=padilla_raw.get("immigration_status", "UNKNOWN"),
            deportation_risk=padilla_raw.get("deportation_risk", "UNKNOWN"),
            aggravated_felony_risk=padilla_raw.get("aggravated_felony_risk", False),
            crime_involving_moral_turpitude=padilla_raw.get(
                "crime_involving_moral_turpitude", False
            ),
            controlled_substance_offense=padilla_raw.get("controlled_substance_offense", False),
            firearm_offense=padilla_raw.get("firearm_offense", False),
            domestic_violence_offense=padilla_raw.get("domestic_violence_offense", False),
            advisory_required=padilla_raw.get("advisory_required", False),
            advisory_summary=padilla_raw.get("advisory_summary", ""),
        )

        return CollateralConsequencesOutput(
            consequences=consequences,
            padilla_assessment=padilla,
            plea_strategy_impact=raw.get("plea_strategy_impact", ""),
            priority_consequences=raw.get("priority_consequences", []),
            client_stated_priorities=(priorities if isinstance(priorities, list) else []),
        )

    def _calculate_confidence(
        self,
        output: CollateralConsequencesOutput,
        circumstances: dict[str, Any],
    ) -> float:
        """Calculate confidence based on analysis completeness."""
        score = 0.5  # baseline

        # More consequences = more thorough analysis
        if len(output.consequences) >= 5:
            score += 0.15
        elif len(output.consequences) >= 3:
            score += 0.1

        # Having a Padilla assessment is important
        if output.padilla_assessment.immigration_status != "UNKNOWN":
            score += 0.1

        # Rich circumstances data = better analysis
        if circumstances:
            filled_fields = sum(
                1 for v in circumstances.values() if v and v != "" and v != 0 and v is not False
            )
            score += min(filled_fields * 0.02, 0.15)

        # Having plea strategy impact text
        if len(output.plea_strategy_impact) > 50:
            score += 0.05

        return max(0.3, min(score, 0.95))
