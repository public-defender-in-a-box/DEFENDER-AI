"""Fact Gathering Agent — Tier 2 Intake Specialist.

Conducts the core factual interview by extracting and structuring information
from client responses against charge elements. Dynamically generates follow-up
questions for gaps. Produces a structured timeline, witness roster, evidence
inventory, and element-by-element coverage analysis.

Depends on: Intake Conductor (client responses), Charge Processing (charge
elements and targeted questions).

Georgia-specific knowledge:
- O.C.G.A. Title 16 offense elements
- Georgia criminal procedure (Title 17) timing and procedural requirements
- Georgia Rules of Evidence for admissibility considerations
- Scene and evidence preservation under Georgia law
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.intake import FactGatheringOutput
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "REAL"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

# Prompts: src/prompts/fact_gatherer/
_SYSTEM = load_prompt("fact_gatherer.system", "v1")
_EXTRACTION = load_prompt("fact_gatherer.extraction", "v1")
# Thinking tokens count toward max_tokens on current models (Phase 1 §2).
_MAX_TOKENS = 16000


class FactGathererAgent(BaseAgent):
    """Tier 2 Intake Specialist — extracts and structures case facts.

    Reads client responses from the Intake Conductor, cross-references against
    charge elements from the Charge Processing Agent, and produces a structured
    factual record for the defense team.
    """

    agent_id = "fact_gatherer"
    agent_name = "Fact Gathering Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate structured facts from client responses and charge elements.

        Args:
            input_data: Dict containing:
                - targeted_questions: list of questions asked during intake
                - client_responses: dict or list of client response messages
                - charges: parsed charge data from Charge Processing Agent
                - research_context: pre-interview research (optional)
                - intake_facts: any facts already extracted by Intake Conductor (optional)

        Returns:
            Wrapped output with FactGatheringOutput data and confidence score.
        """
        self.log_action(
            "fact_gathering_started",
            {
                "has_charges": bool(input_data.get("charges")),
                "has_responses": bool(input_data.get("client_responses")),
            },
        )

        # Extract inputs with defaults
        questions = input_data.get("targeted_questions", [])
        client_responses = input_data.get("client_responses", {})
        charges = input_data.get("charges", [])
        research_context = input_data.get("research_context", {})
        intake_facts = input_data.get("intake_facts", [])

        # Validate we have enough to work with
        if not client_responses and not intake_facts:
            self.log_action("fact_gathering_skipped", {"reason": "no_client_data"})
            empty_output = FactGatheringOutput(
                timeline=[],
                witnesses=[],
                evidence_inventory=[],
                scene_description="",
                element_coverage=[],
                follow_up_questions=[],
                credibility_notes=["No client responses available for fact extraction."],
            )
            return self.wrap_output(empty_output.model_dump(), confidence=0.0)

        # Build the prompt
        prompt = _EXTRACTION.text.format(
            charges_json=json.dumps(charges, indent=2, default=str),
            questions_json=json.dumps(questions, indent=2, default=str),
            responses_json=json.dumps(client_responses, indent=2, default=str),
            research_context=json.dumps(research_context, indent=2, default=str),
        )

        # The response model is the output model: structured outputs constrain every
        # item, so there is no per-item "skip malformed" pass (Phase 1 §3.2).
        result = await call_model(
            ModelCallRequest(
                prompt=prompt,
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=FactGatheringOutput,
                prompt_id="fact_gatherer.extraction",
                prompt_version=compose_version(_SYSTEM, _EXTRACTION),
                agent_id=self.agent_id,
            )
        )
        output = result.data

        # Calculate confidence based on element coverage
        confidence = self._calculate_confidence(output)

        self.log_action(
            "fact_gathering_completed",
            {
                "timeline_events": len(output.timeline),
                "witnesses": len(output.witnesses),
                "evidence_items": len(output.evidence_inventory),
                "elements_covered": sum(1 for ec in output.element_coverage if ec.covered),
                "elements_total": len(output.element_coverage),
                "follow_ups_needed": len(output.follow_up_questions),
                "confidence": confidence,
            },
        )

        return self.wrap_output(output.model_dump(), confidence=confidence)

    def _calculate_confidence(self, output: FactGatheringOutput) -> float:
        """Calculate overall confidence based on element coverage and data quality."""
        if not output.element_coverage:
            return 0.5  # No elements to assess

        covered = sum(1 for ec in output.element_coverage if ec.covered)
        total = len(output.element_coverage)
        coverage_ratio = covered / total if total > 0 else 0.0

        # Boost for having timeline events and witnesses
        has_timeline = min(len(output.timeline) / 3, 1.0) * 0.1
        has_witnesses = min(len(output.witnesses) / 2, 1.0) * 0.05

        # Penalize for many MUST_ASK follow-ups
        must_asks = sum(1 for fq in output.follow_up_questions if fq.priority == "MUST_ASK")
        penalty = min(must_asks * 0.05, 0.2)

        confidence = (coverage_ratio * 0.7) + has_timeline + has_witnesses - penalty
        return max(0.1, min(confidence, 0.95))
