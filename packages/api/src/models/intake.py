"""Data models for the Intake Conductor and sub-agents."""

from __future__ import annotations

from pydantic import BaseModel


class TargetedQuestion(BaseModel):
    question: str
    relevant_charge_id: str
    relevant_element: str
    priority: str  # MUST_ASK, SHOULD_ASK, IF_TIME


class IntakeConductorInput(BaseModel):
    pre_interview_brief: dict
    client_session: dict


class IntakeMessage(BaseModel):
    id: str
    timestamp: str
    sender: str  # SYSTEM, CLIENT
    content: str
    generated_by: str | None = None
    target_element: str | None = None


class IntakeFactItem(BaseModel):
    id: str
    category: str  # ARREST_TIMELINE, WITNESS, EVIDENCE, OFFICER_CONDUCT, RIGHTS, PERSONAL, OTHER
    statement: str
    confidence: str  # HIGH, MEDIUM, LOW
    source_message_ids: list[str] = []
    contradicts: list[str] | None = None


class InconsistencyFlag(BaseModel):
    id: str
    client_statement: str
    document_statement: str
    severity: str  # CRITICAL, NOTABLE, MINOR
    possible_explanations: list[str] = []


class PersonalCircumstancesData(BaseModel):
    citizenship: str = ""
    employment_status: str = ""
    housing_status: str = ""
    dependents: int = 0
    mental_health_history: str | None = None
    substance_abuse_history: str | None = None
    military_service: bool = False
    education_status: str = ""
    prior_record_self_report: str = ""


class IntakeSummaryOutput(BaseModel):
    session_id: str
    completed_at: str
    completion_percentage: float
    facts: list[IntakeFactItem]
    inconsistencies: list[InconsistencyFlag]
    personal_circumstances: PersonalCircumstancesData
    unanswered_questions: list[dict] = []
    transcript: list[IntakeMessage] = []
