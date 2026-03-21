"""In-memory case store for MVP. Replaced by database in production."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.agents.tier0.orchestrator import OrchestratorAgent

# Maps case_id -> OrchestratorAgent instance
case_store: dict[str, OrchestratorAgent] = {}
