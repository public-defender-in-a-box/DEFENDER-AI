"""Data models for the Rights Violation Scanner agent."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RightsViolation(BaseModel):
    """A single identified constitutional rights violation."""

    id: str
    amendment: str  # 4TH, 5TH, 6TH, 8TH
    category: str
    description: str
    severity: str  # CRITICAL, SIGNIFICANT, MODERATE, MINOR
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_facts: list[str] = []
    source: str  # ARREST_REPORT, CLIENT_NARRATIVE, OFFICER_CONDUCT, CROSS_REFERENCE
    legal_standard: str = ""
    relevant_case_law: list[str] = []
    suppression_potential: str = ""  # HIGH, MEDIUM, LOW


class DiscrepancyItem(BaseModel):
    """A discrepancy between officer account and client narrative."""

    id: str
    topic: str
    officer_account: str
    client_account: str
    significance: str  # CRITICAL, NOTABLE, MINOR
    possible_explanations: list[str] = []
    defense_relevance: str = ""


class SuppressionViability(BaseModel):
    """Assessment of evidence suppression viability."""

    score: int = Field(ge=0, le=100)
    confidence: float = Field(ge=0.0, le=1.0)
    basis: list[str] = []
    risks: list[str] = []
    recommended_motions: list[str] = []


class MirandaAnalysis(BaseModel):
    """Detailed analysis of Miranda rights compliance."""

    miranda_given: bool | None = None  # None = unknown
    timing: str = ""  # BEFORE_QUESTIONING, DURING_QUESTIONING, AFTER_QUESTIONING, NOT_GIVEN, UNKNOWN
    custodial: bool | None = None
    statements_before_miranda: list[str] = []
    statements_after_miranda: list[str] = []
    waiver_validity: str = ""  # VALID, QUESTIONABLE, INVALID, UNKNOWN
    suppression_basis: str = ""


class SearchAnalysis(BaseModel):
    """Detailed analysis of search and seizure."""

    search_occurred: bool = False
    warrant_present: bool | None = None
    probable_cause_articulated: str = ""
    consent_given: bool | None = None
    consent_voluntariness: str = ""  # VOLUNTARY, COERCED, QUESTIONABLE, NOT_APPLICABLE
    scope_exceeded: bool | None = None
    exigent_circumstances_claimed: bool = False
    plain_view_claimed: bool = False
    search_incident_to_arrest: bool = False
    vehicle_exception: bool = False
    evidence_found: list[str] = []
    suppression_basis: str = ""


class SixthAmendmentAnalysis(BaseModel):
    """Analysis of Sixth Amendment protections."""

    counsel_requested: bool | None = None
    counsel_provided: bool | None = None
    counsel_denied_or_delayed: bool = False
    lineup_conducted: bool = False
    lineup_procedural_issues: list[str] = []
    speedy_trial_concerns: str = ""
    confrontation_issues: list[str] = []


class EighthAmendmentAnalysis(BaseModel):
    """Analysis of Eighth Amendment protections."""

    excessive_bail: bool | None = None
    bail_amount: str = ""
    bail_proportionality: str = ""
    excessive_force: bool | None = None
    force_description: str = ""
    cruel_conditions: list[str] = []


class RightsScannerInput(BaseModel):
    """Input for the Rights Violation Scanner."""

    arrest_report: str = ""
    client_narrative: str = ""
    officer_conduct: str = ""
    charges: list[dict] = Field(default_factory=list)
    pre_interview_flags: list[str] = Field(default_factory=list)


class RightsScannerOutput(BaseModel):
    """Full output of the Rights Violation Scanner."""

    violations: list[RightsViolation] = []
    discrepancy_report: list[DiscrepancyItem] = []
    suppression_viability: SuppressionViability = Field(
        default_factory=lambda: SuppressionViability(score=0, confidence=0.0)
    )
    miranda_analysis: MirandaAnalysis = Field(default_factory=MirandaAnalysis)
    search_analysis: SearchAnalysis = Field(default_factory=SearchAnalysis)
    sixth_amendment_analysis: SixthAmendmentAnalysis = Field(
        default_factory=SixthAmendmentAnalysis
    )
    eighth_amendment_analysis: EighthAmendmentAnalysis = Field(
        default_factory=EighthAmendmentAnalysis
    )
    total_violations_found: int = 0
    critical_violations: int = 0
    attorney_flags: list[str] = []
