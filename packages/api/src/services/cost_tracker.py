"""Cost tracker for research agent pipeline.

Tracks LLM token usage and external API calls per agent per case.
Uses Claude Sonnet pricing as default: $3/1M input, $15/1M output.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Claude Sonnet pricing (per token)
_INPUT_COST_PER_TOKEN = 3.0 / 1_000_000
_OUTPUT_COST_PER_TOKEN = 15.0 / 1_000_000


@dataclass
class AgentCostEntry:
    """Cost tracking for a single agent run."""

    agent_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    courtlistener_calls: int = 0
    web_search_calls: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None

    @property
    def llm_cost(self) -> float:
        return (
            self.input_tokens * _INPUT_COST_PER_TOKEN + self.output_tokens * _OUTPUT_COST_PER_TOKEN
        )

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
        """Begin tracking costs for an agent."""
        entry = AgentCostEntry(agent_id=agent_id)
        self._entries[agent_id] = entry
        return entry

    def record_llm_call(
        self,
        agent_id: str,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        """Record a single LLM API call."""
        entry = self._entries.get(agent_id)
        if entry is None:
            entry = self.start_agent(agent_id)
        entry.input_tokens += input_tokens
        entry.output_tokens += output_tokens
        entry.llm_calls += 1

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
            "budget_remaining_usd": round(1.00 - self.total_cost, 4),
            "over_budget": self.total_cost > 1.00,
        }

        logger.info(
            "Research cost report for case %s: $%.4f (%d CL calls)",
            self.case_id,
            self.total_cost,
            self.total_courtlistener_calls,
        )

        return report
