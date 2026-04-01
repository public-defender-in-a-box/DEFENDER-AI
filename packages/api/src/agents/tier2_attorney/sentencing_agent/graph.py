"""LangGraph subgraph for the Sentencing & Mitigation Agent.

Workflow:
    scope_gate → authority_loader → exposure_calculator → diversion_checker
    → mitigation_fact_sheet → leniency_argument_builder → mitigation_narrative_builder
    → comparable_sentence_lookup → memo_framework_builder → output_assembler
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from langgraph.graph import END, StateGraph

from .config import AGENT_VERSION
from .models.inputs import SentencingAgentInput
from .models.outputs import SentencingAgentOutput
from .models.state import SentencingGraphState
from .nodes.authority_loader import authority_loader
from .nodes.comparable_sentence_lookup import comparable_sentence_lookup
from .nodes.diversion_checker import diversion_checker
from .nodes.exposure_calculator import exposure_calculator
from .nodes.leniency_argument_builder import leniency_argument_builder
from .nodes.memo_framework_builder import memo_framework_builder
from .nodes.mitigation_fact_sheet import mitigation_fact_sheet_node
from .nodes.mitigation_narrative_builder import mitigation_narrative_builder
from .nodes.output_assembler import output_assembler
from .nodes.scope_gate import scope_gate

logger = logging.getLogger(__name__)


def should_continue_after_scope(state: SentencingGraphState) -> str:
    """Route after scope gate — skip full analysis if out of scope."""
    if state.get("scope_status") == "in_scope":
        return "authority_loader"
    return "output_assembler"


def build_sentencing_graph() -> StateGraph:
    """Build the sentencing agent LangGraph subgraph."""
    graph = StateGraph(SentencingGraphState)

    # Add all nodes
    graph.add_node("scope_gate", scope_gate)
    graph.add_node("authority_loader", authority_loader)
    graph.add_node("exposure_calculator", exposure_calculator)
    graph.add_node("diversion_checker", diversion_checker)
    graph.add_node("mitigation_fact_sheet", mitigation_fact_sheet_node)
    graph.add_node("leniency_argument_builder", leniency_argument_builder)
    graph.add_node("mitigation_narrative_builder", mitigation_narrative_builder)
    graph.add_node("comparable_sentence_lookup", comparable_sentence_lookup)
    graph.add_node("memo_framework_builder", memo_framework_builder)
    graph.add_node("output_assembler", output_assembler)

    # Entry point
    graph.set_entry_point("scope_gate")

    # Conditional routing after scope gate
    graph.add_conditional_edges(
        "scope_gate",
        should_continue_after_scope,
        {
            "authority_loader": "authority_loader",
            "output_assembler": "output_assembler",
        },
    )

    # Linear chain for in-scope cases
    graph.add_edge("authority_loader", "exposure_calculator")
    graph.add_edge("exposure_calculator", "diversion_checker")
    graph.add_edge("diversion_checker", "mitigation_fact_sheet")
    graph.add_edge("mitigation_fact_sheet", "leniency_argument_builder")
    graph.add_edge("leniency_argument_builder", "mitigation_narrative_builder")
    graph.add_edge("mitigation_narrative_builder", "comparable_sentence_lookup")
    graph.add_edge("comparable_sentence_lookup", "memo_framework_builder")
    graph.add_edge("memo_framework_builder", "output_assembler")

    # End
    graph.add_edge("output_assembler", END)

    return graph


# Compiled graph — import and invoke this
sentencing_pipeline = build_sentencing_graph().compile()


def state_to_output(state: SentencingGraphState) -> SentencingAgentOutput:
    """Convert final graph state to SentencingAgentOutput."""
    input_data: SentencingAgentInput = state["input"]

    return SentencingAgentOutput(
        case_id=input_data.case_id,
        agent_version=AGENT_VERSION,
        timestamp=state.get("_timestamp", datetime.now(timezone.utc).isoformat()),
        scope_status=state.get("scope_status", "insufficient_data"),
        out_of_scope_reason=state.get("out_of_scope_reason"),
        confidence_score=state.get("_confidence_score", 0.0),
        section_confidence=state.get("_section_confidence", []),
        guideline_range=state.get("guideline_range"),
        diversion_options=state.get("diversion_options", []),
        departure_arguments=state.get("departure_arguments", []),
        mitigation_narrative=state.get("mitigation_narrative"),
        comparable_sentences=state.get("comparable_sentences", []),
        sentencing_memo=state.get("sentencing_memo"),
        alternative_sentences=state.get("alternative_sentences", []),
        flags=state.get("flags", []),
        attorney_decision_points=state.get("attorney_decision_points", []),
        ethics_flags=state.get("ethics_flags", []),
        warnings=state.get("warnings", []),
    )


async def run_sentencing_analysis(input_data: SentencingAgentInput) -> SentencingAgentOutput:
    """Run the full sentencing analysis pipeline."""
    initial_state: SentencingGraphState = {
        "input": input_data,
        "scope_status": "insufficient_data",
        "out_of_scope_reason": None,
        "authority_bundle": {},
        "guideline_range": None,
        "diversion_options": [],
        "mitigation_fact_sheet": None,
        "departure_arguments": [],
        "mitigation_narrative": None,
        "comparable_sentences": [],
        "sentencing_memo": None,
        "flags": [],
        "warnings": [],
        "ethics_flags": [],
        "attorney_decision_points": [],
        "alternative_sentences": [],
        "audit_records": [],
    }

    final_state = await sentencing_pipeline.ainvoke(initial_state)
    return state_to_output(final_state)
