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
from src.models.responses.pre_interview import PreInterviewBrief
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "PARTIAL"

logger = logging.getLogger(__name__)


# Prompts: src/prompts/pre_interview_research/
_SYSTEM = load_prompt("pre_interview_research.system", "v1")
_BRIEF = load_prompt("pre_interview_research.brief", "v1")
# Thinking tokens count toward max_tokens on current models (Phase 1 §2).
_MAX_TOKENS = 16000


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

        prompt = _BRIEF.text.format(charge_data=charge_str)

        # A failed call raises. It used to return an "Error generating summary" brief
        # with every list empty, which the Orchestrator merged as a success.
        call = await call_model(
            ModelCallRequest(
                prompt=prompt,
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=PreInterviewBrief,
                prompt_id="pre_interview_research.brief",
                prompt_version=compose_version(_SYSTEM, _BRIEF),
                agent_id=self.agent_id,
            )
        )
        result = call.data.model_dump()

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
