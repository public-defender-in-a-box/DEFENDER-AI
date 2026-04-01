"""Output schemas for the Sentencing & Mitigation Agent."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class GuidelineRange(BaseModel):
    """Normalized statutory sentencing exposure for Georgia misdemeanor MVP.

    Georgia does not use a formal guideline grid. This object represents
    the statutory sentencing range, retained for downstream compatibility.
    """

    statutory_minimum: int  # days
    statutory_maximum: int  # days
    fine_minimum: float
    fine_maximum: float
    has_mandatory_minimum: bool = False
    mandatory_minimum_days: Optional[int] = None
    probation_possible: bool = True
    suspended_sentence_possible: bool = True
    weekend_service_possible: bool = True
    weekend_service_threshold_days: int = 180
    time_served_credit_days: int = 0
    typical_range_description: str
    data_basis: list[str] = Field(default_factory=list)
    special_fees: list[dict] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class DiversionOption(BaseModel):
    program_name: str
    statutory_basis: str
    availability_status: Literal[
        "confirmed_available",
        "not_available_in_circuit",
        "unknown",
    ] = "unknown"
    preliminary_eligibility: Literal["yes", "no", "unknown"] = "unknown"
    eligibility_factors: list[str] = Field(default_factory=list)
    outcome_if_completed: str = ""
    typical_duration: Optional[str] = None
    conditions: list[str] = Field(default_factory=list)
    recommendation_notes: str = ""
    source_ref: Optional[str] = None


class DepartureArgument(BaseModel):
    """Leniency / alternative-sentence arguments for Georgia misdemeanor MVP.

    Named 'DepartureArgument' for downstream compatibility, but these are
    not formal guideline departures.
    """

    argument_type: Literal[
        "mitigating_factor",
        "alternative_sentence",
        "judicial_discretion_argument",
    ]
    basis: str
    supporting_facts: list[str]
    supporting_fact_ids: list[str] = Field(default_factory=list)
    strength: Literal["strong", "moderate", "weak"]
    applicable_authority: list[str] = Field(default_factory=list)
    authority_verification_status: Literal[
        "confirmed",
        "unconfirmed",
        "not_applicable",
    ] = "not_applicable"
    notes: str = ""


class MitigationNarrative(BaseModel):
    summary: str
    full_narrative: str
    key_themes: list[str] = Field(default_factory=list)
    supporting_facts: list[dict] = Field(default_factory=list)
    paragraph_fact_map: list[dict] = Field(default_factory=list)
    unsupported_claim_warnings: list[str] = Field(default_factory=list)
    tone_notes: str = ""


class ComparableSentence(BaseModel):
    description: str
    offense: str
    defendant_profile: str
    sentence_imposed: str
    jurisdiction: str
    date: Optional[str] = None
    source: Literal["verified_corpus", "unverified_research"] = "verified_corpus"
    verification_status: Literal["confirmed", "unconfirmed"] = "confirmed"
    source_ref: Optional[str] = None
    relevance_notes: str = ""


class SentencingMemoFramework(BaseModel):
    title: str
    sections: list[dict]
    # Each section: {
    #   "heading": str,
    #   "content": str,
    #   "attorney_action": "REVIEW" | "EDIT_REQUIRED" | "FILL_IN" | "ANNOTATION_REQUIRED",
    #   "engagement_level": "HIGH" | "MEDIUM" | "LOW"
    # }
    recommended_attachments: list[str] = Field(default_factory=list)
    filing_notes: str = ""


class SectionConfidence(BaseModel):
    section_name: str
    score: float
    reasons: list[str] = Field(default_factory=list)


class SentencingAgentOutput(BaseModel):
    case_id: str
    agent_version: str = "0.2.0"
    timestamp: str
    scope_status: Literal["in_scope", "out_of_scope", "insufficient_data"]
    out_of_scope_reason: Optional[str] = None
    confidence_score: float
    section_confidence: list[SectionConfidence] = Field(default_factory=list)

    guideline_range: Optional[GuidelineRange] = None
    diversion_options: list[DiversionOption] = Field(default_factory=list)
    departure_arguments: list[DepartureArgument] = Field(default_factory=list)
    mitigation_narrative: Optional[MitigationNarrative] = None
    comparable_sentences: list[ComparableSentence] = Field(default_factory=list)
    sentencing_memo: Optional[SentencingMemoFramework] = None
    alternative_sentences: list[dict] = Field(default_factory=list)

    flags: list[str] = Field(default_factory=list)
    attorney_decision_points: list[str] = Field(default_factory=list)
    ethics_flags: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    disclaimer: str = (
        "DRAFT — ATTORNEY REVIEW REQUIRED. This output is decision support only. "
        "All sentencing calculations, diversion assessments, and mitigation arguments "
        "must be reviewed, verified, and approved by a supervising attorney before "
        "any filing, client communication, or court presentation."
    )


class NodeAuditRecord(BaseModel):
    node_name: str
    status: Literal["ok", "warning", "error", "skipped"]
    started_at: str
    completed_at: str
    warnings: list[str] = Field(default_factory=list)
    output_keys: list[str] = Field(default_factory=list)
