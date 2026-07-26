"""LangGraph orchestration graph — defines the full agent pipeline.

Pipeline sequence:
    Charge Processing → Pre-Interview Research → Intake Conductor → (Case Prep placeholder)

The Orchestrator manages the CaseState object and validates/merges every agent
output before advancing to the next stage.
"""

from __future__ import annotations

import logging
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


class GraphState(TypedDict):
    """State passed through the LangGraph pipeline."""

    case_id: str
    case_state: dict[str, Any]
    current_stage: str
    error: str | None


async def orchestrator_init_node(state: GraphState) -> GraphState:
    """Node: Initialize the Orchestrator and CaseState."""
    from src.agents.tier0.orchestrator import OrchestratorAgent

    orchestrator = OrchestratorAgent()
    case_state = await orchestrator.run(
        {
            "case_id": state["case_id"],
            "attorney_id": state["case_state"].get("attorney_id", ""),
            "jurisdiction": state["case_state"].get("jurisdiction", "GA"),
            "attorney_config": state["case_state"].get("attorney_config", {}),
            "documents": state["case_state"].get("documents", []),
        }
    )

    state["case_state"] = case_state
    state["current_stage"] = "CREATED"
    # Store orchestrator ref in state for downstream nodes
    state["case_state"]["_orchestrator_ref"] = id(orchestrator)
    return state


async def charge_processing_node(state: GraphState) -> GraphState:
    """Node: Charge Processing Agent."""
    from src.agents.tier0.orchestrator import OrchestratorAgent
    from src.agents.tier1.charge_processing import ChargeProcessingAgent

    orchestrator = OrchestratorAgent()
    # Re-initialize with current state
    await orchestrator.run(
        {
            "case_id": state["case_id"],
            "attorney_id": state["case_state"].get("attorney_id", ""),
            "jurisdiction": state["case_state"].get("jurisdiction", "GA"),
            "documents": state["case_state"].get("documents", []),
        }
    )

    # Check sequencing
    can_run, reason = orchestrator.can_run_agent("charge_processing")
    if not can_run:
        logger.warning("Cannot run charge_processing: %s", reason)
        state["error"] = reason
        return state

    orchestrator.mark_agent_started("charge_processing")

    agent = ChargeProcessingAgent()
    documents = state["case_state"].get("documents", [])

    if not documents:
        failure = await orchestrator.handle_agent_failure(
            "charge_processing",
            "No documents to process",
        )
        state["error"] = failure["error"]
        state["case_state"] = orchestrator.get_case_state_snapshot()
        return state

    # Get document text — support both extracted_text and raw text
    doc = documents[0] if isinstance(documents[0], dict) else {}
    document_text = doc.get("extracted_text", doc.get("text", ""))
    if not document_text:
        # Try loading from the conftest fixture pattern
        document_text = state["case_state"].get("document_text", "")

    try:
        result = await agent.run(
            {
                "document_text": document_text,
                "document_type": doc.get("type", "COMPLAINT"),
                "jurisdiction": state["case_state"].get("jurisdiction", "GA"),
                "filename": doc.get("file_name", "document_1"),
                "matter_id": state["case_id"],
            }
        )
    except Exception as e:
        failure = await orchestrator.handle_agent_failure(
            "charge_processing",
            str(e),
        )
        state["error"] = failure["error"]
        state["case_state"] = orchestrator.get_case_state_snapshot()
        return state

    # Merge through Orchestrator
    merge_result = await orchestrator.receive_agent_output("charge_processing", result)

    state["case_state"] = orchestrator.get_case_state_snapshot()
    state["current_stage"] = state["case_state"].get("stage", "CHARGES_PROCESSED")

    if merge_result["decision"] in ("BLOCKED_ETHICS_P1", "FAILED"):
        state["error"] = merge_result.get("reason", "Merge blocked")

    return state


async def pre_interview_node(state: GraphState) -> GraphState:
    """Node: Pre-Interview Research Conductor."""
    from src.agents.tier0.orchestrator import OrchestratorAgent
    from src.agents.tier1.pre_interview import PreInterviewResearchAgent

    orchestrator = OrchestratorAgent()
    await orchestrator.run(
        {
            "case_id": state["case_id"],
            "attorney_id": state["case_state"].get("attorney_id", ""),
            "jurisdiction": state["case_state"].get("jurisdiction", "GA"),
        }
    )

    # Reconstruct state — in production this would load from DB
    # For the pipeline, we rebuild from the state dict
    orchestrator._case_state.charge_processing = state["case_state"].get("charge_processing")
    orchestrator._case_state.advance_stage(
        __import__(
            "src.models.case_state", fromlist=["PipelineStage"]
        ).PipelineStage.CHARGES_PROCESSED
    )

    agent = PreInterviewResearchAgent()

    try:
        result = await agent.run(
            {
                "charge_processing": state["case_state"].get("charge_processing"),
            }
        )
    except Exception as e:
        failure = await orchestrator.handle_agent_failure(
            "pre_interview_research",
            str(e),
        )
        state["error"] = failure["error"]
        state["case_state"] = orchestrator.get_case_state_snapshot()
        return state

    merge_result = await orchestrator.receive_agent_output("pre_interview_research", result)

    state["case_state"] = orchestrator.get_case_state_snapshot()
    state["current_stage"] = state["case_state"].get("stage", "PRE_INTERVIEW_COMPLETE")

    if merge_result["decision"] in ("BLOCKED_ETHICS_P1", "FAILED"):
        state["error"] = merge_result.get("reason", "Merge blocked")

    return state


