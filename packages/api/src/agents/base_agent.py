"""Base class for all agents. Every agent inherits from this."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from src.models.case_state import ConfidenceLevel
from src.models.ethics import AuditEntry


class BaseAgent(ABC):
    """Base agent with confidence scoring, audit logging, and ethics hooks."""

    agent_id: str
    agent_name: str

    def __init__(self) -> None:
        self._audit_log: list[AuditEntry] = []

    @abstractmethod
    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Execute the agent's primary task. Must be implemented by subclasses."""
        ...

    def score_confidence(self, value: float) -> ConfidenceLevel:
        """Convert a numeric confidence score to a level."""
        if value >= 0.85:
            return ConfidenceLevel.HIGH
        elif value >= 0.6:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    def log_action(self, action: str, details: dict[str, Any] | None = None) -> None:
        """Add an entry to the agent's audit log."""
        entry = AuditEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            agent_id=self.agent_id,
            action=action,
            details=details or {},
            ethical_check=False,
        )
        self._audit_log.append(entry)

    def get_audit_log(self) -> list[AuditEntry]:
        """Return the agent's audit log."""
        return self._audit_log

    def wrap_output(self, data: dict[str, Any], confidence: float) -> dict[str, Any]:
        """Wrap agent output with confidence rating and metadata."""
        return {
            "data": data,
            "confidence": self.score_confidence(confidence).value,
            "source": self.agent_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
