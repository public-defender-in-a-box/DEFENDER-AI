"""Test support for the model gateway. Imported only by tests.

Two tools:

- ``MockAnthropic``: an ``AsyncAnthropic`` client on an ``httpx2.MockTransport``, for
  testing gateway mechanics (error mapping, retries, keying, accounting) without a key
  or a network (PHASE_1_MODEL_GATEWAY.md §5.5).
- ``fake_call_model``: a stand-in for ``call_model`` that validates canned payloads
  against each request's ``response_model``, for agent tests that are not replaying
  real recordings. A canned payload that does not fit the schema raises
  ``SchemaMismatchError``, exactly as the gateway would.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from datetime import datetime, timezone

import anthropic
import httpx2
from pydantic import BaseModel, JsonValue, ValidationError

from src.services.model_gateway.allowlist import resolve_model
from src.services.model_gateway.errors import ModelCallError, SchemaMismatchError
from src.services.model_gateway.types import ModelCallRecord, ModelCallRequest, ModelCallResult

TEST_API_KEY = "test-key-not-a-real-credential"


def api_message(
    payload: JsonValue | str,
    *,
    stop_reason: str = "end_turn",
    model: str = "claude-opus-5-5",
    thinking: bool = True,
    input_tokens: int = 1200,
    output_tokens: int = 340,
) -> dict[str, JsonValue]:
    """A Messages API response body. Thinking block first, as current models return."""
    text = payload if isinstance(payload, str) else json.dumps(payload)
    content: list[JsonValue] = []
    if thinking:
        content.append({"type": "thinking", "thinking": "", "signature": "sig-test"})
    content.append({"type": "text", "text": text})
    return {
        "id": "msg_test",
        "type": "message",
        "role": "assistant",
        "model": model,
        "content": content,
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_input_tokens": 0,
            "cache_creation_input_tokens": 0,
        },
    }


class MockAnthropic:
    """Records every request body; answers with the queued responses in order."""

    def __init__(self, *responses: httpx2.Response | dict[str, JsonValue]) -> None:
        self.requests: list[dict[str, JsonValue]] = []
        self.request_headers: list[dict[str, str]] = []
        self._queue = list(responses)

    def queue(self, *responses: httpx2.Response | dict[str, JsonValue]) -> None:
        self._queue.extend(responses)

    def _handle(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content.decode("utf-8")))
        self.request_headers.append(dict(request.headers))
        if not self._queue:
            raise AssertionError("MockAnthropic: unexpected request (queue empty)")
        nxt = self._queue.pop(0)
        if isinstance(nxt, httpx2.Response):
            return nxt
        return httpx2.Response(200, json=nxt)

    def client(self, *, max_retries: int = 2) -> anthropic.AsyncAnthropic:
        return anthropic.AsyncAnthropic(
            api_key=TEST_API_KEY,
            max_retries=max_retries,
            http_client=anthropic.DefaultAsyncHttpxClient(
                transport=httpx2.MockTransport(self._handle)
            ),
        )


def error_response(status: int, message: str = "error") -> httpx2.Response:
    error_type = {
        400: "invalid_request_error",
        401: "authentication_error",
        403: "permission_error",
        404: "not_found_error",
        429: "rate_limit_error",
        500: "api_error",
        529: "overloaded_error",
    }.get(status, "api_error")
    return httpx2.Response(
        status,
        json={"type": "error", "error": {"type": error_type, "message": message}},
        headers={"retry-after-ms": "1"},
    )


def _record_for(req: ModelCallRequest[BaseModel]) -> ModelCallRecord:
    return ModelCallRecord(
        request_hash="fake",
        agent_id=req.agent_id,
        prompt_id=req.prompt_id,
        prompt_version=req.prompt_version,
        model_requested=resolve_model(req.model),
        model_returned=resolve_model(req.model),
        effort=req.effort,
        cassette="bypassed",
        at=datetime.now(timezone.utc),
    )


Canned = JsonValue | ModelCallError | Callable[[ModelCallRequest[BaseModel]], JsonValue]


class FakeCallModel:
    """An async stand-in for ``call_model``. Use as ``side_effect`` or patch target.

    ``responses`` are consumed in order; each is a payload dict (validated against the
    request's ``response_model``), an exception instance to raise, or a function of the
    request returning a payload. ``by_prompt`` maps a ``prompt_id`` to a payload or a
    sequence of payloads consumed in order, for agents whose calls run concurrently.
    ``respond_with`` answers any call nothing else covers.
    """

    def __init__(
        self,
        *responses: Canned,
        by_prompt: dict[str, Canned | Sequence[Canned]] | None = None,
        respond_with: Callable[[ModelCallRequest[BaseModel]], JsonValue] | None = None,
    ) -> None:
        self._queue = list(responses)
        self._respond_with = respond_with
        self._by_prompt: dict[str, list[Canned]] = {}
        for prompt_id, value in (by_prompt or {}).items():
            if isinstance(value, (list, tuple)):
                self._by_prompt[prompt_id] = list(value)
            else:
                self._by_prompt[prompt_id] = [value]  # type: ignore[list-item]
        self.requests: list[ModelCallRequest[BaseModel]] = []

    def _next(self, req: ModelCallRequest[BaseModel]) -> Canned:
        queue = self._by_prompt.get(req.prompt_id)
        if queue:
            # A single canned payload for a prompt id answers every call to it.
            return queue.pop(0) if len(queue) > 1 else queue[0]
        if not self._queue:
            if self._respond_with is not None:
                return self._respond_with(req)
            raise AssertionError(f"FakeCallModel: no response queued for {req.prompt_id}")
        return self._queue.pop(0)

    async def __call__(self, req: ModelCallRequest[BaseModel]) -> ModelCallResult[BaseModel]:
        return await self.respond(req)

    async def respond(self, req: ModelCallRequest[BaseModel]) -> ModelCallResult[BaseModel]:
        """The same, as a plain coroutine function: usable as an ``AsyncMock``
        ``side_effect`` where a test also wants the mock's call assertions."""
        self.requests.append(req)
        canned = self._next(req)
        if isinstance(canned, ModelCallError):
            raise canned
        payload = canned(req) if callable(canned) else canned
        try:
            data = req.response_model.model_validate(payload)
        except ValidationError as exc:
            raise SchemaMismatchError(
                f"{req.agent_id}/{req.prompt_id}: canned payload failed "
                f"{req.response_model.__name__} validation: {exc}"
            ) from exc
        return ModelCallResult(data=data, record=_record_for(req))

    @property
    def prompt_ids(self) -> list[str]:
        return [r.prompt_id for r in self.requests]
