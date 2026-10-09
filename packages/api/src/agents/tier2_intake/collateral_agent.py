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
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.intake import CollateralConsequencesOutput, PadillaAssessment
from src.models.responses.intake import CollateralAnalysis
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "REAL"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

# Prompts: src/prompts/collateral_agent/
_SYSTEM = load_prompt("collateral_agent.system", "v1")
_ANALYSIS = load_prompt("collateral_agent.analysis", "v1")
# Thinking tokens count toward max_tokens on current models (Phase 1 §2).
_MAX_TOKENS = 16000


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

        prompt = _ANALYSIS.text.format(
            charges_json=json.dumps(charges, indent=2, default=str),
            circumstances_json=json.dumps(circumstances, indent=2, default=str),
            priorities_json=json.dumps(priorities, indent=2, default=str),
        )

        # Structured outputs constrain every item, so there is no per-item
        # "skip malformed" pass (Phase 1 §3.2).
        result = await call_model(
            ModelCallRequest(
                prompt=prompt,
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=CollateralAnalysis,
                prompt_id="collateral_agent.analysis",
                prompt_version=compose_version(_SYSTEM, _ANALYSIS),
                agent_id=self.agent_id,
            )
        )
        output = CollateralConsequencesOutput(
            **result.data.model_dump(),
            client_stated_priorities=priorities if isinstance(priorities, list) else [],
        )
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
