"""Response models for the Charge Processing Agent's three model calls.

Field names and nesting match the JSON structures in the agent's prompts, so the
agent's output (``model_dump()``) keeps the shape downstream agents already read.
Every list is required: the model must say "none" explicitly with ``[]``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

DocumentType = Literal[
    "indictment",
    "information",
    "accusation",
    "complaint",
    "arrest_report",
    "police_report",
    "witness_statement",
    "lab_report",
    "search_warrant",
    "other",
]


class DocumentClassification(BaseModel):
    document_type: DocumentType
    confidence: float
    rationale: str


# --- Pass 1: per-document extraction ---------------------------------------


class Defendant(BaseModel):
    name: str
    aliases: list[str]
    date_of_birth: str | None
    address: str | None
    prior_record_mentioned: bool
    prior_record_details: str | None
    custody_status: str
    confidence: float
    source_reference: str


class Statute(BaseModel):
    code: str
    title: str
    full_text_reference: str


class Element(BaseModel):
    element: str
    factual_support_in_charging_document: str | None
    confidence: float


class PenaltyRange(BaseModel):
    minimum: str
    maximum: str
    mandatory_minimum: str | None
    notes: str


class Enhancement(BaseModel):
    type: str
    statute: str
    additional_penalty: str
    factual_basis: str
    confidence: float
    source_reference: str


class Charge(BaseModel):
    count_number: int
    charge_description: str
    statute: Statute
    degree: str
    classification: str
    elements: list[Element]
    penalty_range: PenaltyRange
    enhancements: list[Enhancement]
    lesser_included_offenses: list[str]
    date_of_alleged_offense: str | None
    location_of_alleged_offense: str | None
    confidence: float
    source_reference: str


class FactualAllegation(BaseModel):
    allegation_id: str
    summary: str
    detail: str
    source_document: str
    source_page: str
    category: str
    related_charges: list[int]
    exculpatory_potential: bool
    exculpatory_notes: str | None
    confidence: float


class PersonOfInterest(BaseModel):
    person_id: str
    name: str
    role: str
    badge_number: str | None
    agency: str | None
    involvement_summary: str
    documents_appearing_in: list[str]
    potential_impeachment_notes: str | None
    confidence: float


class EvidenceItem(BaseModel):
    description: str
    type: str
    chain_of_custody_notes: str | None
    source_reference: str
    confidence: float


class MisconductFlag(BaseModel):
    flag_id: str
    category: str
    subcategory: str
    description: str
    factual_basis: str
    legal_significance: str
    severity: Literal["high", "medium", "low"]
    source_document: str
    source_page: str
    related_charges: list[int]
    confidence: float


class ProceduralFlag(BaseModel):
    flag_type: str
    description: str
    deadline_date: str | None
    calculated_from: str | None
    statute_reference: str
    confidence: float


class DocumentExtraction(BaseModel):
    defendant: Defendant
    charges: list[Charge]
    factual_allegations: list[FactualAllegation]
    persons_of_interest: list[PersonOfInterest]
    evidence_items: list[EvidenceItem]
    misconduct_flags: list[MisconductFlag]
    procedural_flags: list[ProceduralFlag]


# --- Pass 2: cross-document analysis ----------------------------------------


class Jurisdiction(BaseModel):
    level: Literal["state", "federal", "unknown"]
    court: str
    confidence: float


class DocumentClaim(BaseModel):
    document_id: str
    page: int
    claim: str


class Inconsistency(BaseModel):
    inconsistency_id: str
    description: str
    document_a: DocumentClaim
    document_b: DocumentClaim
    defense_relevance: str
    severity: Literal["high", "medium", "low"]
    confidence: float


class FirstOffenderEligibility(BaseModel):
    potentially_eligible: bool
    basis: str
    disqualifying_factors: list[str]
    confidence: float


class PretrialDiversionEligibility(BaseModel):
    potentially_eligible: bool
    basis: str
    notes: str
    confidence: float


class Eligibility(BaseModel):
    potentially_eligible: bool
    basis: str
    confidence: float


class DiversionEligibility(BaseModel):
    first_offender_act_eligible: FirstOffenderEligibility
    pretrial_diversion_eligible: PretrialDiversionEligibility
    drug_court_eligible: Eligibility
    federal_pretrial_diversion: Eligibility


class CrossDocumentAnalysis(BaseModel):
    jurisdiction: Jurisdiction
    inconsistencies: list[Inconsistency]
    additional_misconduct_flags: list[MisconductFlag]
    diversion_eligibility: DiversionEligibility
    consolidated_defendant: Defendant
