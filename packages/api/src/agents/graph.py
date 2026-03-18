"""LangGraph orchestration graph — defines the full agent pipeline."""

from typing import Any, TypedDict

from langgraph.graph import StateGraph, END


class GraphState(TypedDict):
    """State passed through the LangGraph pipeline."""

    case_id: str
    case_state: dict[str, Any]
    current_stage: str
    error: str | None


async def charge_processing_node(state: GraphState) -> GraphState:
    """Node: Charge Processing Agent."""
    from src.agents.tier1.charge_processing import ChargeProcessingAgent

    agent = ChargeProcessingAgent()
    documents = state["case_state"].get("documents", [])
    if not documents:
        state["error"] = "No documents to process"
        return state

    result = await agent.run({
        "document_text": documents[0].get("extracted_text", ""),
        "document_type": documents[0].get("type", "COMPLAINT"),
        "jurisdiction": state["case_state"].get("jurisdiction", "IL"),
    })

    state["case_state"]["charge_processing"] = result
    state["current_stage"] = "CHARGES_PROCESSED"
    return state


async def pre_interview_node(state: GraphState) -> GraphState:
    """Node: Pre-Interview Research Conductor."""
    from src.agents.tier1.pre_interview import PreInterviewResearchAgent

    agent = PreInterviewResearchAgent()
    result = await agent.run({
        "charge_processing": state["case_state"].get("charge_processing"),
    })

    state["case_state"]["pre_interview_research"] = result
    state["current_stage"] = "PRE_INTERVIEW_COMPLETE"
    return state


async def intake_node(state: GraphState) -> GraphState:
    """Node: Intake Conductor — placeholder for interactive chat."""
    state["current_stage"] = "INTAKE_IN_PROGRESS"
    # Intake is interactive (WebSocket) — this node marks it as ready
    return state


async def case_prep_node(state: GraphState) -> GraphState:
    """Node: Case Prep Conductor."""
    from src.agents.tier1.case_prep import CasePrepAgent

    agent = CasePrepAgent()
    result = await agent.run({
        "case_state": state["case_state"],
    })

    state["case_state"]["case_prep_memo"] = result
    state["current_stage"] = "CASE_PREP_COMPLETE"
    return state


def should_continue_after_charges(state: GraphState) -> str:
    """Route after charge processing."""
    if state.get("error"):
        return END
    return "pre_interview"


def build_pipeline() -> StateGraph:
    """Build the full agent pipeline graph."""
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("charge_processing", charge_processing_node)
    graph.add_node("pre_interview", pre_interview_node)
    graph.add_node("intake", intake_node)
    graph.add_node("case_prep", case_prep_node)

    # Set entry point
    graph.set_entry_point("charge_processing")

    # Add edges
    graph.add_conditional_edges(
        "charge_processing",
        should_continue_after_charges,
        {"pre_interview": "pre_interview", END: END},
    )
    graph.add_edge("pre_interview", "intake")
    graph.add_edge("intake", "case_prep")
    graph.add_edge("case_prep", END)

    return graph


# Compiled graph — import and invoke this
pipeline = build_pipeline().compile()
