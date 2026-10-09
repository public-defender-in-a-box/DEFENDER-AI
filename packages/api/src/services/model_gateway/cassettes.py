"""Cassette record/replay for model calls (PHASE_1_MODEL_GATEWAY.md §5).

A cassette stores the request body as sent and the response body as received —
never request headers, so it cannot contain an API key. Cassettes are committed,
which is safe only because every fixture is synthetic (CLAUDE.md §2). Each cassette
names the fixture file(s) its request was built from; recording refuses to run
without them, so nothing outside a committed fixture can be recorded.
"""

from __future__ import annotations

import contextlib
import contextvars
import hashlib
import json
import re
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field, JsonValue

from src.config import settings

# packages/api/tests/cassettes
DEFAULT_CASSETTE_ROOT = Path(__file__).resolve().parents[3] / "tests" / "cassettes"
CASSETTE_FORMAT_VERSION = 1

_fixture_ids: contextvars.ContextVar[tuple[str, ...]] = contextvars.ContextVar(
    "cassette_fixture_ids", default=()
)


@contextlib.contextmanager
def using_fixtures(*fixture_ids: str) -> Iterator[None]:
    """Declare the committed fixture(s) the enclosed calls are built from.

    An identifier is a path relative to ``packages/api`` (``tests/fixtures/x.txt``),
    optionally followed by ``::name`` for a fixture defined inside a file.
    """
    token = _fixture_ids.set(_fixture_ids.get() + tuple(fixture_ids))
    try:
        yield
    finally:
        _fixture_ids.reset(token)


def current_fixture_ids() -> tuple[str, ...]:
    return _fixture_ids.get()


def schema_version(schema: dict[str, JsonValue]) -> str:
    """A content hash of the response schema, so changing the model changes the key."""
    canonical = json.dumps(schema, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def cassette_key(
    *,
    model_requested: str,
    effort: str,
    system: str,
    prompt: str,
    max_tokens: int,
    prompt_id: str,
    prompt_version: str,
    response_model_name: str,
    schema_version: str,
) -> str:
    """sha256 over everything that can change the output (§5.1).

    ``model_requested`` and ``effort`` must be in the key: without them one model's
    recording would be served for another and the comparison destroyed.
    """
    material = json.dumps(
        [
            model_requested,
            effort,
            system,
            prompt,
            max_tokens,
            prompt_id,
            prompt_version,
            response_model_name,
            schema_version,
        ],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class Cassette(BaseModel):
    format_version: int = CASSETTE_FORMAT_VERSION
    key: str
    recorded_at: datetime
    sdk_version: str
    model_requested: str
    agent_id: str
    prompt_id: str
    prompt_version: str
    response_model: str
    schema_version: str
    fixture_ids: list[str] = Field(min_length=1)
    request: dict[str, JsonValue]
    response: dict[str, JsonValue]
    retries: int
    latency_ms: int


_SAFE = re.compile(r"[^A-Za-z0-9._-]")


class CassetteStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, model: str, agent_id: str, key: str) -> Path:
        return self.root / _SAFE.sub("_", model) / _SAFE.sub("_", agent_id) / f"{key}.json"

    def load(self, model: str, agent_id: str, key: str) -> Cassette | None:
        path = self.path_for(model, agent_id, key)
        if not path.is_file():
            return None
        return Cassette.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, cassette: Cassette) -> Path:
        path = self.path_for(cassette.model_requested, cassette.agent_id, cassette.key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(cassette.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        return path


def default_store() -> CassetteStore:
    configured = settings.MODEL_GATEWAY_CASSETTE_DIR
    return CassetteStore(Path(configured) if configured else DEFAULT_CASSETTE_ROOT)
