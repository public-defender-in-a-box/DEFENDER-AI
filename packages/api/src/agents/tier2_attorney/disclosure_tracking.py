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
from src.services.llm_service import call_llm

logger = logging.getLogger(__name__)


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

        prompt = f"""You are a discovery analyst for a public defender's office.

TASK: Classify each discovery document and identify any exculpatory,
impeachment, or Jencks material. Flag any buried exculpatory language.

DISCOVERY DOCUMENTS RECEIVED:
{docs_text}

CHARGES:
{charges_text}

CLIENT'S ACCOUNT (from intake):
{facts_text}

Return JSON with exactly these keys:

1. "discovery_ledger": array of objects, each with:
   - "id": unique string (e.g., "DL-001")
   - "document_name": string
   - "category": one of POLICE_REPORT, WITNESS_STATEMENT, LAB_REPORT,
     BODYCAM_FOOTAGE, SURVEILLANCE_FOOTAGE, DISPATCH_RECORDING, PHOTO_ARRAY,
     LINEUP_RECORD, FORENSIC_EVIDENCE, INFORMANT_AGREEMENT, OFFICER_DISCIPLINARY,
     PRIOR_STATEMENT, CRIMINAL_HISTORY, COOPERATION_AGREEMENT, SEARCH_WARRANT,
     COURT_ORDER, MEDICAL_RECORD, FINANCIAL_RECORD, PHONE_RECORD,
     DIGITAL_EVIDENCE, CHAIN_OF_CUSTODY, EXPERT_REPORT, OTHER
   - "source": who provided it
   - "received_date": ISO date or "unknown"
   - "disclosure_types": array of "BRADY", "GIGLIO", and/or "JENCKS" as applicable
   - "page_count": number or null
   - "summary": brief description of contents
   - "flags": array of strings for any notable items (exculpatory language found,
     missing pages, inconsistencies, etc.)
   - "confidence": 0.0 to 1.0

2. "exculpatory_highlights": array of strings — any exculpatory or impeachment
   language found in the documents. Quote the exact language and cite the
   document and approximate location (e.g., "Police report p.8: 'witness
   stated she was not certain of identification'").

Return valid JSON only."""

        return await call_llm(prompt)

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

        prompt = f"""You are a Brady compliance specialist for a public defender.

TASK: Generate a comprehensive, case-specific disclosure checklist. The
checklist should adapt based on the charges and case facts.

CASE TYPE: {case_type}
JURISDICTION: {jurisdiction}

CHARGES:
{charges_text}

CASE FACTS:
{facts_text}

OFFICERS INVOLVED:
{officers_text}

For each charge type and fact pattern, generate the appropriate checklist
items. Examples:
- If eyewitness ID is involved → photo array procedures, lineup records
- If informant mentioned → cooperation agreements, compensation records
- If forensic evidence → lab analyst credentials, chain of custody, error history
- If bodycam/surveillance mentioned → footage production
- Always include: officer disciplinary records, 911 recordings, dispatch logs,
  prior inconsistent statements of witnesses

Return JSON: an array of objects, each with:
- "id": unique string (e.g., "CK-001")
- "description": what evidence is expected
- "material_type": "BRADY", "GIGLIO", or "JENCKS"
- "status": "PENDING" (initial default for all)
- "triggered_by": what case fact triggered this item
- "related_ledger_entries": empty array (to be populated later)
- "notes": any additional context

Generate at least 10 items. Be thorough — missing a Brady item can mean
a wrongful conviction.

Return valid JSON array only."""

        return await call_llm(prompt)

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

        prompt = f"""You are a Brady/Giglio gap detection analyst for a public defender.

TASK: Cross-reference what has been disclosed against what should exist.
Identify every gap, red flag, and potential violation.

DISCOVERY LEDGER (what we've received):
{ledger_text}

CHECKLIST (what should exist):
{checklist_text}

CHARGES:
{charges_text}

CASE FACTS:
{facts_text}

OFFICERS INVOLVED:
{officers_text}

RAW DOCUMENTS:
{docs_text}

GAP DETECTION RULES:
- If a police report mentions footage but no footage produced → FLAG
- If a witness has prior convictions and no Giglio notice filed → FLAG
- If an informant is listed but no cooperation agreement disclosed → FLAG
- If officer names appear with no disciplinary record check → FLAG
- If lab results referenced but no chain of custody → FLAG
- If report mentions additional witnesses not on witness list → FLAG
- If 911 call referenced but recording not produced → FLAG
- Cross-reference officer names for patterns of misconduct
- Look for implicit disclosure triggers (CI nicknames, references to
  "the source", informant indicators)

Return JSON with exactly these keys:

1. "gaps": array of objects, each with:
   - "id": unique string (e.g., "GAP-001")
   - "material_type": "BRADY", "GIGLIO", or "JENCKS"
   - "severity": "CRITICAL", "HIGH", "MEDIUM", or "LOW"
   - "description": what is missing
   - "expected_evidence": what specifically should exist
   - "basis": legal/factual basis for expecting this evidence
   - "source_reference": what document or fact triggered this detection
   - "suggested_action": recommended next step (e.g., "File Motion to Compel",
     "Send targeted Brady demand letter")
   - "related_checklist_items": array of checklist item IDs

2. "officer_records": array of objects, each with:
   - "name": officer name
   - "badge_number": if available
   - "agency": department
   - "disciplinary_record_requested": false (default)
   - "disciplinary_record_status": "not_requested"
   - "prior_case_flags": array of any flags
   - "giglio_relevant": true/false

Return valid JSON only."""

        return await call_llm(prompt)

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

        prompt = f"""You are a Brady compliance auditor for a public defender.

TASK: Build a comprehensive compliance report, update discovery request
tracking, construct a disclosure timeline, and produce a plain-language
client summary.

CASE ID: {case_id}
JURISDICTION: {jurisdiction}

DISCOVERY LEDGER:
{ledger_text}

DISCLOSURE CHECKLIST:
{checklist_text}

IDENTIFIED GAPS:
{gaps_text}

PRIOR DISCOVERY REQUESTS:
{requests_text}

CASE TIMELINE DATES:
{timeline_text}

JURISDICTION RULES (Georgia):
- O.C.G.A. § 17-16-1 et seq. (Georgia Criminal Discovery)
- Brady v. Maryland, 373 U.S. 83 (1963)
- Giglio v. United States, 405 U.S. 150 (1972)
- Jencks v. United States, 353 U.S. 657 (1957)
- Georgia deadline: prosecution must disclose within 10 days of demand
- Motion to Compel deadline: before trial or as court directs

Return JSON with exactly these keys:

1. "discovery_requests": array of request objects, each with:
   - "id": unique string (e.g., "REQ-001")
   - "date_sent": ISO date
   - "method": how sent
   - "items_requested": array of strings
   - "recipient": who received
   - "status": "SENT", "ACKNOWLEDGED", "PARTIALLY_FULFILLED", "FULFILLED",
     "DENIED", "NO_RESPONSE", or "MOTION_FILED"
   - "response_date": ISO date or null
   - "response_summary": text
   - "deadline": ISO date or null
   - "escalation_notes": any notes on overdue items

2. "timeline": array of event objects, each with:
   - "date": ISO date
   - "description": what happened
   - "event_type": "arraignment", "discovery_received", "request_sent",
     "response_received", "motion_filed", "deadline", "trial_date", "alert"
   - "is_alert": true if this is a warning (overdue, approaching deadline)
   - "related_ids": array of related IDs

3. "compliance_report": object with:
   - "case_id": string
   - "generated_at": ISO datetime
   - "total_items_tracked": number
   - "items_received": number
   - "items_outstanding": number
   - "unresolved_gaps": array of gap IDs
   - "suggested_motions": array of motion types to file
   - "compliance_assessment": plain-language summary of disclosure status
   - "appellate_preservation_notes": what to preserve for appeal
   - "attorney_action_items": array of specific next steps

4. "client_summary": a plain-language paragraph summarizing the disclosure
   status for the client. Use simple language. Example: "The prosecution has
   provided most of the evidence in your case, but your attorney has requested
   the bodycam footage from your arrest, which has not been turned over yet."

Return valid JSON only."""

        return await call_llm(prompt)

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

        prompt = f"""You are a public defender drafting discovery enforcement documents.

TASK: Based on the identified disclosure gaps, draft:
1. A targeted Brady/Giglio demand letter to the prosecution
2. A Motion to Compel (if there are overdue or denied requests)

JURISDICTION: {jurisdiction}

IDENTIFIED GAPS:
{gaps_text}

CHARGES:
{charges_text}

PRIOR REQUESTS SENT:
{requests_text}

LEGAL CITATIONS TO INCLUDE:
- Brady v. Maryland, 373 U.S. 83 (1963)
- Giglio v. United States, 405 U.S. 150 (1972)
- Jencks v. United States, 353 U.S. 657 (1957)
- Kyles v. Whitley, 514 U.S. 419 (1995) (cumulative materiality)
- Strickler v. Greene, 527 U.S. 263 (1999) (suppression element)
- O.C.G.A. § 17-16-1 et seq. (Georgia criminal discovery)
- O.C.G.A. § 17-16-6 (prosecution disclosure obligations)
- O.C.G.A. § 17-16-8 (sanctions for noncompliance)

For the demand letter:
- Address to the assigned prosecutor
- Cite specific gaps with legal authority
- Set a reasonable deadline (10 days per Georgia rules)
- Note preservation obligations

For the Motion to Compel:
- Standard Georgia motion format
- Specific items sought
- Good cause showing
- Proposed order

Return JSON with:
1. "draft_demand_letter": full text of the letter
2. "draft_motion_to_compel": full text of the motion

Both MUST begin with the text exactly as provided — the caller will prepend
the "DRAFT — ATTORNEY REVIEW REQUIRED" header.

Return valid JSON only."""

        return await call_llm(prompt)

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
