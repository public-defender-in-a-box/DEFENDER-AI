"""Input schemas for the Sentencing & Mitigation Agent."""

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, Field


class CasePhase(str, Enum):
    PRETRIAL = "pretrial"
    POST_CONVICTION = "post_conviction"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    SELF_REPORTED = "self_reported"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ConductType(str, Enum):
    SIMPLE_POSSESSION = "simple_possession"
    PWID = "possession_with_intent"
    SALE = "sale"
    DISTRIBUTION = "distribution"
    MANUFACTURE = "manufacture"
    UNKNOWN = "unknown"


class QuantityUnit(str, Enum):
    OUNCES = "ounces"
    GRAMS = "grams"
    UNKNOWN = "unknown"


class JurisdictionContext(BaseModel):
    state: Literal["georgia"] = "georgia"
    county: str
    judicial_circuit: Optional[str] = None
    court_name: Optional[str] = None
    court_type: Optional[str] = None


class SourceFact(BaseModel):
    fact_id: str
    text: str
    source_agent: str
    source_ref: Optional[str] = None
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    sensitivity_tags: list[str] = Field(default_factory=list)


class OffenseDetails(BaseModel):
    statute: str  # e.g. "O.C.G.A. § 16-13-30(j)(1)"
    charge_description: str
    conduct_type: ConductType = ConductType.UNKNOWN
    substance_name: Optional[str] = None
    quantity_text: Optional[str] = None
    quantity_value: Optional[float] = None
    quantity_unit: QuantityUnit = QuantityUnit.UNKNOWN
    degree: Optional[str] = None
    enhancements: list[str] = Field(default_factory=list)
    statutory_max_jail: Optional[int] = None
    statutory_max_fine: Optional[float] = None
    elements: list[str] = Field(default_factory=list)


class PriorRecord(BaseModel):
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    has_prior_convictions: bool
    prior_drug_offenses: int = 0
    prior_felonies: int = 0
    prior_misdemeanors: int = 0
    prior_conditional_discharge_used: bool = False
    prior_out_of_state_or_federal_drug_convictions: int = 0
    details: list[dict] = Field(default_factory=list)


class PersonalCircumstances(BaseModel):
    age: Optional[int] = None
    employment_status: Optional[str] = None
    employment_details: Optional[str] = None
    employer_supportive: Optional[bool] = None
    housing_stable: Optional[bool] = None
    housing_details: Optional[str] = None
    dependents: list[str] = Field(default_factory=list)
    caregiving_obligations: Optional[str] = None
    education_status: Optional[str] = None
    education_details: Optional[str] = None
    mental_health_history: Optional[str] = None
    substance_use_history: Optional[str] = None
    treatment_history: Optional[str] = None
    currently_in_treatment: Optional[bool] = None
    military_service: Optional[bool] = None
    military_details: Optional[str] = None
    community_ties: Optional[str] = None
    character_references_available: Optional[bool] = None
    additional_mitigating_factors: list[str] = Field(default_factory=list)
    structured_facts: list[SourceFact] = Field(default_factory=list)


class PleaOfferTerms(BaseModel):
    offered_disposition: Optional[str] = None
    jail_days: Optional[int] = None
    probation_months: Optional[int] = None
    fine_amount: Optional[float] = None
    diversion_offer: Optional[str] = None
    conviction_required: Optional[bool] = None
    notes: Optional[str] = None


class SentencingAgentInput(BaseModel):
    case_id: str
    case_phase: CasePhase
    jurisdiction_context: JurisdictionContext
    offense_details: OffenseDetails
    criminal_history: PriorRecord
    personal_circumstances: PersonalCircumstances
    pretrial_custody_days: int = 0
    conviction_charges: list[str] = Field(default_factory=list)
    plea_offer_terms: Optional[PleaOfferTerms] = None
    attorney_notes: Optional[str] = None
    program_availability_overrides: dict[str, bool] = Field(default_factory=dict)
