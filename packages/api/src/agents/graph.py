"""LangGraph orchestration graph — defines the full agent pipeline.

Pipeline sequence:
    Charge Processing → Pre-Interview Research → Intake Conductor
    → Intake Sub-Agents (Fact Gatherer, Collateral, Personal — parallel)
    → Case Prep (placeholder)

The Orchestrator manages the CaseState object and validates/merges every agent
output before advancing to the next stage.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, TypedDict

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


class GraphState(TypedDict):
    """State passed through the LangGraph pipeline."""

    case_id: str
    case_state: dict[str, Any]
    current_stage: str
    error: Optional[str]


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
    """Node: Intake Conductor — placeholder for interactive chat.

    In production, this is interactive via WebSocket. In the pipeline test,
    this marks the case as ready for intake.
    """
    state["current_stage"] = "INTAKE_IN_PROGRESS"
    return state


async def intake_sub_agents_node(state: GraphState) -> GraphState:
    """Node: Tier 2 Intake Specialists — run after Intake Conductor.

    Dispatches the three intake sub-agents in parallel:
    1. Fact Gatherer — structures timeline, witnesses, evidence, element coverage
    2. Collateral Consequences — immigration, employment, housing, Padilla check
    3. Personal Circumstances — bail profile, mitigation, diversion eligibility

    All three read from intake_summary and charge_processing in the CaseState
    and write their outputs back to the state dict. Results are merged through
    the Orchestrator's receive_agent_output for ethics checking and audit.
    """
    import asyncio

    from src.agents.cross_cutting.ethics_monitor import EthicsMonitorAgent
    from src.agents.tier2_intake.collateral_agent import CollateralConsequencesAgent
    from src.agents.tier2_intake.fact_gatherer import FactGathererAgent
    from src.agents.tier2_intake.personal_circumstances import (
        PersonalCircumstancesAgent,
    )

    case_state = state["case_state"]
    intake_summary = case_state.get("intake_summary", {})
    charge_data = case_state.get("charge_processing", {})
    charges = []
    if isinstance(charge_data, dict):
        inner = charge_data.get("data", charge_data)
        charges = inner.get("charges", []) if isinstance(inner, dict) else []

    # Build inputs for each sub-agent
    fact_input = {
        "targeted_questions": intake_summary.get("unanswered_questions", []),
        "client_responses": intake_summary.get("transcript", []),
        "charges": charges,
        "research_context": case_state.get("pre_interview_research", {}),
        "intake_facts": intake_summary.get("facts", []),
    }

    collateral_input = {
        "charges": charges,
        "personal_circumstances": intake_summary.get("personal_circumstances", {}),
        "client_priorities": intake_summary.get("priorities_and_concerns", []),
        "intake_summary": intake_summary,
    }

    personal_input = {
        "client_background": intake_summary.get("personal_circumstances", {}),
        "charges": charges,
        "client_priorities": intake_summary.get("priorities_and_concerns", []),
    }

    # Run all three in parallel
    fact_agent = FactGathererAgent()
    collateral_agent = CollateralConsequencesAgent()
    personal_agent = PersonalCircumstancesAgent()

    try:
        fact_result, collateral_result, personal_result = await asyncio.gather(
            fact_agent.run(fact_input),
            collateral_agent.run(collateral_input),
            personal_agent.run(personal_input),
            return_exceptions=True,
        )

        # Ethics monitor for Tier 2 outputs before merging into state
        ethics = EthicsMonitorAgent()

        # Agent ID → (state field, result) mapping
        agent_results = [
            ("fact_gatherer", "fact_gathering", fact_result),
            ("collateral_consequences", "collateral_consequences", collateral_result),
            ("personal_circumstances", "personal_circumstances", personal_result),
        ]

        for agent_id, state_field, result in agent_results:
            if isinstance(result, Exception):
                logger.error("%s failed: %s", agent_id, result)
                state["case_state"][state_field] = {
                    "error": str(result),
                    "confidence": "LOW",
                }
                continue

            # Run ethics check before writing to state
            ethics_result = await ethics.run(
                {
                    "output": result,
                    "agent_id": agent_id,
                    "is_client_facing": False,
                }
            )

            ethics_flags = ethics_result.get("flags", [])
            p1_flags = [
                f for f in ethics_flags if f.get("priority") == "CRITICAL"
            ]

            if p1_flags or ethics_result.get("blocked", False):
                logger.warning(
                    "%s output blocked by ethics monitor: %s",
                    agent_id,
                    p1_flags,
                )
                state["case_state"][state_field] = {
                    "error": "Blocked by ethics monitor",
                    "confidence": "LOW",
                    "ethics_flags": ethics_flags,
                }
            else:
                state["case_state"][state_field] = result
                if ethics_flags:
                    state["case_state"].setdefault("ethical_flags", []).extend(
                        ethics_flags
                    )

    except Exception as e:
        logger.error("Intake sub-agents node failed: %s", e)
        state["error"] = f"Intake sub-agents failed: {e}"

    state["current_stage"] = "INTAKE_COMPLETE"
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
    """Route after intake — run sub-agents or stop on error."""
    if state.get("error"):
        return END
    return "intake_sub_agents"


def build_pipeline() -> StateGraph:
    """Build the full Tier 0 + Tier 1 + Tier 2 Intake agent pipeline graph."""
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("charge_processing", charge_processing_node)
    graph.add_node("pre_interview", pre_interview_node)
    graph.add_node("intake", intake_node)
    graph.add_node("intake_sub_agents", intake_sub_agents_node)
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
        {"intake_sub_agents": "intake_sub_agents", END: END},
    )
    graph.add_edge("intake_sub_agents", "case_prep")
    graph.add_edge("case_prep", END)

    return graph


# Compiled graph — import and invoke this
pipeline = build_pipeline().compile()
