"""Disclosure Tracking Agent — Tier 2 Attorney Prep.

Tracks Brady, Giglio, and Jencks material across the lifecycle of a case.
Core responsibilities:
  1. Ingest and classify discovery documents into a timestamped ledger
  2. Generate a dynamic checklist based on case type and facts
  3. Detect gaps and red flags in prosecutorial disclosure
  4. Track discovery requests and deadlines
  5. Build a disclosure timeline
  6. Run a pre-trial Brady compliance audit
  7. Use LLM to surface exculpatory language, implicit disclosure triggers,
     and chain-of-custody issues buried in documents

All outputs marked: DRAFT — ATTORNEY REVIEW REQUIRED
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.responses.disclosure import (
    ComplianceBundle,
    DisclosureChecklist,
    DiscoveryDrafts,
    DocumentClassificationResult,
    GapAnalysis,
)
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "REAL"

logger = logging.getLogger(__name__)

# Prompts: src/prompts/disclosure_tracking/
_CLASSIFY = load_prompt("disclosure_tracking.classify_documents", "v1")
_CHECKLIST = load_prompt("disclosure_tracking.checklist", "v1")
_GAPS = load_prompt("disclosure_tracking.gap_detection", "v1")
_COMPLIANCE = load_prompt("disclosure_tracking.compliance_report", "v1")
_DRAFTS = load_prompt("disclosure_tracking.drafts", "v1")
# The system prompt these calls used as call_llm's default.
_SYSTEM = load_prompt("shared.json_assistant", "v1")
# Thinking tokens count toward max_tokens on current models (Phase 1 §2).
_MAX_TOKENS = 24000


class DisclosureTrackingAgent(BaseAgent):
    agent_id = "disclosure_tracking"
    agent_name = "Disclosure Tracking Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the full disclosure tracking pipeline.

        Input keys:
            discovery_documents: list[dict] — documents received so far
            charges: list[dict] | str — parsed charges or charge summary
            case_type: str — e.g., "armed_robbery", "drug_possession", "dv"
            intake_facts: dict | str — facts from intake
            officer_roster: list[dict] — officers involved
            jurisdiction: str — default "GA"
            case_timeline: dict — key dates (arraignment, trial, etc.)
            prior_requests: list[dict] — previously sent discovery requests
            case_id: str

        Output: ConfidenceRated wrapper around DisclosureTrackingOutput dict
        """
        self.log_action(
            "disclosure_tracking_started",
            {
                "case_id": input_data.get("case_id", ""),
            },
        )

        # ── Gather inputs ─────────────────────────────────────────────
        discovery_docs = input_data.get("discovery_documents", [])
        charges = input_data.get("charges", "")
        case_type = input_data.get("case_type", "criminal")
        intake_facts = input_data.get("intake_facts", "")
        officer_roster = input_data.get("officer_roster", [])
        jurisdiction = input_data.get("jurisdiction", "GA")
        case_timeline = input_data.get("case_timeline", {})
        prior_requests = input_data.get("prior_requests", [])
        case_id = input_data.get("case_id", "")

        # Serialize complex inputs for LLM
        charges_text = (
            json.dumps(charges, indent=2) if isinstance(charges, (dict, list)) else str(charges)
        )
        facts_text = (
            json.dumps(intake_facts, indent=2)
            if isinstance(intake_facts, dict)
            else str(intake_facts)
        )
        docs_text = (
            json.dumps(discovery_docs, indent=2)
            if isinstance(discovery_docs, list)
            else str(discovery_docs)
        )
        officers_text = (
            json.dumps(officer_roster, indent=2)
            if isinstance(officer_roster, list)
            else str(officer_roster)
        )
        timeline_text = (
            json.dumps(case_timeline, indent=2)
            if isinstance(case_timeline, dict)
            else str(case_timeline)
        )
        requests_text = (
            json.dumps(prior_requests, indent=2)
            if isinstance(prior_requests, list)
            else str(prior_requests)
        )

        # ── Pass 1: Document Classification & Ledger ──────────────────
        self.log_action("pass1_document_classification_started")
        ledger_and_highlights = await self._classify_documents(
            docs_text,
            charges_text,
            facts_text,
        )

        # ── Pass 2: Dynamic Checklist Generation ──────────────────────
        self.log_action("pass2_checklist_generation_started")
        checklist = await self._generate_checklist(
            charges_text,
            case_type,
            facts_text,
            officers_text,
            jurisdiction,
        )

        # ── Pass 3: Gap Detection & Red Flag Analysis ─────────────────
        self.log_action("pass3_gap_detection_started")
        gaps_and_officers = await self._detect_gaps(
            json.dumps(ledger_and_highlights.get("discovery_ledger", []), indent=2),
            json.dumps(checklist, indent=2),
            charges_text,
            facts_text,
            officers_text,
            docs_text,
        )

        # ── Pass 4: Request Tracking, Timeline & Compliance Audit ─────
        self.log_action("pass4_compliance_audit_started")
        compliance = await self._build_compliance_report(
            json.dumps(ledger_and_highlights.get("discovery_ledger", []), indent=2),
            json.dumps(checklist, indent=2),
            json.dumps(gaps_and_officers.get("gaps", []), indent=2),
            requests_text,
            timeline_text,
            case_id,
            jurisdiction,
        )

        # ── Pass 5: Draft Demand Letter & Motion to Compel ────────────
        self.log_action("pass5_drafting_started")
        drafts = await self._draft_legal_documents(
            json.dumps(gaps_and_officers.get("gaps", []), indent=2),
            charges_text,
            requests_text,
            jurisdiction,
        )

        # ── Assemble output ───────────────────────────────────────────
        output = {
            "discovery_ledger": ledger_and_highlights.get("discovery_ledger", []),
            "checklist": checklist,
            "gaps": gaps_and_officers.get("gaps", []),
            "discovery_requests": compliance.get("discovery_requests", []),
            "timeline": compliance.get("timeline", []),
            "officer_records": gaps_and_officers.get("officer_records", []),
            "compliance_report": compliance.get("compliance_report"),
            "draft_demand_letter": (
                "DRAFT — ATTORNEY REVIEW REQUIRED\n\n" + drafts.get("draft_demand_letter", "")
            ),
            "draft_motion_to_compel": (
                "DRAFT — ATTORNEY REVIEW REQUIRED\n\n" + drafts.get("draft_motion_to_compel", "")
            ),
            "client_summary": compliance.get("client_summary", ""),
            "exculpatory_highlights": ledger_and_highlights.get("exculpatory_highlights", []),
        }

        # ── Compute confidence ────────────────────────────────────────
        confidence = self._compute_confidence(
            discovery_docs,
            checklist,
            gaps_and_officers.get("gaps", []),
        )

        self.log_action(
            "disclosure_tracking_completed",
            {
                "ledger_items": len(output["discovery_ledger"]),
                "checklist_items": len(output["checklist"]),
                "gaps_found": len(output["gaps"]),
                "confidence": confidence,
            },
        )

        return self.wrap_output(output, confidence=confidence)

    # ======================================================================
    # Pass 1: Document Classification & Exculpatory Highlights
    # ======================================================================

    async def _classify_documents(
        self,
        docs_text: str,
        charges_text: str,
        facts_text: str,
    ) -> dict[str, Any]:
        """Ingest discovery documents, classify each, and flag exculpatory language."""

        result = await call_model(
            ModelCallRequest(
                prompt=_CLASSIFY.text.format(
                    charges_text=charges_text,
                    docs_text=docs_text,
                    facts_text=facts_text,
                ),
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=DocumentClassificationResult,
                prompt_id=_CLASSIFY.id,
                prompt_version=compose_version(_SYSTEM, _CLASSIFY),
                agent_id=self.agent_id,
            )
        )
        return result.data.model_dump(mode="json")

    # ======================================================================
    # Pass 2: Dynamic Checklist Generation
    # ======================================================================

    async def _generate_checklist(
        self,
        charges_text: str,
        case_type: str,
        facts_text: str,
        officers_text: str,
        jurisdiction: str,
    ) -> list[dict[str, Any]]:
        """Generate a case-specific Brady/Giglio/Jencks checklist."""

        result = await call_model(
            ModelCallRequest(
                prompt=_CHECKLIST.text.format(
                    case_type=case_type,
                    charges_text=charges_text,
                    facts_text=facts_text,
                    jurisdiction=jurisdiction,
                    officers_text=officers_text,
                ),
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=DisclosureChecklist,
                prompt_id=_CHECKLIST.id,
                prompt_version=compose_version(_SYSTEM, _CHECKLIST),
                agent_id=self.agent_id,
            )
        )
        return [item.model_dump(mode="json") for item in result.data.items]

    # ======================================================================
    # Pass 3: Gap Detection & Red Flag Analysis
    # ======================================================================

    async def _detect_gaps(
        self,
        ledger_text: str,
        checklist_text: str,
        charges_text: str,
        facts_text: str,
        officers_text: str,
        docs_text: str,
    ) -> dict[str, Any]:
        """Cross-reference ledger against checklist to find disclosure gaps."""

        result = await call_model(
            ModelCallRequest(
                prompt=_GAPS.text.format(
                    charges_text=charges_text,
                    checklist_text=checklist_text,
                    docs_text=docs_text,
                    facts_text=facts_text,
                    ledger_text=ledger_text,
                    officers_text=officers_text,
                ),
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=GapAnalysis,
                prompt_id=_GAPS.id,
                prompt_version=compose_version(_SYSTEM, _GAPS),
                agent_id=self.agent_id,
            )
        )
        return result.data.model_dump(mode="json")

    # ======================================================================
    # Pass 4: Compliance Report, Request Tracking & Timeline
    # ======================================================================

    async def _build_compliance_report(
        self,
        ledger_text: str,
        checklist_text: str,
        gaps_text: str,
        requests_text: str,
        timeline_text: str,
        case_id: str,
        jurisdiction: str,
    ) -> dict[str, Any]:
        """Build the compliance report, request tracker, and timeline."""

        result = await call_model(
            ModelCallRequest(
                prompt=_COMPLIANCE.text.format(
                    case_id=case_id,
                    checklist_text=checklist_text,
                    gaps_text=gaps_text,
                    jurisdiction=jurisdiction,
                    ledger_text=ledger_text,
                    requests_text=requests_text,
                    timeline_text=timeline_text,
                ),
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=ComplianceBundle,
                prompt_id=_COMPLIANCE.id,
                prompt_version=compose_version(_SYSTEM, _COMPLIANCE),
                agent_id=self.agent_id,
            )
        )
        return result.data.model_dump(mode="json")

    # ======================================================================
    # Pass 5: Draft Legal Documents
    # ======================================================================

    async def _draft_legal_documents(
        self,
        gaps_text: str,
        charges_text: str,
        requests_text: str,
        jurisdiction: str,
    ) -> dict[str, Any]:
        """Draft a Brady demand letter and Motion to Compel if warranted."""

        result = await call_model(
            ModelCallRequest(
                prompt=_DRAFTS.text.format(
                    charges_text=charges_text,
                    gaps_text=gaps_text,
                    jurisdiction=jurisdiction,
                    requests_text=requests_text,
                ),
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=DiscoveryDrafts,
                prompt_id=_DRAFTS.id,
                prompt_version=compose_version(_SYSTEM, _DRAFTS),
                agent_id=self.agent_id,
            )
        )
        return result.data.model_dump(mode="json")

    # ======================================================================
    # Confidence computation
    # ======================================================================

    def _compute_confidence(
        self,
        discovery_docs: list[dict[str, Any]],
        checklist: list[dict[str, Any]],
        gaps: list[dict[str, Any]],
    ) -> float:
        """Compute overall confidence score for the disclosure analysis.

        Factors:
        - Number of documents analyzed (more = higher base)
        - Checklist completeness
        - Number of critical gaps (more critical gaps = lower confidence
          in prosecution compliance, but higher confidence in our analysis)
        """
        base = 0.55

        # More documents analyzed → better coverage
        doc_count = len(discovery_docs)
        if doc_count >= 10:
            base += 0.15
        elif doc_count >= 5:
            base += 0.10
        elif doc_count >= 1:
            base += 0.05

        # Checklist generation quality
        checklist_count = len(checklist) if isinstance(checklist, list) else 0
        if checklist_count >= 15:
            base += 0.10
        elif checklist_count >= 10:
            base += 0.07
        elif checklist_count >= 5:
            base += 0.03

        # Gap detection quality — finding gaps is good analysis
        gap_count = len(gaps) if isinstance(gaps, list) else 0
        if gap_count > 0:
            base += 0.05  # Found something to flag

        # Cap at 0.85 — disclosure tracking is inherently uncertain
        # because we can't know what we don't know
        return min(base, 0.85)
