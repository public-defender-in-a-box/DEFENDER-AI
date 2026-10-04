"""Personal Circumstances Agent — Tier 2 Intake Specialist.

Gathers and analyzes information relevant to bail, sentencing mitigation, and
diversion eligibility. This agent focuses on the PERSON, not the facts of the
case. The output informs bail arguments, mitigation narratives, and diversion
screening.

Georgia-specific authority:
- O.C.G.A. § 17-6-1 (Bail in general)
- O.C.G.A. § 17-6-12 (Conditions of release)
- O.C.G.A. § 42-8-60 et seq. (Georgia First Offender Act)
- O.C.G.A. § 15-1-15 (Accountability Courts — Drug, Mental Health, Veterans)
- O.C.G.A. § 42-8-34 (Pretrial diversion programs)
- O.C.G.A. § 17-10-1 (Sentencing — general provisions)
- O.C.G.A. § 17-10-30 (Youthful Offender Act)

Depends on: Intake Conductor (client personal information, priorities).
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.intake import (
    BailProfile,
    CommunityTie,
    DiversionEligibility,
    FlightRiskFactor,
    MitigationNarrative,
    PersonalCircumstancesOutput,
    TreatmentNeed,
)
from src.services.llm_service import call_llm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a personal circumstances analyst for a Georgia public defender's "
    "office. You analyze client background information to build bail arguments, "
    "mitigation narratives, and diversion eligibility assessments.\n\n"
    "JURISDICTION: Georgia\n\n"
    "YOUR ROLE:\n"
    "1. You analyze — you do NOT advise. All outputs are for the attorney.\n"
    "2. Present the client's circumstances favorably but honestly.\n"
    "3. Identify every possible mitigation factor and diversion pathway.\n"
    "4. Flag treatment needs that could support diversion or mitigation.\n"
    "5. All information is attorney-client privileged.\n\n"
    "GEORGIA BAIL LAW (O.C.G.A. § 17-6-1):\n"
    "- Most offenses are bailable. Non-bailable: treason, murder, rape, armed "
    "robbery, aircraft hijacking, and certain drug trafficking offenses (unless "
    "court finds no significant risk of flight or danger).\n"
    "- Factors: nature of offense, defendant's ability to post bail, community "
    "ties, employment, family, prior record, flight risk, danger to community.\n"
    "- O.C.G.A. § 17-6-12: conditions of release (electronic monitoring, curfew, "
    "substance abuse testing, no-contact orders, etc.).\n\n"
    "GEORGIA FIRST OFFENDER ACT (O.C.G.A. § 42-8-60):\n"
    "- Available to defendants with no prior felony conviction.\n"
    "- Court defers adjudication of guilt; successful completion = no conviction.\n"
    "- NOT available for: serious violent felonies (§ 17-10-6.1), sex offenses "
    "requiring registration, DUI (O.C.G.A. § 40-6-391).\n"
    "- Can only be used ONCE in a lifetime.\n\n"
    "GEORGIA ACCOUNTABILITY COURTS (O.C.G.A. § 15-1-15):\n"
    "- Drug Court: non-violent drug offenders, structured treatment program\n"
    "- Mental Health Court: defendants with diagnosed mental illness\n"
    "- Veterans Court: veterans and active military\n"
    "- Family Treatment Court: parents in dependency proceedings\n"
    "- DUI Court: repeat DUI offenders\n"
    "- Each county may or may not have each type.\n\n"
    "PRETRIAL DIVERSION (O.C.G.A. § 42-8-34):\n"
    "- DA discretion. Typically first-time offenders, non-violent offenses.\n"
    "- Successful completion = charges dismissed.\n\n"
    "YOUTHFUL OFFENDER (O.C.G.A. § 17-10-30):\n"
    "- Defendants under 25 at time of offense, excluding certain violent offenses.\n"
    "- Alternative sentencing considerations.\n\n"
    "OUTPUT: Always respond with valid JSON matching the requested schema."
)

_ANALYSIS_PROMPT_TEMPLATE = """Analyze this client's personal circumstances for bail, mitigation, and diversion.

CLIENT BACKGROUND (from intake):
{background_json}

CHARGES:
{charges_json}

CLIENT PRIORITIES:
{priorities_json}

Return a single JSON object with:

1. "bail_profile":
   - "community_ties": Array of community ties. Each:
     - "category": "EMPLOYMENT" | "FAMILY" | "RESIDENCE" | "EDUCATION" | "RELIGIOUS" | "COMMUNITY_ORG" | "MILITARY"
     - "description": specific description
     - "strength": "STRONG" | "MODERATE" | "WEAK"
     - "verifiable": true/false
     - "verification_source": how to verify
   - "flight_risk_factors": Array. Each:
     - "factor": what the factor is
     - "direction": "INCREASES_RISK" | "DECREASES_RISK"
     - "weight": "HIGH" | "MEDIUM" | "LOW"
     - "notes": context
   - "danger_to_community_factors": Array of strings (factors relevant to dangerousness assessment)
   - "recommendation": "OR" | "LOW_BOND" | "MODERATE_BOND" | "HIGH_BOND" (personal recognizance through high bond)
   - "recommended_conditions": Array of suggested release conditions
   - "georgia_bail_schedule_note": Reference to applicable county bail schedule if relevant

