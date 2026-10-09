"""Cost tracker for research agent pipeline.

Tracks model usage and external API calls per agent per case. Reused from the
original research pipeline, re-plumbed for Phase 1 (PHASE_1_MODEL_GATEWAY.md §6):
costs now come from the gateway's ``ModelCallRecord``s, priced from
``model_gateway/pricing.json`` per model, instead of a hard-coded $3/$15 rate applied
to token counts nobody recorded.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from src.config import settings
from src.services.model_gateway.types import ModelCallRecord

logger = logging.getLogger(__name__)


@dataclass
class AgentCostEntry:
    """Cost tracking for a single agent run."""

    agent_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    # Cost as priced per call by the gateway; on a cassette hit, the would-be cost.
    llm_cost_usd: float = 0.0
    billed_cost_usd: float = 0.0
    replayed_calls: int = 0
    courtlistener_calls: int = 0
    web_search_calls: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None

    @property
    def llm_cost(self) -> float:
        return self.llm_cost_usd

    @property
    def total_cost(self) -> float:
        # CourtListener is free; web search has no per-query cost in our setup
        return self.llm_cost

    @property
    def duration_seconds(self) -> float:
        end = self.end_time or time.time()
        return end - self.start_time

    def to_dict(self) -> dict:
        return {
            "agent_id": self.agent_id,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "llm_calls": self.llm_calls,
            "replayed_calls": self.replayed_calls,
            "billed_cost_usd": round(self.billed_cost_usd, 4),
            "courtlistener_calls": self.courtlistener_calls,
            "web_search_calls": self.web_search_calls,
            "llm_cost_usd": round(self.llm_cost, 4),
            "total_cost_usd": round(self.total_cost, 4),
            "duration_seconds": round(self.duration_seconds, 1),
        }


class CostTracker:
    """Tracks costs across all agents for a single case processing run."""

    def __init__(self, case_id: str) -> None:
        self.case_id = case_id
        self._entries: dict[str, AgentCostEntry] = {}

    def start_agent(self, agent_id: str) -> AgentCostEntry:
        """Begin tracking costs for an agent (idempotent)."""
        entry = self._entries.get(agent_id)
        if entry is None:
            entry = AgentCostEntry(agent_id=agent_id)
            self._entries[agent_id] = entry
        return entry

    def record_model_call(self, record: ModelCallRecord) -> None:
        """Record one gateway call (successful or failed) against its agent."""
        entry = self._entries.get(record.agent_id)
        if entry is None:
            entry = self.start_agent(record.agent_id)
        entry.input_tokens += record.input_tokens
        entry.output_tokens += record.output_tokens
        entry.llm_calls += 1
        entry.llm_cost_usd += record.cost_usd
        entry.billed_cost_usd += record.billed_usd
        entry.replayed_calls += record.cassette == "hit"

    def record_courtlistener_call(self, agent_id: str) -> None:
        """Record a CourtListener API call."""
        entry = self._entries.get(agent_id)
        if entry is None:
            entry = self.start_agent(agent_id)
        entry.courtlistener_calls += 1

    def record_web_search(self, agent_id: str) -> None:
        """Record a web search call."""
        entry = self._entries.get(agent_id)
        if entry is None:
            entry = self.start_agent(agent_id)
        entry.web_search_calls += 1

    def finish_agent(self, agent_id: str) -> None:
        """Mark an agent as finished."""
        entry = self._entries.get(agent_id)
        if entry:
            entry.end_time = time.time()

    @property
    def total_cost(self) -> float:
        return sum(e.total_cost for e in self._entries.values())

    @property
    def total_courtlistener_calls(self) -> int:
        return sum(e.courtlistener_calls for e in self._entries.values())

    def get_report(self) -> dict:
        """Generate a full cost report."""
        report = {
            "case_id": self.case_id,
            "agents": {aid: entry.to_dict() for aid, entry in self._entries.items()},
            "total_cost_usd": round(self.total_cost, 4),
            "total_courtlistener_calls": self.total_courtlistener_calls,
            "billed_cost_usd": round(sum(e.billed_cost_usd for e in self._entries.values()), 4),
            "budget_remaining_usd": round(settings.RESEARCH_COST_BUDGET_USD - self.total_cost, 4),
            "over_budget": self.total_cost > settings.RESEARCH_COST_BUDGET_USD,
        }

        logger.info(
            "Research cost report for case %s: $%.4f (%d CL calls)",
            self.case_id,
            self.total_cost,
            self.total_courtlistener_calls,
        )

        return report
