"""CourtListener API client for case law search and citation verification.

Primary data source for Georgia appellate cases and federal authority.
API docs: https://www.courtlistener.com/api/rest/v3/

Every request goes through ``_get``, which applies the gateway's record/replay modes
(PHASE_1_MODEL_GATEWAY.md §5.4): ``replay`` serves recorded responses and raises on a
miss, ``record`` calls the API and writes a cassette (no headers, so no token), and
``live`` calls the API directly.

A failed request raises ``CourtListenerError``. It used to return an empty list, so
"the search failed" and "no case law found" were the same result.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import JsonValue

from src.config import settings
from src.services import measurements
from src.services.model_gateway.cassettes import (
    ExternalCassette,
    ExternalCassetteStore,
    current_fixture_ids,
    default_external_store,
    external_key,
)
from src.services.model_gateway.gateway import current_mode

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.courtlistener.com/api/rest/v3"
_TIMEOUT = 30.0

# Court IDs for CourtListener
GEORGIA_COURTS = {
    "ga": "Supreme Court of Georgia",
    "gactapp": "Court of Appeals of Georgia",
}

FEDERAL_COURTS = {
    "scotus": "Supreme Court of the United States",
    "ca11": "United States Court of Appeals for the Eleventh Circuit",
}

ALL_TARGET_COURTS = {**GEORGIA_COURTS, **FEDERAL_COURTS}

_SERVICE = "courtlistener"


class CourtListenerError(Exception):
    """A CourtListener request failed (transport error or HTTP error status)."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


class CourtListenerCassetteMiss(CourtListenerError):
    """Replay mode found no recording for this request. Never falls through."""


