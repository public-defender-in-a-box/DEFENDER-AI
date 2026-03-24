"""CourtListener API client for case law search and citation verification.

Primary data source for Georgia appellate cases and federal authority.
API docs: https://www.courtlistener.com/api/rest/v3/
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from src.config import settings

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


class CourtListenerClient:
    """Async client for the CourtListener REST API."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or settings.COURTLISTENER_API_KEY
        self._headers: dict[str, str] = {}
        if self._api_key:
            self._headers["Authorization"] = f"Token {self._api_key}"
        self._call_count = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def reset_call_count(self) -> None:
        self._call_count = 0

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
            court, date_filed, snippet, absolute_url, cluster_id.
        """
        params: dict[str, Any] = {
            "q": query,
            "type": "o",  # opinions
            "order_by": "score desc",
            "page_size": min(max_results, 20),
        }
        if court_ids:
            params["court"] = " ".join(court_ids)

        self._call_count += 1

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{_BASE_URL}/search/",
                    params=params,
                    headers=self._headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.warning("CourtListener search failed (%s): %s", exc.response.status_code, query)
            return []
        except httpx.RequestError as exc:
            logger.warning("CourtListener request error: %s", exc)
            return []

        results: list[dict[str, Any]] = []
        for item in data.get("results", [])[:max_results]:
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
        """Retrieve full opinion cluster by ID.

        Returns the cluster object with case name, citations, sub-opinions, etc.
        """
        self._call_count += 1

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{_BASE_URL}/clusters/{cluster_id}/",
                    headers=self._headers,
                )
                resp.raise_for_status()
                return resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("CourtListener cluster fetch failed: %s", exc)
            return None

    async def get_opinion_text(self, opinion_id: int) -> str | None:
        """Retrieve the text of an opinion by ID."""
        self._call_count += 1

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{_BASE_URL}/opinions/{opinion_id}/",
                    headers=self._headers,
                )
                resp.raise_for_status()
                data = resp.json()

            # Try plain_text first, then html_with_citations, then html
            for field in ("plain_text", "html_with_citations", "html"):
                text = data.get(field, "")
                if text:
                    return text

            return None
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("CourtListener opinion text fetch failed: %s", exc)
            return None

    async def get_citing_cases(self, cluster_id: int) -> list[dict[str, Any]]:
        """Find cases that cite a given cluster (for citation network / Shepardizing)."""
        self._call_count += 1

        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.get(
                    f"{_BASE_URL}/search/",
                    params={
                        "q": f"cites:({cluster_id})",
                        "type": "o",
                        "order_by": "dateFiled desc",
                        "page_size": 20,
                    },
                    headers=self._headers,
                )
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            logger.warning("CourtListener citing-cases fetch failed: %s", exc)
            return []

        results = []
        for item in data.get("results", []):
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
            # Fallback: search by the citation text directly
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
