"""Response models for the Rights Violation Scanner's two passes.

They reuse the scanner's domain models (src/models/rights.py); field names match the
JSON shapes in src/prompts/rights_scanner/.
"""

from __future__ import annotations

from pydantic import BaseModel

from src.models.rights import (
    DiscrepancyItem,
    EighthAmendmentAnalysis,
    MirandaAnalysis,
    RightsViolation,
    SearchAnalysis,
    SixthAmendmentAnalysis,
    SuppressionViability,
)


class DocumentScan(BaseModel):
    """Pass 1: official documents."""

    violations: list[RightsViolation]
    miranda_analysis: MirandaAnalysis
    search_analysis: SearchAnalysis
    sixth_amendment_analysis: SixthAmendmentAnalysis
    eighth_amendment_analysis: EighthAmendmentAnalysis


class MirandaUpdates(BaseModel):
    statements_before_miranda: list[str]
    waiver_validity: str
    suppression_basis: str


class SearchUpdates(BaseModel):
    consent_given: bool | None
    consent_voluntariness: str
    scope_exceeded: bool | None
    suppression_basis: str


class NarrativeCrossReference(BaseModel):
    """Pass 2: client narrative against the official record."""

    additional_violations: list[RightsViolation]
    discrepancy_report: list[DiscrepancyItem]
    miranda_updates: MirandaUpdates
    search_updates: SearchUpdates
    suppression_viability: SuppressionViability
    attorney_flags: list[str]
