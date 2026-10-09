"""Append-only measurements store (CLAUDE.md §3.3, PHASE_1_MODEL_GATEWAY.md §6).

Everything the study counts is written here as a typed event rather than only into
prose or logs: model calls (successes and failures), malformed items dropped from
model output, agent failures, and merge decisions.

Phase 1 keeps the store in process memory, with an optional JSON Lines sink
(``MEASUREMENTS_PATH``). Durable storage keyed by ``(case_id, run_id)`` is Phase 2a.
"""

from __future__ import annotations

import contextlib
import contextvars
import logging
import os
import threading
from collections.abc import Iterator
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, JsonValue

logger = logging.getLogger(__name__)


class MeasurementKind(str, Enum):
    MODEL_CALL = "MODEL_CALL"
    ITEM_DROPPED = "ITEM_DROPPED"
    AGENT_FAILURE = "AGENT_FAILURE"
    MERGE_DECISION = "MERGE_DECISION"
    EXTERNAL_CALL = "EXTERNAL_CALL"


class Measurement(BaseModel):
    kind: MeasurementKind
    agent_id: str
    case_id: str | None = None
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, JsonValue] = Field(default_factory=dict)


_lock = threading.Lock()
_events: list[Measurement] = []
_captures: contextvars.ContextVar[tuple[list[Measurement], ...]] = contextvars.ContextVar(
    "measurement_captures", default=()
)


def record(event: Measurement) -> Measurement:
    """Append an event. Never raises on the sink: a measurement must not fail a run."""
    with _lock:
        _events.append(event)
    for sink in _captures.get():
        sink.append(event)
    path = os.getenv("MEASUREMENTS_PATH", "")
    if path:
        try:
            with Path(path).open("a", encoding="utf-8") as fh:
                fh.write(event.model_dump_json() + "\n")
        except OSError:
            # Narrow: the in-memory record above already holds the event.
            logger.exception("Could not append measurement to %s", path)
    return event


def events(kind: MeasurementKind | None = None, agent_id: str | None = None) -> list[Measurement]:
    with _lock:
        snapshot = list(_events)
    return [
        e
        for e in snapshot
        if (kind is None or e.kind == kind) and (agent_id is None or e.agent_id == agent_id)
    ]


def clear() -> None:
    """Tests only."""
    with _lock:
        _events.clear()


@contextlib.contextmanager
def capture() -> Iterator[list[Measurement]]:
    """Collect the events recorded in this context (and tasks it spawns)."""
    sink: list[Measurement] = []
    token = _captures.set(_captures.get() + (sink,))
    try:
        yield sink
    finally:
        _captures.reset(token)


def record_dropped_item(
    agent_id: str, item_kind: str, error: Exception, item: JsonValue = None
) -> None:
    """Count a malformed item dropped from model output (§3.2: a drop is a measurement)."""
    logger.warning("%s dropped a malformed %s: %s", agent_id, item_kind, error)
    record(
        Measurement(
            kind=MeasurementKind.ITEM_DROPPED,
            agent_id=agent_id,
            payload={"item_kind": item_kind, "error": str(error)[:2000], "item": item},
        )
    )


def dropped_item_count(agent_id: str | None = None) -> int:
    return len(events(MeasurementKind.ITEM_DROPPED, agent_id))