class CourtListenerClient:
    """Async client for the CourtListener REST API."""

    def __init__(
        self,
        api_key: str | None = None,
        *,
        agent_id: str = "unknown",
        transport: httpx.AsyncBaseTransport | None = None,
        store: ExternalCassetteStore | None = None,
    ) -> None:
        self._api_key = api_key or settings.COURTLISTENER_API_KEY
        self._headers: dict[str, str] = {}
        if self._api_key:
            self._headers["Authorization"] = f"Token {self._api_key}"
        self._call_count = 0
        self._agent_id = agent_id
        self._transport = transport
        self._store = store

    @property
    def call_count(self) -> int:
        return self._call_count

    def reset_call_count(self) -> None:
        self._call_count = 0

    async def _send(self, url: str, params: list[tuple[str, str]]) -> tuple[int, JsonValue]:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, transport=self._transport) as client:
                resp = await client.get(url, params=params, headers=self._headers)
        except httpx.RequestError as exc:
            raise CourtListenerError(f"CourtListener request error for {url}: {exc}") from exc
        if resp.status_code >= 400:
            return resp.status_code, {"error_text": resp.text[:2000]}
        try:
            return resp.status_code, resp.json()
        except ValueError as exc:
            raise CourtListenerError(f"CourtListener returned non-JSON for {url}") from exc

    async def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        *,
        not_found_ok: bool = False,
    ) -> JsonValue:
        url = f"{_BASE_URL}{path}"
        param_list = sorted((k, str(v)) for k, v in (params or {}).items())
        key = external_key(_SERVICE, "GET", url, param_list)
        mode = current_mode()
        self._call_count += 1

        outcome = "bypassed"
        if mode in ("replay", "record"):
            store = self._store or default_external_store()
            cassette = store.load(_SERVICE, key)
            if cassette is not None:
                outcome = "hit"
                status, body = cassette.status, cassette.response
            elif mode == "replay":
                raise CourtListenerCassetteMiss(
                    f"No CourtListener cassette for GET {url} {param_list} (key {key[:12]}, "
                    f"expected at {store.path_for(_SERVICE, key)}). Record it with "
                    "MODEL_GATEWAY_MODE=record."
                )
            else:
                if not current_fixture_ids():
                    raise ValueError(
                        "Record mode requires the fixture(s) the request was built from: "
                        "wrap the call in cassettes.using_fixtures(...)."
                    )
                outcome = "recorded"
                status, body = await self._send(url, param_list)
                store.save(
                    ExternalCassette(
                        key=key,
                        service=_SERVICE,
                        recorded_at=datetime.now(timezone.utc),
                        method="GET",
                        url=url,
                        params=param_list,
                        fixture_ids=list(current_fixture_ids()),
                        status=status,
                        response=body,
                    )
                )
        else:
            status, body = await self._send(url, param_list)

        measurements.record(
            measurements.Measurement(
                kind=measurements.MeasurementKind.EXTERNAL_CALL,
                agent_id=self._agent_id,
                payload={"service": _SERVICE, "path": path, "status": status, "cassette": outcome},
            )
        )
        if status == 404 and not_found_ok:
            return None
        if status >= 400:
            raise CourtListenerError(f"CourtListener GET {path} returned {status}", status=status)
        return body

    async def search_opinions(
        self,
        query: str,
        court_ids: list[str] | None = None,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Search for court opinions matching a query.

        Args:
            query: Free-text search query.
            court_ids: Limit to specific courts (e.g., ["ga", "gactapp"]).
            max_results: Maximum number of results to return.

        Returns:
            List of opinion result dicts with keys: case_name, citation,
            court, date_filed, snippet, absolute_url, cluster_id. Empty only when
            the search found nothing; a failed search raises ``CourtListenerError``.
        """
        params: dict[str, Any] = {
            "q": query,
            "type": "o",  # opinions
            "order_by": "score desc",
            "page_size": min(max_results, 20),
        }
        if court_ids:
            params["court"] = " ".join(court_ids)

        data = await self._get("/search/", params)
        items = data.get("results", []) if isinstance(data, dict) else []

        results: list[dict[str, Any]] = []
        for item in items[:max_results]:
            results.append(
                {
                    "case_name": item.get("caseName", ""),
                    "citation": _extract_citation(item),
                    "court": item.get("court", ""),
                    "court_id": item.get("court_id", ""),
                    "date_filed": item.get("dateFiled", ""),
                    "snippet": item.get("snippet", ""),
                    "absolute_url": item.get("absolute_url", ""),
                    "cluster_id": item.get("cluster_id"),
                    "docket_id": item.get("docket_id"),
                }
            )

        return results

    async def get_opinion_cluster(self, cluster_id: int) -> dict[str, Any] | None:
        """Retrieve full opinion cluster by ID; None only if CourtListener has no such cluster.

        Returns the cluster object with case name, citations, sub-opinions, etc.
        """
        data = await self._get(f"/clusters/{cluster_id}/", not_found_ok=True)
        return data if isinstance(data, dict) else None

    async def get_opinion_text(self, opinion_id: int) -> str | None:
        """Retrieve the text of an opinion by ID; None if there is no such opinion or text."""
        data = await self._get(f"/opinions/{opinion_id}/", not_found_ok=True)
        if not isinstance(data, dict):
            return None
        # Try plain_text first, then html_with_citations, then html
        for field in ("plain_text", "html_with_citations", "html"):
            text = data.get(field, "")
            if isinstance(text, str) and text:
                return text
        return None

    async def get_citing_cases(self, cluster_id: int) -> list[dict[str, Any]]:
        """Find cases that cite a given cluster (for citation network / Shepardizing)."""
        data = await self._get(
            "/search/",
            {
                "q": f"cites:({cluster_id})",
                "type": "o",
                "order_by": "dateFiled desc",
                "page_size": 20,
            },
        )
        items = data.get("results", []) if isinstance(data, dict) else []

        results = []
        for item in items:
            results.append(
                {
                    "case_name": item.get("caseName", ""),
                    "citation": _extract_citation(item),
                    "court": item.get("court", ""),
                    "date_filed": item.get("dateFiled", ""),
                    "snippet": item.get("snippet", ""),
                }
            )
        return results

    async def search_by_citation(self, citation: str) -> dict[str, Any] | None:
        """Look up a specific case by its citation string.

        Returns the first matching result, or None.
        """
        results = await self.search_opinions(
            query=f'citation:("{citation}")',
            max_results=3,
        )

        if not results:
            # Second strategy (not an error fallback): search the citation text directly
            results = await self.search_opinions(query=citation, max_results=3)

        if results:
            return results[0]
        return None

    async def verify_case_exists(self, citation: str) -> dict[str, Any]:
        """Attempt to verify a case citation exists.

        Returns a dict with: found (bool), case_data (dict or None),
        method (str describing how it was found).
        """
        result = await self.search_by_citation(citation)
        if result and result.get("case_name"):
            return {
                "found": True,
                "case_data": result,
                "method": "CourtListener citation search",
            }

        return {
            "found": False,
            "case_data": None,
            "method": "CourtListener search — not found",
        }


def _extract_citation(item: dict[str, Any]) -> str:
    """Extract the best available citation string from a search result."""
    # CourtListener returns citations in various formats
    citation_list = item.get("citation", [])
    if isinstance(citation_list, list) and citation_list:
        return citation_list[0]
    if isinstance(citation_list, str) and citation_list:
        return citation_list

    # Fallback: construct from case name and date
    name = item.get("caseName", "Unknown")
    date = item.get("dateFiled", "")
    if date:
        return f"{name} ({date[:4]})"
    return name
