"""Request, record, and result types for the model gateway (PHASE_1_MODEL_GATEWAY.md §2)."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field

Effort = Literal["low", "medium", "high", "xhigh", "max"]
CassetteOutcome = Literal["hit", "miss", "recorded", "bypassed"]
GatewayMode = Literal["replay", "record", "live"]

T = TypeVar("T", bound=BaseModel)


class ModelCallRequest(BaseModel, Generic[T]):
    """One model call. ``response_model`` is required: there is no untyped path."""

    model_config = ConfigDict(frozen=True)

    prompt: str
    system: str
    # Per call site. Thinking tokens count toward it, so the old 4096 default
    # truncates on current models.
    max_tokens: int = Field(gt=0)
    # Pinned, identical across models; the models' own defaults differ (§5.3).
    effort: Effort = "high"
    # None = the run's model (see ``allowlist.use_model``), else the primary.
    model: str | None = None
    response_model: type[T]
    prompt_id: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)


class ModelCallRecord(BaseModel):
    """Accounting for one call, written unconditionally — successes and failures."""

    request_hash: str
    agent_id: str
    prompt_id: str
    prompt_version: str
    model_requested: str
    # From the response. None only when no response exists (transport/auth failure,
    # cassette miss).
    model_returned: str | None
    effort: Effort
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    # On a cassette hit, the latency and retries recorded when the call was made.
    latency_ms: int = 0
    retries: int = 0
    cassette: CassetteOutcome
    stop_reason: str | None = None
    # Actual cost, or what the call would have cost on a cassette hit (§6).
    cost_usd: float = 0.0
    # "ok", or the ModelCallError subclass name.
    outcome: str = "ok"
    at: datetime

    @property
    def billed_usd(self) -> float:
        """What was actually spent: zero for a replayed call."""
        return 0.0 if self.cassette == "hit" else self.cost_usd


class ModelCallResult(BaseModel, Generic[T]):
    data: T
    record: ModelCallRecord


class AbstainableResponse(BaseModel):
    """Mixin for response models where "the record does not address this" is a
    correct answer (CLAUDE.md §4.5). Abstention is expressed here, never by raising
    and never by an empty payload.
    """

    abstained: bool = False
    abstention_reason: str | None = None
