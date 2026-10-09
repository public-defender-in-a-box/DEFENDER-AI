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
import uuid
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.intake import (
    ElementCoverage,
    EvidenceItem,
    FactGatheringOutput,
    TargetedQuestion,
    TimelineEvent,
    WitnessRecord,
)
from src.services.llm_service import call_llm

STATUS = "REAL"

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are a fact-gathering specialist for a Georgia public defender's office. "
    "Your role is to extract, organize, and structure factual information from "
    "client interview responses. You cross-reference client statements against "
    "the elements of each charged offense to identify what has been established, "
    "what is disputed, and where gaps remain.\n\n"
    "JURISDICTION: Georgia (O.C.G.A. Title 16 — Crimes and Offenses)\n\n"
    "CRITICAL RULES:\n"
    "1. You are an INFORMATION ORGANIZER, not an advocate or advisor.\n"
    "2. Report what the client said, not what you think happened.\n"
    "3. Flag inconsistencies neutrally — they may have innocent explanations.\n"
    "4. Confidence scores reflect clarity of client statement, NOT truth.\n"
    "5. Every charge element must be tracked — gaps are as important as coverage.\n"
    "6. Preserve the client's own language for key statements.\n"
    "7. All information is attorney-client privileged.\n\n"
    "EVIDENCE PRESERVATION ALERTS:\n"
    "- Flag any evidence at risk of destruction (surveillance footage typically "
    "retained 30-90 days, cell phone records require preservation letter)\n"
    "- Note chain-of-custody concerns for physical evidence\n"
    "- Identify digital evidence (body cam, dashcam, cell location) that may "
    "require timely subpoena\n\n"
    "OUTPUT: Always respond with valid JSON matching the requested schema."
)

