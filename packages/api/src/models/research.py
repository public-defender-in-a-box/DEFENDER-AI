"""Data models for research agents: Statute, Case Law, Citation Verification."""

from __future__ import annotations

from pydantic import BaseModel


class StatuteEntry(BaseModel):
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
    case_name: str
    citation: str
    court: str
    year: int
    holding: str
    relevance: str
    favorable: bool
    factual_similarity: str  # HIGH, MEDIUM, LOW
    verification_status: str  # VERIFIED, UNVERIFIED
    distinguishing_factors: list[str] = []


class CaseLawOutput(BaseModel):
    authorities: list[CaseAuthority]
    circuit_splits: list[str] = []
    recommended_citations: list[str] = []


class VerifiedCitation(BaseModel):
    citation: str
    status: str  # CONFIRMED, UNCONFIRMED, OVERRULED, SUPERSEDED
    shepard_signal: str | None = None
    notes: str = ""


class StatuteAlert(BaseModel):
    statute_section: str
    alert: str
    amendment_date: str | None = None


class CitationVerificationOutput(BaseModel):
    verified_citations: list[VerifiedCitation]
    statute_alerts: list[StatuteAlert] = []
