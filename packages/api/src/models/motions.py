"""Data models for the Motion Drafter Agent."""

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
