"""Data models for attorney prep agents: Motions, Brady, Plea/Trial, Sentencing."""

from __future__ import annotations

from pydantic import BaseModel


class DraftMotion(BaseModel):
    id: str
    type: str  # SUPPRESS, DISMISS, BAIL_REDUCTION, DISCOVERY, LIMINE, OTHER
    title: str
    draft: str
    status: str = "DRAFT"
    filing_deadline: str | None = None
    supporting_authority: list[str] = []


class MotionDrafterOutput(BaseModel):
    motions: list[DraftMotion]


class BradyGap(BaseModel):
    id: str
    category: str  # MISSING_REPORT, MISSING_FORENSIC, GIGLIO, CI_FILE, etc.
    description: str
    expected_evidence: str
    basis: str


class GiglioEntry(BaseModel):
    officer: str
    disciplinary_record_requested: bool = False
    status: str = ""


class BradyAnalysisOutput(BaseModel):
    gaps: list[BradyGap]
    giglio_checklist: list[GiglioEntry] = []
    draft_demand_letter: str = ""


class PleaTrialOutput(BaseModel):
    plea_scenario: dict
    trial_scenario: dict
    comparison_matrix: dict
    risk_factors: list[str] = []
    recommendation: str = ""  # Always prefixed with DECISION SUPPORT ONLY


class SentencingOutput(BaseModel):
    guideline_range: dict
    departure_arguments: list[dict] = []
    mitigation_narrative: str = ""
    alternatives: list[dict] = []
    comparable_sentences: list[dict] = []
    memo_framework: str = ""
