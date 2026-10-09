"""Data models for the Plea/Trial Assessment Agent."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class OutcomeScenario(BaseModel):
    """A single possible outcome — either a plea resolution or a trial result."""

    label: str  # e.g., "Plea to misdemeanor possession", "Acquittal at trial"
    probability: float = Field(ge=0.0, le=1.0)
    probability_reasoning: str
    incarceration_months: float  # 0 if no incarceration
    probation_months: float = 0.0
    fine_amount: float = 0.0
    community_service_hours: float = 0.0
    treatment_program: bool = False
    criminal_record_impact: str  # e.g., "Misdemeanor conviction", "No record"
    collateral_consequences: list[str] = []  # Key consequences triggered
    notes: list[str] = []  # Attorney-facing notes


class PleaScenario(BaseModel):
    """The plea offer and its full consequences."""

    offer_description: str  # What the State is offering
    plea_charge: str  # What defendant would plead to (may differ from original charge)
    plea_charge_statute: str  # O.C.G.A. section
    original_charges: list[str]  # What's currently charged
    sentences: OutcomeScenario  # The plea outcome
    collateral_consequences_detail: list[dict[str, str]] = []
    # Each entry: {"category": "immigration|employment|housing|...",
    #              "description": "...", "severity": "HIGH|MEDIUM|LOW"}
    diversion_eligible: bool = False
    diversion_details: str = ""
    expungement_eligible: bool = False
    expungement_details: str = ""


class TrialScenario(BaseModel):
    """The trial path with weighted possible outcomes."""

    outcomes: list[OutcomeScenario]  # Multiple outcomes with probabilities (must sum to ~1.0)
    expected_incarceration_months: float  # Probability-weighted average
    expected_probation_months: float
    trial_penalty_estimate: str  # Qualitative assessment of sentencing differential
    key_strengths: list[str]  # Strongest defense arguments
    key_weaknesses: list[str]  # Biggest prosecution advantages
    suppression_motion_impact: str  # How suppression motion outcome affects trial odds
    jury_considerations: list[str] = []  # Jurisdiction-specific jury factors


class ComparisonMatrix(BaseModel):
    """Side-by-side comparison of plea vs. trial paths."""

    dimensions: list[dict[str, Any]]
    # Each dimension: {"factor": str, "plea_value": str, "trial_value": str,
    #                  "advantage": "PLEA"|"TRIAL"|"NEUTRAL"}
    # Factors include: incarceration risk, criminal record impact,
    # collateral consequences, financial cost, time to resolution,
    # certainty of outcome, etc.


class RiskFactor(BaseModel):
    """A specific risk the attorney should consider."""

    factor: str
    description: str
    favors: str  # "PLEA", "TRIAL", or "NEUTRAL"
    weight: str  # "HIGH", "MEDIUM", "LOW" — how much this should matter
    source: str  # Which upstream data supports this


class PleaTrialOutput(BaseModel):
    """Complete output of the Plea/Trial Assessment Agent."""

    # Core analysis
    plea_scenario: PleaScenario
    trial_scenario: TrialScenario
    comparison_matrix: ComparisonMatrix
    risk_factors: list[RiskFactor]

    # Confidence
    confidence: float = Field(ge=0.0, le=1.0)
    confidence_level: str  # HIGH, MEDIUM, LOW
    confidence_reasoning: str

    # Flags
    flags: list[str] = []
    warnings: list[str] = []

    # Metadata
    agent_name: str = "plea_trial_analyst"

    # NON-NEGOTIABLE — these are hardcoded, never overridden
    decision_support_warning: str = "DECISION SUPPORT ONLY — ATTORNEY AND CLIENT DECIDE"
    privilege_warning: str = "ATTORNEY-CLIENT PRIVILEGED MATERIAL"
    draft_warning: str = "DRAFT — ATTORNEY REVIEW REQUIRED"

    # Attorney subjective inputs used (for audit trail)
    attorney_inputs_used: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Response model: what the model returns (src/prompts/plea_trial_analyst/system.v1.txt).
# ``ComparisonMatrix.dimensions`` and ``PleaScenario.collateral_consequences_detail``
# are free-form dicts above, which structured outputs cannot express; these typed
# versions carry the same keys.
# ---------------------------------------------------------------------------


class CollateralDetail(BaseModel):
    category: str
    description: str
    severity: Literal["HIGH", "MEDIUM", "LOW"]


class PleaScenarioResponse(BaseModel):
    offer_description: str
    plea_charge: str
    plea_charge_statute: str
    original_charges: list[str]
    sentences: OutcomeScenario
    collateral_consequences_detail: list[CollateralDetail]
    diversion_eligible: bool
    diversion_details: str
    expungement_eligible: bool
    expungement_details: str


class Dimension(BaseModel):
    factor: str
    plea_value: str
    trial_value: str
    advantage: Literal["PLEA", "TRIAL", "NEUTRAL"]


class ComparisonMatrixResponse(BaseModel):
    dimensions: list[Dimension]


class PleaTrialResponse(BaseModel):
    # None when there is no plea offer: the prompt asks for the trial analysis only.
    plea_scenario: PleaScenarioResponse | None
    trial_scenario: TrialScenario
    comparison_matrix: ComparisonMatrixResponse
    risk_factors: list[RiskFactor]
    flags: list[str]
    confidence_reasoning: str
