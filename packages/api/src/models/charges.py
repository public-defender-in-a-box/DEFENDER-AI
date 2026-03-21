"""Data models for the Charge Processing Agent."""

from __future__ import annotations

from pydantic import BaseModel


class Enhancement(BaseModel):
    type: str  # WEAPON, PRIOR_RECORD, SCHOOL_ZONE, GANG, AMOUNT, OTHER
    description: str
    statute_section: str
    additional_penalty: str


class PenaltyRange(BaseModel):
    minimum_months: int | None = None
    maximum_months: int | None = None
    fine_min: int | None = None
    fine_max: int | None = None
    mandatory_minimum: bool = False
    probation_eligible: bool = True


class ParsedCharge(BaseModel):
    charge_id: str
    statute_section: str
    offense_title: str
    degree: str
    elements: list[str]
    penalty_range: PenaltyRange
    enhancements: list[Enhancement] = []
    procedural_requirements: list[str] = []


class FactualAllegation(BaseModel):
    id: str
    allegation: str
    related_charge_ids: list[str] = []
    related_elements: list[str] = []
    date_of_allegation: str | None = None
    location: str | None = None


class PersonOfInterest(BaseModel):
    name: str
    role: str  # OFFICER, WITNESS, VICTIM, CO_DEFENDANT, OTHER
    badge_number: str | None = None
    agency: str | None = None
    details: str = ""


class ChargeProcessingInput(BaseModel):
    document_text: str
    document_type: str  # COMPLAINT, INDICTMENT, INFORMATION, ARREST_REPORT
    jurisdiction: str = "IL"


class ChargeProcessingOutput(BaseModel):
    charges: list[ParsedCharge]
    factual_allegations: list[FactualAllegation]
    enhancements: list[Enhancement]
    persons_of_interest: list[PersonOfInterest]
    procedural_flags: list[str]
    raw_document_summary: str
