"""CourtListener record/replay and failure semantics (PHASE_1_MODEL_GATEWAY.md §5.4).

The client runs on an ``httpx.MockTransport``; cassettes go to a temporary directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from src.config import settings
from src.services import measurements
from src.services.courtlistener import (
    CourtListenerCassetteMiss,
    CourtListenerClient,
    CourtListenerError,
)
from src.services.model_gateway import using_fixtures
from src.services.model_gateway.cassettes import ExternalCassetteStore

FIXTURE = "tests/test_research_agents.py::williams_full_input"
SEARCH = {
    "results": [
        {
            "caseName": "Synthetic v. State",
            "citation": ["900 Ga. App. 100"],
            "court": "Court of Appeals of Georgia",
            "dateFiled": "2020-05-01",
            "snippet": "nervousness alone",
            "cluster_id": 9000001,
        }
    ]
}


class Server:
    def __init__(self, *responses: httpx.Response) -> None:
        self.requests: list[httpx.Request] = []
        self._responses = list(responses)

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self._responses.pop(0)


@pytest.fixture
def store(tmp_path: Path) -> ExternalCassetteStore:
    return ExternalCassetteStore(tmp_path)


def _client(server: Server, store: ExternalCassetteStore, key: str | None = None):
    return CourtListenerClient(
        api_key=key,
        agent_id="ga_criminal_case_law",
        transport=httpx.MockTransport(server.handler),
        store=store,
    )


async def test_replay_miss_raises_without_network(store: ExternalCassetteStore) -> None:
    server = Server(httpx.Response(200, json=SEARCH))
    with pytest.raises(CourtListenerCassetteMiss):
        await _client(server, store).search_opinions("reasonable suspicion")
    assert server.requests == []


async def test_record_then_replay(
    store: ExternalCassetteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = Server(httpx.Response(200, json=SEARCH))
    monkeypatch.setattr(settings, "MODEL_GATEWAY_MODE", "record")
    with using_fixtures(FIXTURE):
        recorded = await _client(server, store, key="cl-test-token").search_opinions(
            "reasonable suspicion", court_ids=["ga", "gactapp"]
        )
    assert server.requests[0].headers["Authorization"] == "Token cl-test-token"
    (path,) = list(store.root.rglob("*.json"))
    text = path.read_text()
    assert "cl-test-token" not in text and "Authorization" not in text
    assert json.loads(text)["fixture_ids"] == [FIXTURE]

    monkeypatch.setattr(settings, "MODEL_GATEWAY_MODE", "replay")
    replayed = await _client(Server(), store).search_opinions(
        "reasonable suspicion", court_ids=["ga", "gactapp"]
    )
    assert replayed == recorded
    assert replayed[0]["citation"] == "900 Ga. App. 100"
    outcomes = [
        e.payload["cassette"]
        for e in measurements.events(measurements.MeasurementKind.EXTERNAL_CALL)
    ]
    assert outcomes == ["recorded", "hit"]


async def test_record_requires_fixture_ids(
    store: ExternalCassetteStore, monkeypatch: pytest.MonkeyPatch
) -> None:
    server = Server(httpx.Response(200, json=SEARCH))
    monkeypatch.setattr(settings, "MODEL_GATEWAY_MODE", "record")
    with pytest.raises(ValueError, match="using_fixtures"):
        await _client(server, store).search_opinions("q")
    assert server.requests == []


@pytest.fixture
def live(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MODEL_GATEWAY_MODE", "live")


async def test_http_error_raises_not_empty(live: None, store: ExternalCassetteStore) -> None:
    """A failed search used to return [] — indistinguishable from 'no case law found'."""
    server = Server(httpx.Response(503, text="maintenance"))
    with pytest.raises(CourtListenerError) as exc_info:
        await _client(server, store).search_opinions("q")
    assert exc_info.value.status == 503


async def test_transport_error_raises(live: None, store: ExternalCassetteStore) -> None:
    def broken(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    client = CourtListenerClient(transport=httpx.MockTransport(broken), store=store)
    with pytest.raises(CourtListenerError, match="request error"):
        await client.get_citing_cases(9000001)


async def test_not_found_cluster_is_none(live: None, store: ExternalCassetteStore) -> None:
    server = Server(httpx.Response(404, json={"detail": "Not found."}))
    assert await _client(server, store).get_opinion_cluster(1) is None


async def test_empty_search_is_empty(live: None, store: ExternalCassetteStore) -> None:
    server = Server(httpx.Response(200, json={"results": []}))
    assert await _client(server, store).search_opinions("nothing matches") == []