async def intake_node(state: GraphState) -> GraphState:
    """Node: Intake Conductor — runs the intake agent in batch mode.

    In production, interactive intake happens via WebSocket. In the pipeline,
    the agent runs with whatever pre-recorded responses are available in
    state (if any), then merges its output through the Orchestrator.
    """
    from src.agents.tier0.orchestrator import OrchestratorAgent
    from src.agents.tier1.intake_conductor import IntakeConductorAgent
    from src.models.case_state import PipelineStage

    orchestrator = OrchestratorAgent()
    await orchestrator.run(
        {
            "case_id": state["case_id"],
            "attorney_id": state["case_state"].get("attorney_id", ""),
            "jurisdiction": state["case_state"].get("jurisdiction", "GA"),
        }
    )

    # Reconstruct state from previous pipeline stages
    orchestrator._case_state.charge_processing = state["case_state"].get("charge_processing")
    orchestrator._case_state.pre_interview_research = state["case_state"].get(
        "pre_interview_research"
    )
    orchestrator._case_state.advance_stage(PipelineStage.PRE_INTERVIEW_COMPLETE)

    can_run, reason = orchestrator.can_run_agent("intake_conductor")
    if not can_run:
        logger.warning("Cannot run intake_conductor: %s", reason)
        state["error"] = reason
        return state

    orchestrator.mark_agent_started("intake_conductor")

    agent = IntakeConductorAgent()

    charge_data = state["case_state"].get("charge_processing", {})
    if "data" in charge_data and "confidence" in charge_data:
        charge_data = charge_data["data"]

    try:
        result = await agent.run(
            {
                "charge_data": charge_data,
                "matter_id": state["case_id"],
                "responses": state["case_state"].get("intake_responses", {}),
            }
        )
    except Exception as e:
        failure = await orchestrator.handle_agent_failure("intake_conductor", str(e))
        state["error"] = failure["error"]
        state["case_state"] = orchestrator.get_case_state_snapshot()
        return state

    merge_result = await orchestrator.receive_agent_output("intake_conductor", result)

    state["case_state"] = orchestrator.get_case_state_snapshot()
    state["current_stage"] = state["case_state"].get("stage", "INTAKE_COMPLETE")

    if merge_result["decision"] in ("BLOCKED_ETHICS_P1", "FAILED"):
        state["error"] = merge_result.get("reason", "Merge blocked")

    return state


async def case_prep_node(state: GraphState) -> GraphState:
    """Node: Case Prep Conductor — placeholder for Tier 1 synthesis."""
    state["current_stage"] = "CASE_PREP_IN_PROGRESS"
    # Case Prep is a future implementation
    return state


def should_continue_after_charges(state: GraphState) -> str:
    """Route after charge processing — stop on error."""
    if state.get("error"):
        return END
    return "pre_interview"


def should_continue_after_pre_interview(state: GraphState) -> str:
    """Route after pre-interview research — stop on error."""
    if state.get("error"):
        return END
    return "intake"


def should_continue_after_intake(state: GraphState) -> str:
    """Route after intake — stop on error."""
    if state.get("error"):
        return END
    return "case_prep"


def build_pipeline() -> StateGraph:
    """Build the full Tier 0 + Tier 1 agent pipeline graph."""
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("charge_processing", charge_processing_node)
    graph.add_node("pre_interview", pre_interview_node)
    graph.add_node("intake", intake_node)
    graph.add_node("case_prep", case_prep_node)

    # Entry point
    graph.set_entry_point("charge_processing")

    # Edges with conditional routing
    graph.add_conditional_edges(
        "charge_processing",
        should_continue_after_charges,
        {"pre_interview": "pre_interview", END: END},
    )
    graph.add_conditional_edges(
        "pre_interview",
        should_continue_after_pre_interview,
        {"intake": "intake", END: END},
    )
    graph.add_conditional_edges(
        "intake",
        should_continue_after_intake,
        {"case_prep": "case_prep", END: END},
    )
    graph.add_edge("case_prep", END)

    return graph


# Compiled graph — import and invoke this
pipeline = build_pipeline().compile()
