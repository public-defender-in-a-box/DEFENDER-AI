"""Data models for the Disclosure Tracking Agent.

Covers Brady/Giglio/Jencks material tracking, discovery ledger management,
gap detection, request tracking, and pre-trial audit reports.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DisclosureMaterialType(str, Enum):
    """The three core constitutional disclosure categories."""

    BRADY = "BRADY"  # Exculpatory evidence (Brady v. Maryland)
    GIGLIO = "GIGLIO"  # Impeachment evidence (Giglio v. United States)
    JENCKS = "JENCKS"  # Prior witness statements (Jencks v. United States)


class DocumentCategory(str, Enum):
    """Auto-classification categories for discovery items."""

    POLICE_REPORT = "POLICE_REPORT"
    WITNESS_STATEMENT = "WITNESS_STATEMENT"
    LAB_REPORT = "LAB_REPORT"
    BODYCAM_FOOTAGE = "BODYCAM_FOOTAGE"
    SURVEILLANCE_FOOTAGE = "SURVEILLANCE_FOOTAGE"
    DISPATCH_RECORDING = "DISPATCH_RECORDING"
    PHOTO_ARRAY = "PHOTO_ARRAY"
    LINEUP_RECORD = "LINEUP_RECORD"
    FORENSIC_EVIDENCE = "FORENSIC_EVIDENCE"
    INFORMANT_AGREEMENT = "INFORMANT_AGREEMENT"
    OFFICER_DISCIPLINARY = "OFFICER_DISCIPLINARY"
    PRIOR_STATEMENT = "PRIOR_STATEMENT"
    CRIMINAL_HISTORY = "CRIMINAL_HISTORY"
    COOPERATION_AGREEMENT = "COOPERATION_AGREEMENT"
    SEARCH_WARRANT = "SEARCH_WARRANT"
    COURT_ORDER = "COURT_ORDER"
    MEDICAL_RECORD = "MEDICAL_RECORD"
    FINANCIAL_RECORD = "FINANCIAL_RECORD"
    PHONE_RECORD = "PHONE_RECORD"
    DIGITAL_EVIDENCE = "DIGITAL_EVIDENCE"
    CHAIN_OF_CUSTODY = "CHAIN_OF_CUSTODY"
    EXPERT_REPORT = "EXPERT_REPORT"
    OTHER = "OTHER"


class ChecklistItemStatus(str, Enum):
    """Status of each item on the Brady checklist."""

    PENDING = "PENDING"  # Not yet requested or received
    REQUESTED = "REQUESTED"  # Formally requested from prosecution
    RECEIVED = "RECEIVED"  # Received and logged
    PARTIALLY_RECEIVED = "PARTIALLY_RECEIVED"  # Some but not all
    DENIED = "DENIED"  # Prosecution denied existence
    NOT_APPLICABLE = "NOT_APPLICABLE"  # Documented as irrelevant
    OVERDUE = "OVERDUE"  # Request past deadline with no response
    FLAGGED = "FLAGGED"  # Gap detected — needs attorney attention


class GapSeverity(str, Enum):
    """How serious a disclosure gap is."""

    CRITICAL = "CRITICAL"  # Likely Brady violation — motion required
    HIGH = "HIGH"  # Significant gap — demand letter needed
    MEDIUM = "MEDIUM"  # Notable absence — should be requested
    LOW = "LOW"  # Minor — document for completeness


class RequestStatus(str, Enum):
    """Status of a discovery request sent to prosecution."""

    SENT = "SENT"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FULFILLED = "PARTIALLY_FULFILLED"
    FULFILLED = "FULFILLED"
    DENIED = "DENIED"
    NO_RESPONSE = "NO_RESPONSE"
    MOTION_FILED = "MOTION_FILED"  # Motion to Compel filed


# ---------------------------------------------------------------------------
# Core models
# ---------------------------------------------------------------------------


class DiscoveryLedgerEntry(BaseModel):
    """A single item in the timestamped discovery ledger."""

    id: str
    document_name: str
    category: DocumentCategory
    source: str  # Who provided it (e.g., "Fulton County DA", "APD")
    received_date: str  # ISO date string
    disclosure_types: list[DisclosureMaterialType] = []
    page_count: int | None = None
    summary: str = ""
    flags: list[str] = Field(
        default_factory=list,
        description="Auto-detected flags (e.g., 'contains exculpatory language')",
    )
    confidence: float = 0.0


class ChecklistItem(BaseModel):
    """A single item on the dynamic Brady/Giglio/Jencks checklist."""

    id: str
    description: str
    material_type: DisclosureMaterialType
    status: ChecklistItemStatus = ChecklistItemStatus.PENDING
    triggered_by: str = ""  # What case fact triggered this item
    related_ledger_entries: list[str] = Field(
        default_factory=list,
        description="IDs of discovery ledger entries that satisfy this item",
    )
    notes: str = ""


class DisclosureGap(BaseModel):
    """A detected gap in prosecutorial disclosure."""

    id: str
    material_type: DisclosureMaterialType
    severity: GapSeverity
    description: str
    expected_evidence: str
    basis: str  # Why we expect this evidence to exist
    source_reference: str = ""  # What document or fact triggered detection
    suggested_action: str = ""  # e.g., "File Motion to Compel"
    related_checklist_items: list[str] = Field(
        default_factory=list,
        description="IDs of checklist items this gap relates to",
    )


class DiscoveryRequest(BaseModel):
    """A tracked discovery request to the prosecution."""

    id: str
    date_sent: str  # ISO date
    method: str  # e.g., "formal letter", "email", "court filing"
    items_requested: list[str]
    recipient: str  # e.g., "Fulton County DA's Office"
    status: RequestStatus = RequestStatus.SENT
    response_date: str | None = None
    response_summary: str = ""
    deadline: str | None = None  # Calculated from local rules
    escalation_notes: str = ""


class TimelineEvent(BaseModel):
    """An event on the disclosure timeline."""

    date: str  # ISO date
    description: str
    event_type: str  # e.g., "discovery_received", "request_sent", "motion_filed"
    is_alert: bool = False  # Whether this is a warning/overdue item
    related_ids: list[str] = Field(
        default_factory=list,
        description="IDs of related ledger entries, requests, or gaps",
    )


class OfficerRecord(BaseModel):
    """Officer cross-reference for Giglio tracking."""

    name: str
    badge_number: str = ""
    agency: str = ""
    disciplinary_record_requested: bool = False
    disciplinary_record_status: str = ""  # e.g., "received", "pending", "none found"
    prior_case_flags: list[str] = Field(
        default_factory=list,
        description="Flags from prior cases involving this officer",
    )
    giglio_relevant: bool = False


class BradyComplianceReport(BaseModel):
    """Pre-trial Brady compliance audit report."""

    case_id: str
    generated_at: str  # ISO datetime
    total_items_tracked: int = 0
    items_received: int = 0
    items_outstanding: int = 0
    unresolved_gaps: list[str] = Field(
        default_factory=list,
        description="IDs of unresolved DisclosureGaps",
    )
    suggested_motions: list[str] = Field(
        default_factory=list,
        description="Suggested motion types to file",
    )
    compliance_assessment: str = ""  # Plain-language summary
    appellate_preservation_notes: str = ""
    attorney_action_items: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent output model
# ---------------------------------------------------------------------------


class DisclosureTrackingOutput(BaseModel):
    """Full output of the Disclosure Tracking Agent."""

    discovery_ledger: list[DiscoveryLedgerEntry] = []
    checklist: list[ChecklistItem] = []
    gaps: list[DisclosureGap] = []
    discovery_requests: list[DiscoveryRequest] = []
    timeline: list[TimelineEvent] = []
    officer_records: list[OfficerRecord] = []
    compliance_report: BradyComplianceReport | None = None
    draft_demand_letter: str = ""
    draft_motion_to_compel: str = ""
    client_summary: str = ""  # Plain-language status for client
    exculpatory_highlights: list[str] = Field(
        default_factory=list,
        description="Exculpatory language found buried in documents",
    )
