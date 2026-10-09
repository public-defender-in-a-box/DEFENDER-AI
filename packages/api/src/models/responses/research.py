"""Response models for the research agents' model calls.

Field names match the JSON shapes in each agent's prompt, so agent output keeps the
shape the Research Orchestrator and Citation Verification already read.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Similarity = Literal["high", "medium", "low"]

# --- GA Criminal Case Law -----------------------------------------------------


class IssueQueries(BaseModel):
    legal_issue: str
    issue_source: Literal["charge", "rights_violation_flag", "defense_theory"]
    queries: list[str]


class QueryPlan(BaseModel):
    issue_queries: list[IssueQueries]


class AnalyzedCase(BaseModel):
    case_name: str
    citation: str
    court: str
    date: str
    holding: str
    factual_similarity: Similarity
    similarity_explanation: str
    favorable: bool
    relevance_to_client: str


class CaseAnalysis(BaseModel):
    cases: list[AnalyzedCase]


# --- Constitutional Case Law -------------------------------------------------


class FoundationalCase(BaseModel):
    case_name: str
    citation: str
    holding: str


class ConstitutionalIssue(BaseModel):
    amendment: Literal[
        "fourth_amendment", "fifth_amendment", "sixth_amendment", "fourteenth_amendment"
    ]
    issue: str
    legal_standard: str
    foundational_cases: list[FoundationalCase]
    circuit_queries: list[str]
    state_queries: list[str]


class ConstitutionalIssues(BaseModel):
    constitutional_issues: list[ConstitutionalIssue]


class Authority(BaseModel):
    case_name: str
    citation: str
    court: str
    date: str
    holding: str
    source: str
    verification_status: str


class DoctrinalFramework(BaseModel):
    circuit_authority: list[Authority]
    state_authority: list[Authority]
    application_to_client: str
    strength_assessment: Literal["strong", "moderate", "weak"]
    strength_explanation: str


# --- GA Statutes ------------------------------------------------------------


class StatuteElement(BaseModel):
    element: str
    definition: str
    document_support: str


class Penalties(BaseModel):
    imprisonment_range: str
    fine_range: str
    mandatory_minimum: str
    probation_eligible: bool


class ChargedOffense(BaseModel):
    statute: str
    title: str
    full_text: str
    elements: list[StatuteElement]
    lesser_included: list[str]
    penalties: Penalties


class StatutoryAnalysis(BaseModel):
    charged_offenses: list[ChargedOffense]


class DiversionOption(BaseModel):
    program: str
    statute: str
    eligibility_requirements: str
    client_eligible: Literal["likely", "unlikely", "unknown"]
    eligibility_notes: str
    benefits: str
    risks: str


class DiversionAnalysis(BaseModel):
    diversion_options: list[DiversionOption]


class ProceduralRequirement(BaseModel):
    requirement: str
    statute: str
    deadline: str
    notes: str


class ProceduralAnalysis(BaseModel):
    procedural_requirements: list[ProceduralRequirement]
    recent_amendments: list[str]


# --- Citation Verification ------------------------------------------------------


class HoldingCheck(BaseModel):
    matches: bool
    explanation: str
    actual_holding_summary: str


class StatuteVerification(BaseModel):
    exists: bool
    content_accurate: bool
    recently_amended: bool
    amendment_notes: str
    unconstitutional: bool
    unconstitutional_notes: str
    verification_notes: str
