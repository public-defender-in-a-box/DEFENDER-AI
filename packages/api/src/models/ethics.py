"""Data models for the Ethics & Compliance Monitor."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class EthicalFlag(BaseModel):
    id: str
    agent_source: str
    category: str  # PRIVILEGE, UPL, BIAS, COMPETENCE, CANDOR, IAC
    priority: str  # CRITICAL, HIGH, MEDIUM, LOW
    description: str
    blocked: bool = False
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    resolution: str | None = None


class AuditEntry(BaseModel):
    id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent_id: str
    action: str
    details: dict = Field(default_factory=dict)
    ethical_check: bool = False
