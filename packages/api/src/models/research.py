"""Data models for research agents.

Covers GA Criminal Case Law, Constitutional Case Law, GA Statutes,
and Citation Verification agents.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# GA Criminal Case Law Agent (Agent 1)
# ---------------------------------------------------------------------------


class CaseResult(BaseModel):
    """A single case found during case law research."""

    case_name: str
    citation: str
    court: str
    date: str
    holding: str
    factual_similarity: str  # high, medium, low
    similarity_explanation: str
    favorable: bool
    relevance_to_client: str
    source: str  # COURTLISTENER, GOOGLE_SCHOLAR
    source_url: str = ""
    verification_status: str = "PENDING"


class LegalIssueResearch(BaseModel):
    """Research results for a single legal issue."""

    legal_issue: str
    issue_source: str  # charge, rights_violation_flag, defense_theory
    queries_run: list[str] = []
    cases_found: list[CaseResult] = []


class GACriminalCaseLawOutput(BaseModel):
    """Full output of the GA Criminal Case Law Agent."""

    research_results: list[LegalIssueResearch] = []


# ---------------------------------------------------------------------------
# Constitutional Law Case Law Agent (Agent 2)
# ---------------------------------------------------------------------------


class ConstitutionalAuthority(BaseModel):
    """A single case in the constitutional authority hierarchy."""

    case_name: str
    citation: str
    court: str
    date: str = ""
    holding: str
    source: str  # KNOWN_AUTHORITY, COURTLISTENER, GOOGLE_SCHOLAR
    source_url: str = ""
    verification_status: str = "PENDING"


class ConstitutionalIssueResearch(BaseModel):
    """Research on a single constitutional issue with full doctrinal framework."""

    amendment: str  # fourth_amendment, fifth_amendment, sixth_amendment, fourteenth_amendment
    issue: str
    legal_standard: str
    foundational_authority: list[ConstitutionalAuthority] = []
    circuit_authority: list[ConstitutionalAuthority] = []
    state_authority: list[ConstitutionalAuthority] = []
    application_to_client: str = ""
    strength_assessment: str = ""  # strong, moderate, weak
    strength_explanation: str = ""


class ConstitutionalCaseLawOutput(BaseModel):
    """Full output of the Constitutional Law Case Law Agent."""

    constitutional_research: list[ConstitutionalIssueResearch] = []


# ---------------------------------------------------------------------------
# GA Criminal Statutes Agent (Agent 3)
# ---------------------------------------------------------------------------


class StatuteElement(BaseModel):
    """A single element of an offense."""

    element: str
    definition: str
    document_support: str = ""


class PenaltyInfo(BaseModel):
    """Penalty range for an offense."""

    imprisonment_range: str = ""
    fine_range: str = ""
    mandatory_minimum: str = "none"
    probation_eligible: bool = True


class ChargedOffense(BaseModel):
    """Statutory analysis of a single charged offense."""

    statute: str
    title: str
    full_text: str = ""
    elements: list[StatuteElement] = []
    lesser_included: list[str] = []
    penalties: PenaltyInfo = Field(default_factory=PenaltyInfo)


class DiversionOption(BaseModel):
    """A diversion or alternative sentencing option."""

    program: str
    statute: str
    eligibility_requirements: str = ""
    client_eligible: str = "unknown"  # likely, unlikely, unknown
    eligibility_notes: str = ""
    benefits: str = ""
    risks: str = ""


class ProceduralRequirement(BaseModel):
    """A procedural deadline or requirement."""

    requirement: str
    statute: str
    deadline: str = ""
    notes: str = ""


class GAStatutesOutput(BaseModel):
    """Full output of the GA Criminal Statutes Agent."""

    charged_offenses: list[ChargedOffense] = []
    diversion_options: list[DiversionOption] = []
    procedural_requirements: list[ProceduralRequirement] = []
    recent_amendments: list[str] = []


# ---------------------------------------------------------------------------
# Citation Verification Agent (Agent 4)
# ---------------------------------------------------------------------------


class CitationVerificationResult(BaseModel):
    """Verification result for a single citation."""

    original_citation: str
    citation_type: str  # case, statute
    source_agent: str
    verification_status: str  # VERIFIED, UNVERIFIED, OVERRULED, SUPERSEDED,
    #                           DISTINGUISHED, HOLDING_MISMATCH, CITATION_ERROR
    verification_method: str = ""
    good_law_status: str = ""  # GOOD_LAW, OVERRULED, SUPERSEDED, QUESTIONED
    negative_treatment: list[str] = []
    confidence: float = 0.0
    notes: str = ""


class VerificationSummary(BaseModel):
    """Aggregate summary of all verification results."""

    total_citations: int = 0
    verified: int = 0
    unverified: int = 0
    holding_mismatch: int = 0
    overruled: int = 0
    superseded: int = 0
    citation_errors: int = 0


class CitationVerificationOutput(BaseModel):
    """Full output of the Citation Verification Agent."""

    verification_results: list[CitationVerificationResult] = []
    summary: VerificationSummary = Field(default_factory=VerificationSummary)


# ---------------------------------------------------------------------------
# Research Orchestrator combined output
# ---------------------------------------------------------------------------


class ResearchCostReport(BaseModel):
    """Cost breakdown for the research pipeline."""

    ga_case_law_cost: float = 0.0
    constitutional_cost: float = 0.0
    statutes_cost: float = 0.0
    verification_cost: float = 0.0
    courtlistener_calls: int = 0
    total_cost: float = 0.0


class CombinedResearchOutput(BaseModel):
    """Combined output from all research agents after verification."""

    ga_criminal_case_law: GACriminalCaseLawOutput = Field(
        default_factory=GACriminalCaseLawOutput
    )
    constitutional_case_law: ConstitutionalCaseLawOutput = Field(
        default_factory=ConstitutionalCaseLawOutput
    )
    ga_statutes: GAStatutesOutput = Field(default_factory=GAStatutesOutput)
    citation_verification: CitationVerificationOutput = Field(
        default_factory=CitationVerificationOutput
    )
    cost_report: ResearchCostReport = Field(default_factory=ResearchCostReport)


# ---------------------------------------------------------------------------
# Legacy aliases for backward compatibility with existing imports
# ---------------------------------------------------------------------------


class StatuteEntry(BaseModel):
    """Legacy model — use ChargedOffense for new code."""

    statute_section: str
    full_text: str
    elements_breakdown: list[str]
    related_statutes: list[str] = []
    sentencing_guidelines: str = ""
    mandatory_minimums: str | None = None
    diversion_eligibility: str = ""
    last_amended: str | None = None
    verification_status: str = "VERIFIED"


class StatuteAnalysisOutput(BaseModel):
    statutes: list[StatuteEntry]
    procedural_statutes: list[str] = []
    enhancement_statutes: list[str] = []


class CaseAuthority(BaseModel):
    """Legacy model — use CaseResult for new code."""

    case_name: str
    citation: str
    court: str
    year: int
    holding: str
    relevance: str
    favorable: bool
    factual_similarity: str
    verification_status: str
    distinguishing_factors: list[str] = []


class CaseLawOutput(BaseModel):
    authorities: list[CaseAuthority]
    circuit_splits: list[str] = []
    recommended_citations: list[str] = []


class VerifiedCitation(BaseModel):
    citation: str
    status: str
    shepard_signal: str | None = None
    notes: str = ""


class StatuteAlert(BaseModel):
    statute_section: str
    alert: str
    amendment_date: str | None = None