2. "mitigation_narrative":
   - "summary": Draft narrative paragraph for sentencing (mark DRAFT — ATTORNEY REVIEW REQUIRED)
   - "key_themes": Array of mitigation themes (e.g., "supportive family", "employment stability")
   - "favorable_factors": Array of specific favorable factors
   - "areas_needing_development": What additional information or documentation would strengthen mitigation
   - "recommended_documentation": Array of documents to gather (employment records, treatment records, letters of support, etc.)

3. "diversion_eligibility": Array of programs. Each:
   - "program": "PRETRIAL_DIVERSION" | "DRUG_COURT" | "MENTAL_HEALTH_COURT" | "VETERANS_COURT" | "ACCOUNTABILITY_COURT" | "FIRST_OFFENDER"
   - "eligible": true/false
   - "basis": explanation of eligibility or ineligibility
   - "georgia_authority": O.C.G.A. citation
   - "conditions": typical conditions if enrolled
   - "notes": any strategic considerations

4. "treatment_needs": Array of identified needs. Each:
   - "category": "SUBSTANCE_ABUSE" | "MENTAL_HEALTH" | "MEDICAL" | "HOUSING" | "EMPLOYMENT" | "EDUCATION" | "FAMILY"
   - "description": what the need is
   - "urgency": "IMMEDIATE" | "NEAR_TERM" | "ONGOING"
   - "relevant_to_diversion": true/false
   - "relevant_to_mitigation": true/false

5. "first_offender_eligible": true/false — Georgia First Offender Act eligibility
6. "first_offender_notes": Explanation of eligibility analysis
7. "youthful_offender_eligible": true/false — if client is under 25
8. "veterans_status": true/false — if client is a veteran

