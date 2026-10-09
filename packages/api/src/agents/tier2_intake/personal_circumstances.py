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
from src.models.intake import BailProfile, MitigationNarrative, PersonalCircumstancesOutput
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "REAL"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

# Prompts: src/prompts/personal_circumstances/
_SYSTEM = load_prompt("personal_circumstances.system", "v1")
_ANALYSIS = load_prompt("personal_circumstances.analysis", "v1")
# Thinking tokens count toward max_tokens on current models (Phase 1 §2).
_MAX_TOKENS = 16000


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

        prompt = _ANALYSIS.text.format(
            background_json=json.dumps(background, indent=2, default=str),
            charges_json=json.dumps(charges, indent=2, default=str),
            priorities_json=json.dumps(priorities, indent=2, default=str),
        )

        # The response model is the output model: structured outputs constrain every
        # item, so there is no per-item "skip malformed" pass (Phase 1 §3.2).
        result = await call_model(
            ModelCallRequest(
                prompt=prompt,
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=PersonalCircumstancesOutput,
                prompt_id="personal_circumstances.analysis",
                prompt_version=compose_version(_SYSTEM, _ANALYSIS),
                agent_id=self.agent_id,
            )
        )
        output = result.data
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
