"""Agent status and debug endpoints."""

from fastapi import APIRouter

router = APIRouter(tags=["agents"])

AGENT_REGISTRY = {
    "orchestrator": {"name": "Case Orchestrator", "tier": 0},
    "charge_processing": {"name": "Charge Processing Agent", "tier": 1},
    "pre_interview_research": {"name": "Pre-Interview Research Conductor", "tier": 1},
    "intake_conductor": {"name": "Intake Conductor", "tier": 1},
    "case_prep_conductor": {"name": "Case Prep Conductor", "tier": 1},
    "statute_agent": {"name": "Statute Agent", "tier": 2},
    "case_law_agent": {"name": "Case Law Agent", "tier": 2},
    "citation_verifier": {"name": "Citation Verification Agent", "tier": 2},
    "recency_monitor": {"name": "Recency Monitor", "tier": 2},
    "fact_gatherer": {"name": "Fact Gathering Agent", "tier": 2},
    "rights_scanner": {"name": "Rights Violation Scanner", "tier": 2},
    "collateral_agent": {"name": "Collateral Consequences Agent", "tier": 2},
    "personal_circumstances": {"name": "Personal Circumstances Agent", "tier": 2},
    "motion_drafter": {"name": "Motion Drafter Agent", "tier": 2},
    "brady_agent": {"name": "Brady Compliance Agent", "tier": 2},
    "plea_trial_analyst": {"name": "Plea / Trial Assessment Agent", "tier": 2},
    "sentencing_agent": {"name": "Sentencing & Mitigation Agent", "tier": 2},
    "ethics_monitor": {"name": "Ethics & Compliance Monitor", "tier": -1},
}


@router.get("/agents")
async def list_agents():
    """List all registered agents."""
    return AGENT_REGISTRY


@router.get("/agents/{agent_id}")
async def get_agent_info(agent_id: str):
    """Get info about a specific agent."""
    agent = AGENT_REGISTRY.get(agent_id)
    if not agent:
        return {"error": f"Agent '{agent_id}' not found"}
    return {"id": agent_id, **agent}
