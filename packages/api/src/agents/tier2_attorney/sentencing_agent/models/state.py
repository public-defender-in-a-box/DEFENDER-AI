"""LangGraph state for the Sentencing & Mitigation Agent subgraph."""

from typing import Any, Optional, TypedDict

from .inputs import SentencingAgentInput
from .outputs import (
    ComparableSentence,
    DepartureArgument,
    DiversionOption,
    GuidelineRange,
    MitigationNarrative,
    NodeAuditRecord,
    SentencingMemoFramework,
)


class MitigationFactSheet(TypedDict, total=False):
    """Structured mitigation facts with provenance."""

    facts: list[dict[str, Any]]
    themes: list[str]
    sensitive_categories: list[str]
    fact_count: int


class SentencingGraphState(TypedDict, total=False):
    """State passed through the sentencing agent LangGraph subgraph."""

    # Input
    input: SentencingAgentInput

    # Scope gate
    scope_status: str  # "in_scope", "out_of_scope", "insufficient_data"
    out_of_scope_reason: Optional[str]

    # Authority loader
    authority_bundle: dict[str, Any]

    # Exposure calculator
    guideline_range: Optional[GuidelineRange]

    # Diversion checker
    diversion_options: list[DiversionOption]

    # Mitigation fact sheet
    mitigation_fact_sheet: Optional[MitigationFactSheet]

    # Leniency argument builder
    departure_arguments: list[DepartureArgument]

    # Mitigation narrative builder
    mitigation_narrative: Optional[MitigationNarrative]

    # Comparable sentence lookup
    comparable_sentences: list[ComparableSentence]

    # Memo framework builder
    sentencing_memo: Optional[SentencingMemoFramework]

    # Cross-cutting
    flags: list[str]
    warnings: list[str]
    ethics_flags: list[str]
    attorney_decision_points: list[str]
    alternative_sentences: list[dict]
    audit_records: list[NodeAuditRecord]

    # Output assembler computed fields
    _confidence_score: float
    _section_confidence: list[Any]
    _timestamp: str
