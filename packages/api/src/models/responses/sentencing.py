"""Response models for the Sentencing & Mitigation Agent's two model calls.

``LeniencyArgument`` mirrors ``sentencing_agent.models.outputs.DepartureArgument``,
and ``NarrativeDraft`` mirrors ``MitigationNarrative`` with its ``dict`` lists typed
(structured outputs cannot express free-form objects).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class LeniencyArgument(BaseModel):
    argument_type: Literal[
        "mitigating_factor", "alternative_sentence", "judicial_discretion_argument"
    ]
    basis: str
    supporting_facts: list[str]
    supporting_fact_ids: list[str]
    strength: Literal["strong", "moderate", "weak"]
    applicable_authority: list[str]
    authority_verification_status: Literal["confirmed", "unconfirmed", "not_applicable"]
    notes: str


class LeniencyArguments(BaseModel):
    arguments: list[LeniencyArgument]


class SupportingFact(BaseModel):
    fact_id: str
    text: str
    used_in: str


class ParagraphFacts(BaseModel):
    paragraph: str
    fact_ids: list[str]


class NarrativeDraft(BaseModel):
    summary: str
    full_narrative: str
    key_themes: list[str]
    supporting_facts: list[SupportingFact]
    paragraph_fact_map: list[ParagraphFacts]
    unsupported_claim_warnings: list[str]
    tone_notes: str
