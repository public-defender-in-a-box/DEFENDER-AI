"""The model gateway: every model call in the system goes through ``call_model``.

It validates the response against a declared schema, records what the call cost,
distinguishes an error from an abstention, and can be replayed from disk
(PHASE_1_MODEL_GATEWAY.md §1–§6).

Live and replayed responses go through the same parsing path: the response body
(live from the API, or stored in a cassette) is checked for ``stop_reason``, its
text blocks are joined (thinking blocks come first on current models and carry no
text), parsed as JSON, and validated against ``response_model``.
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import cast

import anthropic
from anthropic import AsyncAnthropic
from pydantic import BaseModel, JsonValue, ValidationError

from src.config import settings
from src.services import measurements
from src.services.model_gateway.allowlist import resolve_model
from src.services.model_gateway.cassettes import (
    Cassette,
    CassetteStore,
    cassette_key,
    current_fixture_ids,
    default_store,
    schema_version,
)
from src.services.model_gateway.errors import (
    AuthError,
    CassetteMissError,
    InvalidRequestError,
    MalformedResponseError,
    ModelCallError,
    RefusalError,
    SchemaMismatchError,
    TransportError,
    TruncatedResponseError,
)
from src.services.model_gateway.pricing import cost_usd
from src.services.model_gateway.types import (
    CassetteOutcome,
    GatewayMode,
    ModelCallRecord,
    ModelCallRequest,
    ModelCallResult,
    T,
)

logger = logging.getLogger(__name__)

_MODES: tuple[GatewayMode, ...] = ("replay", "record", "live")
# A response that ends any other way is not a final answer.
_COMPLETE_STOP_REASONS = {"end_turn", "stop_sequence"}
_TRUNCATED_STOP_REASONS = {"max_tokens", "model_context_window_exceeded"}

_client: AsyncAnthropic | None = None
_store: CassetteStore | None = None


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


def current_mode() -> GatewayMode:
    mode = settings.MODEL_GATEWAY_MODE
    if mode not in _MODES:
        raise ValueError(f"MODEL_GATEWAY_MODE must be one of {_MODES}, got {mode!r}")
    return cast(GatewayMode, mode)


def require_api_key() -> None:
    """Bring your own key (§8.1): fail before any request, with an actionable message."""
    if not settings.ANTHROPIC_API_KEY:
        raise AuthError(
            f"ANTHROPIC_API_KEY is not set, and MODEL_GATEWAY_MODE={settings.MODEL_GATEWAY_MODE} "
            "needs it. Put your own key in the repository-root .env (see .env.example) and "
            "start the backend with `uvicorn src.main:app --env-file ../../.env`, or set "
            "MODEL_GATEWAY_MODE=replay to run from recorded cassettes without a key."
        )


def set_client(client: AsyncAnthropic | None) -> None:
    """Inject a client (tests use one built on a mock HTTP transport)."""
    global _client
    _client = client


def set_store(store: CassetteStore | None) -> None:
    global _store
    _store = store


def _get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        # Retries and timeout are explicit, not SDK defaults (§2). The SDK does the
        # retrying (408/409/429/5xx and connection errors, with backoff); the gateway
        # records how many it took.
        _client = AsyncAnthropic(
            api_key=settings.ANTHROPIC_API_KEY,
            max_retries=settings.MODEL_GATEWAY_MAX_RETRIES,
            timeout=settings.MODEL_GATEWAY_TIMEOUT_S,
        )
    return _client


def _get_store() -> CassetteStore:
    return _store if _store is not None else default_store()


# ---------------------------------------------------------------------------
# Request construction
# ---------------------------------------------------------------------------


def _uses_structured_output(response_model: type[BaseModel]) -> bool:
    return bool(getattr(response_model, "gateway_structured_output", True))


def _check_strict_compatible(node: JsonValue, where: str) -> None:
    """Reject schemas that structured outputs would silently empty.

    The API requires ``additionalProperties: false`` on every object, and the SDK's
    transform forces it. A ``dict[str, X]`` field would therefore be constrained to
    ``{}`` — a well-formed empty result, the exact failure this gateway exists to
    prevent. Fail at request construction instead.
    """
    if isinstance(node, dict):
        if node.get("type") == "object":
            extra = node.get("additionalProperties", False)
            if extra is not False or "properties" not in node:
                raise TypeError(
                    f"{where}: free-form object (dict field?) cannot be expressed in "
                    "structured outputs; use a list of typed objects instead"
                )
        for value in node.values():
            _check_strict_compatible(value, where)
    elif isinstance(node, list):
        for value in node:
            _check_strict_compatible(value, where)


def _response_schema(response_model: type[BaseModel]) -> dict[str, JsonValue]:
    schema = cast(dict[str, JsonValue], response_model.model_json_schema())
    if _uses_structured_output(response_model):
        _check_strict_compatible(schema, response_model.__name__)
    return schema


def build_request_body(
    req: ModelCallRequest[T], model: str, schema: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    """The exact body sent to the API and stored in a cassette.

    No ``temperature``, ``top_p``, ``top_k`` (current models reject them; §5.3), no
    ``fallbacks`` (§0.3), no ``thinking`` (each model's default applies; effort is the
    pinned control).
    """
    output_config: dict[str, JsonValue] = {"effort": req.effort}
    if _uses_structured_output(req.response_model):
        output_config["format"] = {
            "type": "json_schema",
            "schema": anthropic.transform_schema(cast(dict[str, object], schema)),
        }
    return {
        "model": model,
        "max_tokens": req.max_tokens,
        "system": req.system,
        "messages": [{"role": "user", "content": req.prompt}],
        "output_config": output_config,
    }


def request_key(req: ModelCallRequest[T], model: str, schema: dict[str, JsonValue]) -> str:
    return cassette_key(
        model_requested=model,
        effort=req.effort,
        system=req.system,
        prompt=req.prompt,
        max_tokens=req.max_tokens,
        prompt_id=req.prompt_id,
        prompt_version=req.prompt_version,
        response_model_name=req.response_model.__name__,
        schema_version=schema_version(schema),
    )


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


async def _send(body: dict[str, JsonValue]) -> tuple[dict[str, JsonValue], int, int]:
    """Send the request; return (response body, retries taken, latency ms)."""
    client = _get_client()
    started = time.monotonic()
    try:
        raw = await client.messages.with_raw_response.create(**body)  # type: ignore[arg-type]
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        raise AuthError(f"The API rejected the key ({exc.status_code}): {exc.message}") from exc
    except (anthropic.APIConnectionError, anthropic.RateLimitError) as exc:
        raise TransportError(f"{type(exc).__name__}: {exc}") from exc
    except anthropic.APIStatusError as exc:
        if exc.status_code >= 500:
            raise TransportError(f"Server error {exc.status_code}: {exc.message}") from exc
        raise InvalidRequestError(f"Request rejected ({exc.status_code}): {exc.message}") from exc
    latency_ms = int((time.monotonic() - started) * 1000)
    response = cast(dict[str, JsonValue], raw.http_response.json())
    return response, raw.retries_taken, latency_ms


# ---------------------------------------------------------------------------
# Response handling (shared by live and replayed responses)
# ---------------------------------------------------------------------------


def _int(value: JsonValue) -> int:
    return value if isinstance(value, int) else 0


def _make_record(
    req: ModelCallRequest[T],
    *,
    model: str,
    key: str,
    cassette: CassetteOutcome,
    response: dict[str, JsonValue] | None = None,
    retries: int = 0,
    latency_ms: int = 0,
) -> ModelCallRecord:
    usage = response.get("usage") if response else None
    usage = usage if isinstance(usage, dict) else {}
    tokens = {
        "input_tokens": _int(usage.get("input_tokens")),
        "output_tokens": _int(usage.get("output_tokens")),
        "cache_read_input_tokens": _int(usage.get("cache_read_input_tokens")),
        "cache_creation_input_tokens": _int(usage.get("cache_creation_input_tokens")),
    }
    returned = response.get("model") if response else None
    stop_reason = response.get("stop_reason") if response else None
    return ModelCallRecord(
        request_hash=key,
        agent_id=req.agent_id,
        prompt_id=req.prompt_id,
        prompt_version=req.prompt_version,
        model_requested=model,
        model_returned=returned if isinstance(returned, str) else None,
        effort=req.effort,
        latency_ms=latency_ms,
        retries=retries,
        cassette=cassette,
        stop_reason=stop_reason if isinstance(stop_reason, str) else None,
        cost_usd=cost_usd(model, **tokens) if response else 0.0,
        at=datetime.now(timezone.utc),
        **tokens,
    )


def _ledger(record: ModelCallRecord) -> None:
    measurements.record(
        measurements.Measurement(
            kind=measurements.MeasurementKind.MODEL_CALL,
            agent_id=record.agent_id,
            payload=cast(dict[str, JsonValue], record.model_dump(mode="json")),
        )
    )


def _strip_fences(text: str) -> str:
    # Only for the deprecated passthrough model, which predates structured outputs.
    if "```json" in text:
        return text.split("```json", 1)[1].split("```", 1)[0]
    if "```" in text:
        return text.split("```", 1)[1].split("```", 1)[0]
    return text


def _text_of(response: dict[str, JsonValue]) -> str:
    """Join text blocks. Never ``content[0]``: thinking blocks come first."""
    content = response.get("content")
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, dict) and block.get("type") == "text":
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def parse_response(
    req: ModelCallRequest[T], response: dict[str, JsonValue], record: ModelCallRecord
) -> T:
    stop_reason = record.stop_reason
    if stop_reason == "refusal":
        raise RefusalError(
            f"{req.agent_id}/{req.prompt_id}: the model refused ({response.get('stop_details')})",
            record=record,
        )
    if stop_reason in _TRUNCATED_STOP_REASONS:
        raise TruncatedResponseError(
            f"{req.agent_id}/{req.prompt_id}: stop_reason={stop_reason} at "
            f"max_tokens={req.max_tokens}; raise max_tokens at this call site",
            record=record,
        )
    if stop_reason not in _COMPLETE_STOP_REASONS:
        raise MalformedResponseError(
            f"{req.agent_id}/{req.prompt_id}: unexpected stop_reason={stop_reason!r}",
            record=record,
        )

    text = _text_of(response)
    if not text.strip():
        raise MalformedResponseError(
            f"{req.agent_id}/{req.prompt_id}: response has no text block", record=record
        )
    if not _uses_structured_output(req.response_model):
        text = _strip_fences(text)
    try:
        payload = json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise MalformedResponseError(
            f"{req.agent_id}/{req.prompt_id}: response is not JSON ({exc})", record=record
        ) from exc
    try:
        return req.response_model.model_validate(payload)
    except ValidationError as exc:
        raise SchemaMismatchError(
            f"{req.agent_id}/{req.prompt_id}: response failed "
            f"{req.response_model.__name__} validation: {exc}",
            record=record,
        ) from exc


def _failure(record: ModelCallRecord, error: ModelCallError) -> ModelCallError:
    error.record = record
    _ledger(record.model_copy(update={"outcome": error.error_type}))
    return error


def _complete(
    req: ModelCallRequest[T], response: dict[str, JsonValue], record: ModelCallRecord
) -> ModelCallResult[T]:
    try:
        data = parse_response(req, response, record)
    except ModelCallError as exc:
        _failure(record, exc)
        raise
    _ledger(record)
    return ModelCallResult(data=data, record=record)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


async def call_model(req: ModelCallRequest[T]) -> ModelCallResult[T]:
    """Make (or replay) one model call. Raises a ``ModelCallError`` on any failure."""
    model = resolve_model(req.model)
    mode = current_mode()
    schema = _response_schema(req.response_model)
    key = request_key(req, model, schema)
    body = build_request_body(req, model, schema)

    store = _get_store()
    if mode in ("replay", "record"):
        cassette = store.load(model, req.agent_id, key)
        if cassette is not None:
            record = _make_record(
                req,
                model=model,
                key=key,
                cassette="hit",
                response=cassette.response,
                retries=cassette.retries,
                latency_ms=cassette.latency_ms,
            )
            return _complete(req, cassette.response, record)
        if mode == "replay":
            record = _make_record(req, model=model, key=key, cassette="miss")
            raise _failure(
                record,
                CassetteMissError(
                    f"No cassette for {req.agent_id}/{req.prompt_id}@{req.prompt_version} on "
                    f"{model} (key {key[:12]}, expected at "
                    f"{store.path_for(model, req.agent_id, key)}). Replay never falls through "
                    "to a live call: record it with MODEL_GATEWAY_MODE=record and your own key."
                ),
            )
        if not current_fixture_ids():
            raise ValueError(
                "Record mode requires the fixture(s) the request was built from: wrap the "
                "call in cassettes.using_fixtures(...). Only synthetic fixtures are recorded."
            )

    require_api_key()
    outcome: CassetteOutcome = "recorded" if mode == "record" else "bypassed"
    try:
        response, retries, latency_ms = await _send(body)
    except ModelCallError as exc:
        _failure(_make_record(req, model=model, key=key, cassette=outcome), exc)
        raise

    if mode == "record":
        # Saved before parsing, so a refusal or truncation replays as one.
        store.save(
            Cassette(
                key=key,
                recorded_at=datetime.now(timezone.utc),
                sdk_version=anthropic.__version__,
                model_requested=model,
                agent_id=req.agent_id,
                prompt_id=req.prompt_id,
                prompt_version=req.prompt_version,
                response_model=req.response_model.__name__,
                schema_version=schema_version(schema),
                fixture_ids=list(current_fixture_ids()),
                request=body,
                response=response,
                retries=retries,
                latency_ms=latency_ms,
            )
        )
    record = _make_record(
        req,
        model=model,
        key=key,
        cassette=outcome,
        response=response,
        retries=retries,
        latency_ms=latency_ms,
    )
    return _complete(req, response, record)
