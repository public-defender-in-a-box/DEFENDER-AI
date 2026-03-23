"""Data models for the Intake Conductor and sub-agents."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Shared / Intake Conductor models
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Fact Gathering Agent models
# ---------------------------------------------------------------------------


class TimelineEvent(BaseModel):
    """A single event in the case timeline."""

    id: str
    timestamp_description: str  # natural language, e.g. "approximately 2:30 AM on Jan 15"
    event: str
    source: str  # CLIENT_STATEMENT, DOCUMENT, INFERENCE
    confidence: str  # HIGH, MEDIUM, LOW
    related_charge_ids: list[str] = []
    source_message_ids: list[str] = []


class WitnessRecord(BaseModel):
    """A potential witness identified during fact gathering."""

    id: str
    name: str = ""
    contact_info: str = ""
    relationship: str  # EYEWITNESS, CHARACTER, ALIBI, EXPERT, CO_DEFENDANT, VICTIM, OTHER
    observed_events: list[str] = []
    favorable: bool | None = None  # True = defense-favorable, None = unknown
    notes: str = ""


class EvidenceItem(BaseModel):
    """A piece of physical or digital evidence."""

    id: str
    description: str
    evidence_type: str  # PHYSICAL, DIGITAL, DOCUMENTARY, TESTIMONIAL, FORENSIC
    location: str = ""
    preservation_status: str  # PRESERVED, AT_RISK, UNKNOWN, DESTROYED
    relevance: str  # CRITICAL, IMPORTANT, SUPPLEMENTARY
    chain_of_custody_concern: bool = False
    notes: str = ""


class ElementCoverage(BaseModel):
    """Tracks which charge elements have been addressed by client statements."""

    charge_id: str
    element: str
    covered: bool
    client_position: str = ""  # ADMITS, DENIES, PARTIAL, NO_RESPONSE
    confidence: str = "LOW"
    gaps: list[str] = []


class FactGatheringOutput(BaseModel):
    """Structured output from the Fact Gathering Agent."""

    timeline: list[TimelineEvent] = []
    witnesses: list[WitnessRecord] = []
    evidence_inventory: list[EvidenceItem] = []
    scene_description: str = ""
    element_coverage: list[ElementCoverage] = []
    follow_up_questions: list[TargetedQuestion] = []
    credibility_notes: list[str] = []


# ---------------------------------------------------------------------------
# Collateral Consequences Agent models
# ---------------------------------------------------------------------------


class CollateralConsequence(BaseModel):
    """A single non-criminal consequence of conviction."""

    id: str
    category: str  # IMMIGRATION, EMPLOYMENT, HOUSING, EDUCATION, FAMILY, CIVIL_RIGHTS, PROFESSIONAL_LICENSE, SEX_OFFENDER, FINANCIAL
    description: str
    severity: str  # SEVERE, MODERATE, MINOR
    charge_specific: bool  # True if tied to a specific charge
    related_charge_ids: list[str] = []
    affects_plea_strategy: bool = False
    georgia_statute: str = ""  # O.C.G.A. reference if applicable
    federal_statute: str = ""  # Federal reference if applicable
    mitigation_possible: bool = False
    mitigation_strategy: str = ""


class PadillaAssessment(BaseModel):
    """Padilla v. Kentucky (2010) compliance assessment.

    Under Padilla, defense counsel MUST advise non-citizen clients about
    the immigration consequences of a guilty plea. Failure to do so
    constitutes ineffective assistance of counsel.
    """

    non_citizen: bool
    immigration_status: str = ""  # LPR, VISA_HOLDER, UNDOCUMENTED, DACA, TPS, ASYLEE, REFUGEE, UNKNOWN
    deportation_risk: str = "UNKNOWN"  # CERTAIN, LIKELY, POSSIBLE, UNLIKELY, UNKNOWN
    aggravated_felony_risk: bool = False
    crime_involving_moral_turpitude: bool = False
    controlled_substance_offense: bool = False
    firearm_offense: bool = False
    domestic_violence_offense: bool = False
    advisory_required: bool = False
    advisory_summary: str = ""


class CollateralConsequencesOutput(BaseModel):
    """Structured output from the Collateral Consequences Agent."""

    consequences: list[CollateralConsequence] = []
    padilla_assessment: PadillaAssessment
    plea_strategy_impact: str = ""
    priority_consequences: list[str] = Field(
        default_factory=list,
        description="IDs of the most critical consequences to discuss with attorney",
    )
    client_stated_priorities: list[str] = []


# ---------------------------------------------------------------------------
# Personal Circumstances Agent models
# ---------------------------------------------------------------------------


class CommunityTie(BaseModel):
    """A factor demonstrating community ties for bail arguments."""

    category: str  # EMPLOYMENT, FAMILY, RESIDENCE, EDUCATION, RELIGIOUS, COMMUNITY_ORG, MILITARY
    description: str
    strength: str  # STRONG, MODERATE, WEAK
    verifiable: bool = False
    verification_source: str = ""


class FlightRiskFactor(BaseModel):
    """A factor relevant to flight risk assessment."""

    factor: str
    direction: str  # INCREASES_RISK, DECREASES_RISK
    weight: str  # HIGH, MEDIUM, LOW
    notes: str = ""


class BailProfile(BaseModel):
    """Bail recommendation profile per O.C.G.A. § 17-6-1."""

    community_ties: list[CommunityTie] = []
    flight_risk_factors: list[FlightRiskFactor] = []
    danger_to_community_factors: list[str] = []
    recommendation: str = ""  # OR, LOW_BOND, MODERATE_BOND, HIGH_BOND
    recommended_conditions: list[str] = []
    georgia_bail_schedule_note: str = ""


class DiversionEligibility(BaseModel):
    """Assessment of eligibility for a specific diversion program."""

    program: str  # PRETRIAL_DIVERSION, DRUG_COURT, MENTAL_HEALTH_COURT, VETERANS_COURT, ACCOUNTABILITY_COURT, FIRST_OFFENDER
    eligible: bool
    basis: str  # reason for eligibility or ineligibility
    georgia_authority: str = ""  # O.C.G.A. citation
    conditions: list[str] = []
    notes: str = ""


class TreatmentNeed(BaseModel):
    """An identified treatment or service need."""

    category: str  # SUBSTANCE_ABUSE, MENTAL_HEALTH, MEDICAL, HOUSING, EMPLOYMENT, EDUCATION, FAMILY
    description: str
    urgency: str  # IMMEDIATE, NEAR_TERM, ONGOING
    relevant_to_diversion: bool = False
    relevant_to_mitigation: bool = False


class MitigationNarrative(BaseModel):
    """Draft mitigation narrative for sentencing purposes."""

    summary: str
    key_themes: list[str] = []
    favorable_factors: list[str] = []
    areas_needing_development: list[str] = []
    recommended_documentation: list[str] = []


class PersonalCircumstancesOutput(BaseModel):
    """Structured output from the Personal Circumstances Agent."""

    bail_profile: BailProfile
    mitigation_narrative: MitigationNarrative
    diversion_eligibility: list[DiversionEligibility] = []
    treatment_needs: list[TreatmentNeed] = []
    first_offender_eligible: bool = False
    first_offender_notes: str = ""
    youthful_offender_eligible: bool = False
    veterans_status: bool = False