_EXTRACTION_PROMPT_TEMPLATE = """Analyze the client's interview responses against the charged offenses.

CHARGES AND ELEMENTS:
{charges_json}

TARGETED QUESTIONS THAT WERE ASKED:
{questions_json}

CLIENT RESPONSES (from intake interview):
{responses_json}

PRE-INTERVIEW RESEARCH CONTEXT (if available):
{research_context}

Extract and organize the following (return as a single JSON object):

1. "timeline": Array of events in chronological order. Each event:
   - "id": unique ID (e.g. "evt_001")
   - "timestamp_description": natural language timestamp from client's account
   - "event": what happened
   - "source": "CLIENT_STATEMENT" | "DOCUMENT" | "INFERENCE"
   - "confidence": "HIGH" | "MEDIUM" | "LOW"
   - "related_charge_ids": which charges this event relates to
   - "source_message_ids": IDs of source messages (if available)

2. "witnesses": Array of potential witnesses mentioned. Each:
   - "id": unique ID (e.g. "wit_001")
   - "name": name if provided, empty string if unknown
   - "contact_info": any contact info mentioned
   - "relationship": "EYEWITNESS" | "CHARACTER" | "ALIBI" | "EXPERT" | "CO_DEFENDANT" | "VICTIM" | "OTHER"
   - "observed_events": what they witnessed
   - "favorable": true if likely defense-favorable, false if adverse, null if unknown
   - "notes": any relevant notes

3. "evidence_inventory": Physical or digital evidence mentioned. Each:
   - "id": unique ID (e.g. "evi_001")
   - "description": what the evidence is
   - "evidence_type": "PHYSICAL" | "DIGITAL" | "DOCUMENTARY" | "TESTIMONIAL" | "FORENSIC"
   - "location": where it is or was
   - "preservation_status": "PRESERVED" | "AT_RISK" | "UNKNOWN" | "DESTROYED"
   - "relevance": "CRITICAL" | "IMPORTANT" | "SUPPLEMENTARY"
   - "chain_of_custody_concern": true/false
   - "notes": preservation urgency, admissibility concerns

4. "scene_description": Narrative description of the scene based on client account.

5. "element_coverage": For EACH element of EACH charge, assess coverage:
   - "charge_id": the charge ID
   - "element": the specific element
   - "covered": true if client addressed this element
   - "client_position": "ADMITS" | "DENIES" | "PARTIAL" | "NO_RESPONSE"
   - "confidence": "HIGH" | "MEDIUM" | "LOW"
   - "gaps": what information is still needed

6. "follow_up_questions": Questions that should be asked to fill gaps. Each:
   - "question": the question text
   - "relevant_charge_id": which charge
   - "relevant_element": which element
   - "priority": "MUST_ASK" | "SHOULD_ASK" | "IF_TIME"

7. "credibility_notes": Array of strings noting any credibility considerations
   (inconsistencies, corroboration opportunities, demeanor notes from transcript).

Return valid JSON only."""


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
        prompt = _EXTRACTION_PROMPT_TEMPLATE.format(
            charges_json=json.dumps(charges, indent=2, default=str),
            questions_json=json.dumps(questions, indent=2, default=str),
            responses_json=json.dumps(client_responses, indent=2, default=str),
            research_context=json.dumps(research_context, indent=2, default=str),
        )

        try:
            result = await call_llm(prompt, system=_SYSTEM_PROMPT, max_tokens=8192)
        except Exception as e:
            logger.error("Fact gathering LLM call failed: %s", e)
            self.log_action("fact_gathering_llm_error", {"error": str(e)})
            raise

        # Validate and structure the output
        output = self._structure_output(result, charges)

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

    def _structure_output(
        self, raw: dict[str, Any], charges: list[dict[str, Any]]
    ) -> FactGatheringOutput:
        """Validate and structure the LLM output into Pydantic models."""
        timeline = []
        for evt in raw.get("timeline", []):
            try:
                timeline.append(
                    TimelineEvent(
                        id=evt.get("id", f"evt_{uuid.uuid4().hex[:6]}"),
                        timestamp_description=evt.get("timestamp_description", ""),
                        event=evt.get("event", ""),
                        source=evt.get("source", "CLIENT_STATEMENT"),
                        confidence=evt.get("confidence", "LOW"),
                        related_charge_ids=evt.get("related_charge_ids", []),
                        source_message_ids=evt.get("source_message_ids", []),
                    )
                )
            except Exception as e:
                logger.warning("Skipping malformed timeline event: %s", e)

        witnesses = []
        for wit in raw.get("witnesses", []):
            try:
                witnesses.append(
                    WitnessRecord(
                        id=wit.get("id", f"wit_{uuid.uuid4().hex[:6]}"),
                        name=wit.get("name", ""),
                        contact_info=wit.get("contact_info", ""),
                        relationship=wit.get("relationship", "OTHER"),
                        observed_events=wit.get("observed_events", []),
                        favorable=wit.get("favorable"),
                        notes=wit.get("notes", ""),
                    )
                )
            except Exception as e:
                logger.warning("Skipping malformed witness record: %s", e)

        evidence = []
        for evi in raw.get("evidence_inventory", []):
            try:
                evidence.append(
                    EvidenceItem(
                        id=evi.get("id", f"evi_{uuid.uuid4().hex[:6]}"),
                        description=evi.get("description", ""),
                        evidence_type=evi.get("evidence_type", "PHYSICAL"),
                        location=evi.get("location", ""),
                        preservation_status=evi.get("preservation_status", "UNKNOWN"),
                        relevance=evi.get("relevance", "SUPPLEMENTARY"),
                        chain_of_custody_concern=evi.get("chain_of_custody_concern", False),
                        notes=evi.get("notes", ""),
                    )
                )
            except Exception as e:
                logger.warning("Skipping malformed evidence item: %s", e)

        element_coverage = []
        for ec in raw.get("element_coverage", []):
            try:
                element_coverage.append(
                    ElementCoverage(
                        charge_id=ec.get("charge_id", ""),
                        element=ec.get("element", ""),
                        covered=ec.get("covered", False),
                        client_position=ec.get("client_position", "NO_RESPONSE"),
                        confidence=ec.get("confidence", "LOW"),
                        gaps=ec.get("gaps", []),
                    )
                )
            except Exception as e:
                logger.warning("Skipping malformed element coverage: %s", e)

        follow_ups = []
        for fq in raw.get("follow_up_questions", []):
            try:
                follow_ups.append(
                    TargetedQuestion(
                        question=fq.get("question", ""),
                        relevant_charge_id=fq.get("relevant_charge_id", ""),
                        relevant_element=fq.get("relevant_element", ""),
                        priority=fq.get("priority", "SHOULD_ASK"),
                    )
                )
            except Exception as e:
                logger.warning("Skipping malformed follow-up question: %s", e)

        return FactGatheringOutput(
            timeline=timeline,
            witnesses=witnesses,
            evidence_inventory=evidence,
            scene_description=raw.get("scene_description", ""),
            element_coverage=element_coverage,
            follow_up_questions=follow_ups,
            credibility_notes=raw.get("credibility_notes", []),
        )

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
