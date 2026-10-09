"""Response models for the Disclosure Tracking Agent's five passes.

They reuse the agent's domain models (src/models/disclosure.py); field names match
src/prompts/disclosure_tracking/.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.models.disclosure import (
    BradyComplianceReport,
    ChecklistItem,
    DisclosureGap,
    DiscoveryLedgerEntry,
    DiscoveryRequest,
    OfficerRecord,
    TimelineEvent,
)


class DocumentClassificationResult(BaseModel):
    discovery_ledger: list[DiscoveryLedgerEntry]
    exculpatory_highlights: list[str]


class DisclosureChecklist(BaseModel):
    """The checklist prompt asked for a bare array; v1 asks for ``{"items": [...]}``."""

    items: list[ChecklistItem]


class GapAnalysis(BaseModel):
    gaps: list[DisclosureGap]
    officer_records: list[OfficerRecord]


class ComplianceBundle(BaseModel):
    discovery_requests: list[DiscoveryRequest]
    timeline: list[TimelineEvent]
    compliance_report: BradyComplianceReport
    client_summary: str


class DiscoveryDrafts(BaseModel):
    draft_demand_letter: str
    draft_motion_to_compel: str