Return valid JSON only."""


class PersonalCircumstancesAgent(BaseAgent):
    """Tier 2 Intake Specialist — analyzes personal circumstances.

    Builds bail arguments, mitigation narratives, and diversion eligibility
    assessments from client background information. Georgia-specific: First
    Offender Act, Accountability Courts, and state bail law.
    """

    agent_id = "personal_circumstances"
    agent_name = "Personal Circumstances Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze personal circumstances for bail, mitigation, diversion.

        Args:
            input_data: Dict containing:
                - client_background: personal info from intake (demographics,
                  employment, housing, family, mental health, substance use, etc.)
                - charges: parsed charges from Charge Processing Agent (optional,
                  needed for First Offender and diversion eligibility)
                - client_priorities: stated priorities from intake (optional)

        Returns:
            Wrapped output with PersonalCircumstancesOutput data and confidence.
        """
        self.log_action(
            "personal_circumstances_started",
            {
                "has_background": bool(input_data.get("client_background")),
                "has_charges": bool(input_data.get("charges")),
            },
        )

        background = input_data.get("client_background", {})
        charges = input_data.get("charges", [])
        priorities = input_data.get("client_priorities", [])

        if not background:
            self.log_action(
                "personal_circumstances_skipped",
                {
                    "reason": "no_background_data",
                },
            )
            empty_output = PersonalCircumstancesOutput(
                bail_profile=BailProfile(),
                mitigation_narrative=MitigationNarrative(
                    summary="Insufficient client background data for mitigation analysis.",
                ),
                diversion_eligibility=[],
                treatment_needs=[],
            )
            return self.wrap_output(empty_output.model_dump(), confidence=0.0)

        prompt = _ANALYSIS_PROMPT_TEMPLATE.format(
            background_json=json.dumps(background, indent=2, default=str),
            charges_json=json.dumps(charges, indent=2, default=str),
            priorities_json=json.dumps(priorities, indent=2, default=str),
        )

        try:
            result = await call_llm(prompt, system=_SYSTEM_PROMPT, max_tokens=8192)
        except Exception as e:
            logger.error("Personal circumstances LLM call failed: %s", e)
            self.log_action("personal_circumstances_llm_error", {"error": str(e)})
            raise

        output = self._structure_output(result)
        confidence = self._calculate_confidence(output, background)

        self.log_action(
            "personal_circumstances_completed",
            {
                "community_ties": len(output.bail_profile.community_ties),
                "diversion_programs_checked": len(output.diversion_eligibility),
                "diversion_eligible_count": sum(
                    1 for d in output.diversion_eligibility if d.eligible
                ),
                "treatment_needs": len(output.treatment_needs),
                "first_offender_eligible": output.first_offender_eligible,
                "confidence": confidence,
            },
        )

        return self.wrap_output(output.model_dump(), confidence=confidence)

    def _structure_output(self, raw: dict[str, Any]) -> PersonalCircumstancesOutput:
        """Validate and structure LLM output into Pydantic models."""
        # Bail profile
        bail_raw = raw.get("bail_profile", {})
        community_ties = []
        for ct in bail_raw.get("community_ties", []):
            try:
                community_ties.append(
                    CommunityTie(
                        category=ct.get("category", "RESIDENCE"),
                        description=ct.get("description", ""),
                        strength=ct.get("strength", "MODERATE"),
                        verifiable=ct.get("verifiable", False),
                        verification_source=ct.get("verification_source", ""),
                    )
                )
            except Exception as e:
                logger.warning("Skipping malformed community tie: %s", e)

        flight_risk_factors = []
        for frf in bail_raw.get("flight_risk_factors", []):
            try:
                flight_risk_factors.append(
                    FlightRiskFactor(
                        factor=frf.get("factor", ""),
                        direction=frf.get("direction", "INCREASES_RISK"),
                        weight=frf.get("weight", "MEDIUM"),
                        notes=frf.get("notes", ""),
                    )
                )
            except Exception as e:
                logger.warning("Skipping malformed flight risk factor: %s", e)

        bail_profile = BailProfile(
            community_ties=community_ties,
            flight_risk_factors=flight_risk_factors,
            danger_to_community_factors=bail_raw.get("danger_to_community_factors", []),
            recommendation=bail_raw.get("recommendation", ""),
            recommended_conditions=bail_raw.get("recommended_conditions", []),
            georgia_bail_schedule_note=bail_raw.get("georgia_bail_schedule_note", ""),
        )

        # Mitigation narrative
        mit_raw = raw.get("mitigation_narrative", {})
        mitigation_narrative = MitigationNarrative(
            summary=mit_raw.get("summary", ""),
            key_themes=mit_raw.get("key_themes", []),
            favorable_factors=mit_raw.get("favorable_factors", []),
            areas_needing_development=mit_raw.get("areas_needing_development", []),
            recommended_documentation=mit_raw.get("recommended_documentation", []),
        )

        # Diversion eligibility
        diversion = []
        for d in raw.get("diversion_eligibility", []):
            try:
                diversion.append(
                    DiversionEligibility(
                        program=d.get("program", "PRETRIAL_DIVERSION"),
                        eligible=d.get("eligible", False),
                        basis=d.get("basis", ""),
                        georgia_authority=d.get("georgia_authority", ""),
                        conditions=d.get("conditions", []),
                        notes=d.get("notes", ""),
                    )
                )
            except Exception as e:
                logger.warning("Skipping malformed diversion entry: %s", e)

        # Treatment needs
        treatment_needs = []
        for tn in raw.get("treatment_needs", []):
            try:
                treatment_needs.append(
                    TreatmentNeed(
                        category=tn.get("category", "MEDICAL"),
                        description=tn.get("description", ""),
                        urgency=tn.get("urgency", "ONGOING"),
                        relevant_to_diversion=tn.get("relevant_to_diversion", False),
                        relevant_to_mitigation=tn.get("relevant_to_mitigation", False),
                    )
                )
            except Exception as e:
                logger.warning("Skipping malformed treatment need: %s", e)

        return PersonalCircumstancesOutput(
            bail_profile=bail_profile,
            mitigation_narrative=mitigation_narrative,
            diversion_eligibility=diversion,
            treatment_needs=treatment_needs,
            first_offender_eligible=raw.get("first_offender_eligible", False),
            first_offender_notes=raw.get("first_offender_notes", ""),
            youthful_offender_eligible=raw.get("youthful_offender_eligible", False),
            veterans_status=raw.get("veterans_status", False),
        )

    def _calculate_confidence(
        self,
        output: PersonalCircumstancesOutput,
        background: dict[str, Any],
    ) -> float:
        """Calculate confidence based on data completeness and analysis depth."""
        score = 0.5  # baseline

        # Background data richness
        if background:
            filled = sum(
                1 for v in background.values() if v and v != "" and v != 0 and v is not False
            )
            score += min(filled * 0.03, 0.2)

        # Community ties identified
        if len(output.bail_profile.community_ties) >= 3:
            score += 0.1
        elif len(output.bail_profile.community_ties) >= 1:
            score += 0.05

        # Diversion programs assessed
        if len(output.diversion_eligibility) >= 3:
            score += 0.1
        elif len(output.diversion_eligibility) >= 1:
            score += 0.05

        # Mitigation narrative quality
        if len(output.mitigation_narrative.summary) > 100:
            score += 0.05

        return max(0.3, min(score, 0.95))
