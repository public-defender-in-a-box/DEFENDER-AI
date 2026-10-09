"""Gateway mechanics, tested without a key or a network (PHASE_1_MODEL_GATEWAY.md §10).

The Anthropic client runs on an ``httpx2.MockTransport``; cassettes go to a temporary
directory. Agent-level behavior is tested in each agent's own test module.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path

import pytest
from pydantic import BaseModel

from src.config import settings
from src.services import measurements
from src.services.model_gateway import (
    AbstainableResponse,
    AuthError,
    CassetteMissError,
    InvalidRequestError,
    MalformedResponseError,
    ModelCallRequest,
    ModelNotAllowedError,
    RefusalError,
    SchemaMismatchError,
    TransportError,
    TruncatedResponseError,
    call_model,
    check_configuration,
    use_model,
    using_fixtures,
)
from src.services.model_gateway import gateway
from src.services.model_gateway.cassettes import CassetteStore
from src.services.model_gateway.pricing import cost_usd
from src.services.model_gateway.testing import (
    TEST_API_KEY,
    MockAnthropic,
    api_message,
    error_response,
)

FIXTURE = "tests/conftest.py::sample_complaint_text"


class Extraction(BaseModel):
    defendant: str
    counts: int


class Finding(AbstainableResponse):
    answer: str | None = None


def _request(**overrides: object) -> ModelCallRequest[Extraction]:
    fields: dict[str, object] = {
        "prompt": "Extract the defendant and count of charges from: STATE v. JOHN DOE ...",
        "system": "Return JSON.",
        "max_tokens": 8000,
        "response_model": Extraction,
        "prompt_id": "test.extract",
        "prompt_version": "v1",
        "agent_id": "gateway_test",
    }
    fields.update(overrides)
    return ModelCallRequest(**fields)  # type: ignore[arg-type]


@pytest.fixture
def store(tmp_path: Path) -> CassetteStore:
    s = CassetteStore(tmp_path / "cassettes")
    gateway.set_store(s)
    return s


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> MockAnthropic:
    """Live mode against a mock transport, with a (fake) key present."""
    mock = MockAnthropic()
    monkeypatch.setattr(settings, "MODEL_GATEWAY_MODE", "live")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", TEST_API_KEY)
    gateway.set_client(mock.client(max_retries=2))
    return mock


@pytest.fixture
def record(monkeypatch: pytest.MonkeyPatch, store: CassetteStore) -> MockAnthropic:
    mock = MockAnthropic()
    monkeypatch.setattr(settings, "MODEL_GATEWAY_MODE", "record")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", TEST_API_KEY)
    gateway.set_client(mock.client())
    return mock


async def _record_one(
    record: MockAnthropic, response: dict[str, object], req: ModelCallRequest[Extraction]
) -> None:
    record.queue(response)  # type: ignore[arg-type]
    with using_fixtures(FIXTURE):
        try:
            await call_model(req)
        except (RefusalError, TruncatedResponseError, SchemaMismatchError):
            pass


# ---------------------------------------------------------------------------
# §10 acceptance tests
# ---------------------------------------------------------------------------


def test_no_live_network_in_ci(network_guard: list[str]) -> None:
    with pytest.raises(RuntimeError, match="blocked"):
        socket.create_connection(("api.anthropic.com", 443), timeout=1)
    assert network_guard, "the attempt was recorded, so a swallowed error still fails the test"
    network_guard.clear()  # this test made the attempt on purpose


async def test_cassette_miss_raises(store: CassetteStore) -> None:
    mock = MockAnthropic(api_message({"defendant": "x", "counts": 1}))
    gateway.set_client(mock.client())
    assert settings.MODEL_GATEWAY_MODE == "replay"
    with pytest.raises(CassetteMissError) as exc_info:
        await call_model(_request())
    assert mock.requests == [], "replay must never fall through to the API"
    assert exc_info.value.record is not None
    assert exc_info.value.record.cassette == "miss"


async def test_cassette_key_includes_model_and_effort(
    record: MockAnthropic, store: CassetteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = _request()
    await _record_one(record, api_message({"defendant": "Opus", "counts": 1}), base)

    keys = {
        gateway.request_key(r, gateway.resolve_model(r.model), Extraction.model_json_schema())
        for r in (
            base,
            _request(model="claude-sonnet-5-5"),
            _request(effort="medium"),
        )
    }
    assert len(keys) == 3

    monkeypatch.setattr(settings, "MODEL_GATEWAY_MODE", "replay")
    hit = await call_model(base)
    assert hit.data.defendant == "Opus" and hit.record.cassette == "hit"
    with pytest.raises(CassetteMissError):
        await call_model(_request(model="claude-sonnet-5-5"))
    with pytest.raises(CassetteMissError):
        await call_model(_request(effort="medium"))


async def test_schema_mismatch_raises(
    record: MockAnthropic, store: CassetteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    req = _request()
    await _record_one(record, api_message({"defendant": "JOHN DOE", "counts": 1}), req)
    (path,) = list(store.root.rglob("*.json"))
    cassette = json.loads(path.read_text())
    for block in cassette["response"]["content"]:
        if block["type"] == "text":
            block["text"] = json.dumps({"defendant": "JOHN DOE", "counts": "several"})
    path.write_text(json.dumps(cassette))

    monkeypatch.setattr(settings, "MODEL_GATEWAY_MODE", "replay")
    with pytest.raises(SchemaMismatchError):
        await call_model(req)


async def test_auth_error_propagates(live: MockAnthropic) -> None:
    live.queue(error_response(401, "invalid x-api-key"))
    with pytest.raises(AuthError) as exc_info:
        await call_model(_request())
    assert len(live.requests) == 1, "401 is never retried"
    assert exc_info.value.record is not None
    failures = [
        e
        for e in measurements.events(measurements.MeasurementKind.MODEL_CALL)
        if e.payload["outcome"] == "AuthError"
    ]
    assert len(failures) == 1


@pytest.mark.parametrize("mode", ["live", "record"])
async def test_missing_key_fails_fast(
    mode: str, monkeypatch: pytest.MonkeyPatch, store: CassetteStore
) -> None:
    mock = MockAnthropic(api_message({"defendant": "x", "counts": 1}))
    gateway.set_client(mock.client())
    monkeypatch.setattr(settings, "MODEL_GATEWAY_MODE", mode)
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    with using_fixtures(FIXTURE), pytest.raises(AuthError, match="ANTHROPIC_API_KEY"):
        await call_model(_request())
    assert mock.requests == []


async def test_refusal_raises(live: MockAnthropic) -> None:
    live.queue(api_message("I can't help with that.", stop_reason="refusal"))
    with pytest.raises(RefusalError):
        await call_model(_request())


async def test_truncation_raises(live: MockAnthropic) -> None:
    live.queue(api_message('{"defendant": "JOHN', stop_reason="max_tokens"))
    with pytest.raises(TruncatedResponseError, match="max_tokens"):
        await call_model(_request())


async def test_thinking_blocks_skipped(live: MockAnthropic) -> None:
    response = api_message({"defendant": "JOHN DOE", "counts": 1}, thinking=True)
    assert response["content"][0]["type"] == "thinking"  # type: ignore[index]
    live.queue(response)
    result = await call_model(_request())
    assert result.data == Extraction(defendant="JOHN DOE", counts=1)


async def test_model_allowlist(live: MockAnthropic) -> None:
    for model in settings.CLAUDE_MODELS_ALLOWED:
        live.queue(api_message({"defendant": "x", "counts": 1}, model=model))
        result = await call_model(_request(model=model))
        assert result.record.model_requested == model
        assert live.requests[-1]["model"] == model

    for rejected in ("claude-sonnet-4-20250514", "claude-fable-5-1", "gpt-4o"):
        with pytest.raises(ModelNotAllowedError, match="allowlist"):
            await call_model(_request(model=rejected))
        with pytest.raises(ModelNotAllowedError):
            with use_model(rejected):
                pass
    assert len(live.requests) == len(settings.CLAUDE_MODELS_ALLOWED)
    check_configuration()


async def test_run_model_selection(live: MockAnthropic) -> None:
    live.queue(api_message({"defendant": "x", "counts": 1}, model="claude-haiku-5-5"))
    with use_model("claude-haiku-5-5"):
        result = await call_model(_request())
    assert result.record.model_requested == "claude-haiku-5-5"
    live.queue(api_message({"defendant": "x", "counts": 1}))
    result = await call_model(_request())
    assert result.record.model_requested == settings.CLAUDE_MODEL_PRIMARY == "claude-opus-5-5"


async def test_no_fallbacks_or_sampling_params(live: MockAnthropic) -> None:
    live.queue(api_message({"defendant": "x", "counts": 1}))
    await call_model(_request())
    (body,) = live.requests
    for forbidden in ("fallbacks", "temperature", "top_p", "top_k"):
        assert forbidden not in body
    assert body["output_config"]["effort"] == "high"  # type: ignore[index]
    assert body["output_config"]["format"]["type"] == "json_schema"  # type: ignore[index]


async def test_cassettes_contain_no_headers_or_keys(
    record: MockAnthropic, store: CassetteStore
) -> None:
    await _record_one(record, api_message({"defendant": "x", "counts": 1}), _request())
    assert record.request_headers[0]["x-api-key"] == TEST_API_KEY  # sent, but...
    (path,) = list(store.root.rglob("*.json"))
    text = path.read_text()
    assert TEST_API_KEY not in text  # ...never stored
    assert "x-api-key" not in text and "headers" not in json.loads(text)["request"]
    assert json.loads(text)["fixture_ids"] == [FIXTURE]


async def test_record_requires_fixture_ids(record: MockAnthropic) -> None:
    record.queue(api_message({"defendant": "x", "counts": 1}))
    with pytest.raises(ValueError, match="using_fixtures"):
        await call_model(_request())
    assert record.requests == []


async def test_abstention_is_not_error(live: MockAnthropic) -> None:
    live.queue(api_message({"abstained": True, "abstention_reason": "The record does not say."}))
    result = await call_model(_request(response_model=Finding))
    assert result.data.abstained is True
    assert result.record.outcome == "ok"
    (event,) = measurements.events(measurements.MeasurementKind.MODEL_CALL)
    assert event.payload["outcome"] == "ok"


async def test_usage_recorded(
    record: MockAnthropic, store: CassetteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    req = _request()
    record.queue(api_message({"defendant": "x", "counts": 1}, input_tokens=1000, output_tokens=500))
    with using_fixtures(FIXTURE):
        recorded = await call_model(req)
    assert recorded.record.cassette == "recorded"
    assert recorded.record.input_tokens == 1000 and recorded.record.output_tokens == 500
    expected = (1000 * 4 + 500 * 20) / 1_000_000
    assert recorded.record.cost_usd == pytest.approx(expected)
    assert recorded.record.model_returned == "claude-opus-5-5"

    monkeypatch.setattr(settings, "MODEL_GATEWAY_MODE", "replay")
    hit = await call_model(req)
    assert hit.record.cassette == "hit"
    assert hit.record.cost_usd == pytest.approx(expected), "would-be cost on a hit"
    assert hit.record.billed_usd == 0.0
    assert len(measurements.events(measurements.MeasurementKind.MODEL_CALL)) == 2


# ---------------------------------------------------------------------------
# Transport, retries, and pricing
# ---------------------------------------------------------------------------


async def test_retries_recorded(live: MockAnthropic) -> None:
    live.queue(error_response(529, "overloaded"), api_message({"defendant": "x", "counts": 1}))
    result = await call_model(_request())
    assert result.record.retries == 1
    assert len(live.requests) == 2


async def test_transport_error_after_retries(live: MockAnthropic) -> None:
    live.queue(*(error_response(500) for _ in range(3)))
    with pytest.raises(TransportError):
        await call_model(_request())
    assert len(live.requests) == 3  # one call plus MODEL_GATEWAY_MAX_RETRIES=2


async def test_rate_limit_is_transport_error(live: MockAnthropic) -> None:
    live.queue(*(error_response(429) for _ in range(3)))
    with pytest.raises(TransportError):
        await call_model(_request())


async def test_bad_request_is_invalid_request(live: MockAnthropic) -> None:
    live.queue(error_response(400, "output_config.format: schema not supported"))
    with pytest.raises(InvalidRequestError, match="400"):
        await call_model(_request())


async def test_non_json_is_malformed(live: MockAnthropic) -> None:
    live.queue(api_message("The defendant is John Doe."))
    with pytest.raises(MalformedResponseError):
        await call_model(_request())


def test_dict_fields_rejected_before_any_call() -> None:
    class Free(BaseModel):
        anything: dict[str, str]

    with pytest.raises(TypeError, match="free-form object"):
        gateway._response_schema(Free)


def test_haiku_tiered_pricing() -> None:
    low = cost_usd("claude-haiku-5-5", input_tokens=100_000, output_tokens=1_000_000)
    high = cost_usd("claude-haiku-5-5", input_tokens=100_001, output_tokens=1_000_000)
    assert low == pytest.approx(0.10 * 0.1 + 0.50)
    assert high == pytest.approx(0.50 * 0.100001 + 2.50)
    # Cache reads count toward the prompt length that selects the tier.
    cached = cost_usd(
        "claude-haiku-5-5", input_tokens=10, output_tokens=0, cache_read_input_tokens=100_000
    )
    assert cached == pytest.approx((10 * 0.50 + 100_000 * 0.05) / 1_000_000)


async def test_startup_fails_fast_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.main import app, lifespan

    monkeypatch.setattr(settings, "MODEL_GATEWAY_MODE", "live")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    with pytest.raises(AuthError, match="ANTHROPIC_API_KEY"):
        async with lifespan(app):
            pass

    monkeypatch.setattr(settings, "MODEL_GATEWAY_MODE", "replay")
    async with lifespan(app):
        pass  # replay needs no key
