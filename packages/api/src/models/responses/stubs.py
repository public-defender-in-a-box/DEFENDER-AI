"""Response models for the stub agents' single prompts.

The stubs are the naive single-prompt baseline (PHASE_1_MODEL_GATEWAY.md §9.5); their
prompts described these fields loosely, and these models pin them down.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


# --- Case Prep Conductor ---------------------------------------------------------


class DecisionPoint(BaseModel):
    id: str
    description: str
    options: list[str]
    recommendation: str
    human_required: bool


class AttorneyTask(BaseModel):
    id: str
    task: str
    priority: Literal["URGENT", "HIGH", "MEDIUM", "LOW"]
    deadline: str | None
    category: str


class CasePrepMemo(BaseModel):
    case_theory: str
    preparation_memo: str
    decision_points: list[DecisionPoint]
    attorney_task_list: list[AttorneyTask]


# --- Case Law Agent ---------------------------------------------------------------


class Authority(BaseModel):
    case_name: str
    citation: str
    court: str
    year: str
    holding: str
    relevance: str
    favorable: bool
    factual_similarity: str
    verification_status: Literal["VERIFIED", "UNVERIFIED"]
    distinguishing_factors: list[str]


class CaseLawResearch(BaseModel):
    authorities: list[Authority]
    circuit_splits: list[str]
    recommended_citations: list[str]


# --- Citation Verifier ------------------------------------------------------------


class VerifiedCitation(BaseModel):
    citation: str
    status: Literal["CONFIRMED", "UNCONFIRMED", "OVERRULED", "SUPERSEDED"]
    shepard_signal: str
    notes: str


class CitationCheck(BaseModel):
    verified_citations: list[VerifiedCitation]
    statute_alerts: list[str]


# --- Statute Agent ----------------------------------------------------------------


class StatuteAnalysis(BaseModel):
    statute_section: str
    full_text: str
    elements_breakdown: list[str]
    related_statutes: list[str]
    sentencing_guidelines: str
    mandatory_minimums: str
    diversion_eligibility: str
    verification_status: Literal["VERIFIED", "UNVERIFIED"]


class StatuteResearch(BaseModel):
    statutes: list[StatuteAnalysis]
    procedural_statutes: list[str]
    enhancement_statutes: list[str]
