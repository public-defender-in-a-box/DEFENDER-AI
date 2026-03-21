"""Canonical CaseState — single source of truth for every case."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field


class PipelineStage(str, Enum):
    CREATED = "CREATED"
    CHARGES_PROCESSING = "CHARGES_PROCESSING"
    CHARGES_PROCESSED = "CHARGES_PROCESSED"
    PRE_INTERVIEW_RESEARCH = "PRE_INTERVIEW_RESEARCH"
    PRE_INTERVIEW_COMPLETE = "PRE_INTERVIEW_COMPLETE"
    INTAKE_IN_PROGRESS = "INTAKE_IN_PROGRESS"
    INTAKE_COMPLETE = "INTAKE_COMPLETE"
    CASE_PREP_IN_PROGRESS = "CASE_PREP_IN_PROGRESS"
    CASE_PREP_COMPLETE = "CASE_PREP_COMPLETE"
    ATTORNEY_REVIEW = "ATTORNEY_REVIEW"
    ATTORNEY_APPROVED = "ATTORNEY_APPROVED"


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNRATED = "UNRATED"


class VerificationStatus(str, Enum):
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    CONFIRMED = "CONFIRMED"
    UNCONFIRMED = "UNCONFIRMED"
    OVERRULED = "OVERRULED"
    SUPERSEDED = "SUPERSEDED"


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "PENDING_REVIEW"
    IN_REVIEW = "IN_REVIEW"
    ATTORNEY_APPROVED = "ATTORNEY_APPROVED"


T = TypeVar("T")


class ConfidenceRated(BaseModel, Generic[T]):
    data: T
    confidence: ConfidenceLevel
    source: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class StageHistoryEntry(BaseModel):
    stage: PipelineStage
    entered_at: datetime
    exited_at: datetime | None = None


class DocumentRecord(BaseModel):
    id: str
    type: str
    file_name: str
    storage_url: str
    uploaded_at: datetime


class CaseState(BaseModel):
    """The canonical case state object owned by the Orchestrator."""

    # Identity
    id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    jurisdiction: str = "IL"
    case_number: str | None = None

    # Pipeline
    stage: PipelineStage = PipelineStage.CREATED
    stage_history: list[StageHistoryEntry] = Field(default_factory=list)

    # Attorney
    attorney_id: str = ""
    attorney_config: dict[str, Any] = Field(default_factory=dict)

    # Agent outputs — all nullable, populated as pipeline progresses
    charge_processing: dict[str, Any] | None = None
    pre_interview_research: dict[str, Any] | None = None
    intake_summary: dict[str, Any] | None = None
    case_prep_memo: dict[str, Any] | None = None
    statute_analysis: dict[str, Any] | None = None
    case_law_research: dict[str, Any] | None = None
    citation_verification: dict[str, Any] | None = None
    fact_gathering: dict[str, Any] | None = None
    rights_violation_analysis: dict[str, Any] | None = None
    collateral_consequences: dict[str, Any] | None = None
    personal_circumstances: dict[str, Any] | None = None
    draft_motions: dict[str, Any] | None = None
    brady_analysis: dict[str, Any] | None = None
    plea_trial_assessment: dict[str, Any] | None = None
    sentencing_analysis: dict[str, Any] | None = None

    # Cross-cutting
    ethical_flags: list[dict[str, Any]] = Field(default_factory=list)
    audit_log: list[dict[str, Any]] = Field(default_factory=list)

    # Review
    review_status: dict[str, str] = Field(default_factory=dict)

    # Documents
    documents: list[DocumentRecord] = Field(default_factory=list)

    def advance_stage(self, new_stage: PipelineStage) -> None:
        """Move to next pipeline stage with history tracking."""
        now = datetime.utcnow()
        if self.stage_history:
            self.stage_history[-1].exited_at = now
        self.stage_history.append(StageHistoryEntry(stage=new_stage, entered_at=now))
        self.stage = new_stage
        self.updated_at = now
