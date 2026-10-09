"""Response models for the Intake Conductor's model calls and the intake route.

Field names match the JSON shapes in the prompts (src/prompts/intake_conductor/).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from src.models.intake import CollateralConsequence, PadillaAssessment

Priority = Literal["required", "recommended", "optional"]
Severity = Literal["high", "medium", "low"]
Subagent = Literal["fact_gatherer", "rights_violation_scanner", "collateral_consequences"]


# --- Question generation ------------------------------------------------------


class InterviewQuestion(BaseModel):
    question_id: str
    question_text: str
    question_type: Literal["open_ended", "yes_no", "multiple_choice", "scaled"]
    priority: Priority
    rationale: str
    follow_up_triggers: list[str]
    related_charges: list[int]
    feeds_subagent: Subagent | Literal["none"]
    options: list[str]


class PhaseQuestions(BaseModel):
    phase: str
    questions: list[InterviewQuestion]
    phase_instructions: str
    ethical_notes: str


# --- Response processing ------------------------------------------------------


class ExtractedFact(BaseModel):
    fact_id: str
    category: Literal[
        "personal", "incident", "arrest", "custody", "prior_history", "priority", "concern"
    ]
    summary: str
    detail: str
    confidence: float
    source: str
    client_certainty: Literal["certain", "mostly_certain", "uncertain", "vague", "refused"]
    related_charges: list[int]
    feeds_subagent: Subagent | Literal["none"]


class ChargeInconsistency(BaseModel):
    inconsistency_id: str
    description: str
    client_claim: str
    charge_data_claim: str
    severity: Severity
    defense_relevance: str
    confidence: float


class EthicalFlag(BaseModel):
    flag_type: Literal[
        "interpreter_needed",
        "competency_concern",
        "mental_health_crisis",
        "minor_client",
        "conflict_of_interest",
        "privilege_risk",
        "safety_concern",
        "capacity_concern",
    ]
    description: str
    urgency: Literal["immediate", "soon", "routine"]
    recommended_action: str


class FollowUpQuestion(BaseModel):
    question_text: str
    rationale: str
    priority: Priority


class SubagentTrigger(BaseModel):
    target_agent: Subagent
    trigger_reason: str
    context_to_pass: str
    priority: Severity


class ProcessedResponse(BaseModel):
    question_id: str
    phase: str
    extracted_facts: list[ExtractedFact]
    inconsistencies_with_charges: list[ChargeInconsistency]
    ethical_flags: list[EthicalFlag]
    follow_up_questions: list[FollowUpQuestion]
    subagent_triggers: list[SubagentTrigger]


# --- Post-interview inconsistency analysis ------------------------------------


class Inconsistency(BaseModel):
    inconsistency_id: str
    description: str
    client_version: str
    charge_document_version: str
    severity: Severity
    defense_relevance: str
    possible_explanations: list[str]
    attorney_action_needed: str
    confidence: float


class Corroboration(BaseModel):
    description: str
    client_claim: str
    charge_data_support: str
    significance: str


class Gap(BaseModel):
    description: str
    source: str
    suggested_follow_up: str
    priority: Severity


class DefenseAngle(BaseModel):
    description: str
    basis: str
    type: Literal[
        "alibi",
        "mistaken_identity",
        "self_defense",
        "consent",
        "constitutional_violation",
        "other",
    ]
    confidence: float


class InconsistencyAnalysis(BaseModel):
    inconsistencies: list[Inconsistency]
    corroborations: list[Corroboration]
    gaps: list[Gap]
    new_defense_angles: list[DefenseAngle]


# --- Intake route turn message -------------------------------------------------


class TurnMessage(BaseModel):
    combined_message: str


# --- Collateral Consequences Agent ---------------------------------------------


class CollateralAnalysis(BaseModel):
    """The model's part of ``CollateralConsequencesOutput``; the client's stated
    priorities come from the agent's input, not the model."""

    consequences: list[CollateralConsequence]
    padilla_assessment: PadillaAssessment
    plea_strategy_impact: str
    priority_consequences: list[str]
