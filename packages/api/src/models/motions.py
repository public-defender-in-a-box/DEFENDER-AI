"""Data models for attorney prep agents: Motions, Brady, Plea/Trial, Sentencing."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MotionType(str, Enum):
    SUPPRESS = "motion_to_suppress"
    BAIL_REDUCTION = "motion_for_bail_reduction"
    DISMISS = "motion_to_dismiss"
    DISCOVERY_BRADY = "discovery_brady_demand"
    LIMINE = "motion_in_limine"


class MotionSection(BaseModel):
    """A single section of a motion document."""

    heading: str
    content: str
    citations: list[str] = []  # Each citation tagged with verification status


class DraftMotion(BaseModel):
    """
    A complete draft motion. Every field is mandatory.
    The attorney will review, edit, and file — this is a 70% draft.
    """

    motion_type: MotionType
    title: str  # e.g., "MOTION TO SUPPRESS PHYSICAL EVIDENCE"
    case_caption: str
    court: str  # e.g., "IN THE SUPERIOR COURT OF CLARKE COUNTY, STATE OF GEORGIA"
    sections: list[MotionSection]
    prayer_for_relief: str
    certificate_of_service: str = ""  # Blank for attorney to complete
    filing_deadline: Optional[str] = None
    filing_deadline_basis: Optional[str] = None

    # Confidence
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: str  # HIGH, MEDIUM, LOW
    confidence_reasoning: str
    flags: list[str] = []

    # NON-NEGOTIABLE
    draft_warning: str = "DRAFT — ATTORNEY REVIEW REQUIRED"
    privilege_warning: str = "ATTORNEY-CLIENT PRIVILEGED MATERIAL"


class MotionDrafterOutput(BaseModel):
    """Complete output of the Motion Drafter Agent."""

    motions: list[DraftMotion]
    motions_not_generated: list[dict[str, str]] = []  # motion_type + reason
    overall_confidence: float
    overall_confidence_level: str
    agent_name: str = "motion_drafter"
    flags: list[str] = []
    warnings: list[str] = []


# --- Other attorney prep models (unchanged) ---


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


class MotionDraftResponse(BaseModel):
    """What the model returns for one motion (src/prompts/motion_drafter/system.v1.txt).

    The Motion Drafter adds the motion type, its own confidence score and flags, and
    the fixed warnings to build a ``DraftMotion``.
    """

    title: str
    case_caption: str
    court: str
    sections: list[MotionSection]
    prayer_for_relief: str
    filing_deadline: Optional[str]
    filing_deadline_basis: Optional[str]
    flags: list[str]
    confidence_reasoning: str
