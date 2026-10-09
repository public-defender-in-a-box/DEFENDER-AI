"""Response model for the Pre-Interview Research Conductor.

Field names match src/prompts/pre_interview_research/brief.v1.txt; the intake route
reads ``targeted_questions`` (priority, phase) from this shape.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Severity = Literal["high", "medium", "low"]


class TargetedQuestion(BaseModel):
    question_id: str
    question: str
    relevant_charge_id: str
    relevant_element: str
    priority: Literal["MUST_ASK", "SHOULD_ASK", "IF_TIME"]
    rationale: str
    phase: Literal[
        "personal_information",
        "incident_narrative",
        "arrest_and_custody",
        "prior_history",
        "priorities_and_concerns",
    ]


class RightsFlag(BaseModel):
    flag_id: str
    type: Literal[
        "fourth_amendment",
        "fifth_amendment",
        "sixth_amendment",
        "fourteenth_amendment",
        "speedy_trial",
        "brady",
        "other",
    ]
    description: str
    basis: str
    investigation_needed: str
    severity: Severity
    confidence: float


class KnownFact(BaseModel):
    fact_id: str
    fact: str
    source: str
    category: Literal["timeline", "location", "persons", "evidence", "procedure", "statements"]
    verify_with_client: bool
    verification_question: str
    confidence: float


class CollateralAlert(BaseModel):
    alert_id: str
    category: Literal[
        "immigration", "employment", "housing", "family", "financial", "professional_license"
    ]
    description: str
    relevant_charge: str
    intake_question: str
    severity: Severity


class ElementsToProve(BaseModel):
    charge_id: str
    offense: str
    elements: list[str]
    weakest_element: str


class DiversionAssessment(BaseModel):
    first_offender_act: str
    pretrial_diversion: str
    drug_court: str
    notes: str


class ResearchRequest(BaseModel):
    request_id: str
    type: Literal["statute_lookup", "case_law", "sentencing_data", "local_practice"]
    description: str
    priority: Severity
    relevant_charge: str


class LegalBrief(BaseModel):
    key_legal_issues: list[str]
    elements_to_prove: list[ElementsToProve]
    potential_defenses: list[str]
    diversion_eligibility: DiversionAssessment
    procedural_deadlines: list[str]
    research_requests: list[ResearchRequest]


class PreInterviewBrief(BaseModel):
    charges_summary: str
    targeted_questions: list[TargetedQuestion]
    preliminary_rights_flags: list[RightsFlag]
    known_facts_from_documents: list[KnownFact]
    collateral_consequence_alerts: list[CollateralAlert]
    legal_brief: LegalBrief
