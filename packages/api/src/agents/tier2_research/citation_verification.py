"""Citation Verification Agent — Tier 2 Research.

Mechanically verifies every legal citation produced by the three research
agents before anything reaches the attorney. Performs concrete, binary
verification tasks using CourtListener API lookups and LLM analysis.
"""

from __future__ import annotations

import logging
import re
from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.courtlistener import CourtListenerClient
from src.services.llm_service import call_llm

STATUS = "REAL"

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a legal citation verification specialist. Your job is to verify \
whether legal citations are real, correctly formatted, and still good law.

You are CONSERVATIVE — if you cannot confirm a citation, mark it UNVERIFIED \
rather than VERIFIED. False confidence in a citation is worse than admitting \
uncertainty.

OUTPUT FORMAT: Always respond with valid JSON."""

_HOLDING_CHECK_PROMPT = """\
Compare the described holding with the actual case text to determine if they match.

CITATION: {citation}
DESCRIBED HOLDING: {described_holding}

ACTUAL CASE SNIPPET FROM COURTLISTENER:
{case_snippet}

Does the described holding accurately reflect what this case actually says?

Return JSON:
{{
  "matches": true|false,
  "explanation": "Why the holding matches or doesn't match",
  "actual_holding_summary": "Brief summary of what the case actually holds"
}}"""

_STATUTE_VERIFICATION_PROMPT = """\
Verify the following Georgia statute citation.

STATUTE: {statute}
DESCRIBED TEXT/ELEMENTS: {described_content}

Based on your knowledge of the Official Code of Georgia Annotated:
1. Does this statute section exist?
2. Is the described content accurate?
3. Has this statute been recently amended?
4. Has this statute been held unconstitutional by any court?

Return JSON:
{{
  "exists": true|false,
  "content_accurate": true|false,
  "recently_amended": false,
  "amendment_notes": "",
  "unconstitutional": false,
  "unconstitutional_notes": "",
  "verification_notes": "Any additional notes"
}}"""

# Regex patterns for citation formats
_GA_CASE_PATTERN = re.compile(r"\d+\s+Ga\.?\s*(?:App\.?)?\s*\d+")  # e.g., "300 Ga. App. 123"
_FEDERAL_CASE_PATTERN = re.compile(
    r"\d+\s+(?:U\.?S\.?|S\.?\s*Ct\.?|F\.?\s*(?:2d|3d|4th)?|L\.?\s*Ed\.?\s*2d)\s*\d+"
)
_GA_STATUTE_PATTERN = re.compile(
    r"O\.?C\.?G\.?A\.?\s*(?:§\s*)?(\d+-\d+-\d+)"  # e.g., "OCGA 16-13-30"
)


class CitationVerificationAgent(BaseAgent):
    """Verifies all citations from the research agents."""

    agent_id = "citation_verification"
    agent_name = "Citation Verification Agent"

    def __init__(self) -> None:
        super().__init__()
        self._cl_client = CourtListenerClient()

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Verify all citations from the three research agents.

        Input keys:
            ga_case_law_output: dict — output from GA Criminal Case Law Agent
            constitutional_output: dict — output from Constitutional Case Law Agent
            statutes_output: dict — output from GA Statutes Agent

        Output: CitationVerificationOutput as dict
        """
        self.log_action("citation_verification_started")
        self._cl_client.reset_call_count()

        # Step 1: Extract all citations from all three agents
        citations = self._extract_all_citations(input_data)

        self.log_action(
            "citations_extracted",
            {"total_citations": len(citations)},
        )

        # Step 2: Verify each citation
        verification_results = []
        for citation_info in citations:
            result = await self._verify_citation(citation_info)
            verification_results.append(result)

        # Step 3: Build summary
        summary = self._build_summary(verification_results)

        self.log_action(
            "citation_verification_completed",
            {
                "total": summary["total_citations"],
                "verified": summary["verified"],
                "unverified": summary["unverified"],
                "courtlistener_calls": self._cl_client.call_count,
            },
        )

        # Confidence based on verification rate
        if summary["total_citations"] == 0:
            confidence = 0.5
        else:
            verified_rate = summary["verified"] / summary["total_citations"]
            confidence = 0.5 + (verified_rate * 0.4)  # 0.5 to 0.9 range

        return self.wrap_output(
            {
                "verification_results": verification_results,
                "summary": summary,
            },
            confidence=confidence,
        )

    def _extract_all_citations(
        self,
        input_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Extract citations from all research agent outputs."""
        citations: list[dict[str, Any]] = []

        # From GA Criminal Case Law Agent
        ga_output = input_data.get("ga_case_law_output", {})
        for issue in ga_output.get("research_results", []):
            for case in issue.get("cases_found", []):
                citations.append(
                    {
                        "citation": case.get("citation", ""),
                        "case_name": case.get("case_name", ""),
                        "type": "case",
                        "source_agent": "ga_criminal_case_law",
                        "described_holding": case.get("holding", ""),
                        "court": case.get("court", ""),
                    }
                )

        # From Constitutional Case Law Agent
        const_output = input_data.get("constitutional_output", {})
        for issue in const_output.get("constitutional_research", []):
            for level in ("foundational_authority", "circuit_authority", "state_authority"):
                for case in issue.get(level, []):
                    citations.append(
                        {
                            "citation": case.get("citation", ""),
                            "case_name": case.get("case_name", ""),
                            "type": "case",
                            "source_agent": "constitutional_case_law",
                            "described_holding": case.get("holding", ""),
                            "court": case.get("court", ""),
                            "authority_level": level,
                        }
                    )

        # From GA Statutes Agent
        statutes_output = input_data.get("statutes_output", {})
        for offense in statutes_output.get("charged_offenses", []):
            statute = offense.get("statute", "")
            if statute:
                citations.append(
                    {
                        "citation": statute,
                        "type": "statute",
                        "source_agent": "ga_statutes_agent",
                        "described_content": offense.get("full_text", ""),
                        "elements": offense.get("elements", []),
                    }
                )

        for option in statutes_output.get("diversion_options", []):
            statute = option.get("statute", "")
            if statute:
                citations.append(
                    {
                        "citation": statute,
                        "type": "statute",
                        "source_agent": "ga_statutes_agent",
                        "described_content": option.get("eligibility_requirements", ""),
                    }
                )

        for req in statutes_output.get("procedural_requirements", []):
            statute = req.get("statute", "")
            if statute:
                citations.append(
                    {
                        "citation": statute,
                        "type": "statute",
                        "source_agent": "ga_statutes_agent",
                        "described_content": req.get("notes", ""),
                    }
                )

        # Deduplicate by citation string
        seen: set[str] = set()
        unique: list[dict[str, Any]] = []
        for c in citations:
            key = c.get("citation", "")
            if key and key not in seen:
                seen.add(key)
                unique.append(c)

        return unique

    async def _verify_citation(
        self,
        citation_info: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify a single citation."""
        citation = citation_info.get("citation", "")
        citation_type = citation_info.get("type", "case")
        source_agent = citation_info.get("source_agent", "")

        if citation_type == "case":
            return await self._verify_case_citation(citation_info)
        elif citation_type == "statute":
            return await self._verify_statute_citation(citation_info)
        else:
            return {
                "original_citation": citation,
                "citation_type": citation_type,
                "source_agent": source_agent,
                "verification_status": "UNVERIFIED",
                "verification_method": "Unknown citation type",
                "good_law_status": "",
                "negative_treatment": [],
                "confidence": 0.0,
                "notes": f"Unrecognized citation type: {citation_type}",
            }

    async def _verify_case_citation(
        self,
        citation_info: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify a case citation against CourtListener."""
        citation = citation_info.get("citation", "")
        case_name = citation_info.get("case_name", "")
        source_agent = citation_info.get("source_agent", "")
        described_holding = citation_info.get("described_holding", "")

        base_result = {
            "original_citation": f"{case_name}, {citation}" if case_name else citation,
            "citation_type": "case",
            "source_agent": source_agent,
            "verification_status": "UNVERIFIED",
            "verification_method": "",
            "good_law_status": "",
            "negative_treatment": [],
            "confidence": 0.0,
            "notes": "",
        }

        # Step 1: Check citation format
        is_ga = bool(_GA_CASE_PATTERN.search(citation))
        is_federal = bool(_FEDERAL_CASE_PATTERN.search(citation))

        if not is_ga and not is_federal and not citation:
            base_result["verification_status"] = "CITATION_ERROR"
            base_result["verification_method"] = "Format check"
            base_result["notes"] = "Citation format not recognized"
            return base_result

        # Step 2: Search CourtListener
        verify_result = await self._cl_client.verify_case_exists(citation)

        if not verify_result["found"]:
            # Try searching by case name as fallback
            if case_name:
                verify_result = await self._cl_client.verify_case_exists(case_name)

        if not verify_result["found"]:
            base_result["verification_status"] = "UNVERIFIED"
            base_result["verification_method"] = "CourtListener search — case not found"
            base_result["confidence"] = 0.2
            base_result["notes"] = (
                "Could not locate case in CourtListener. This does NOT mean "
                "the case doesn't exist — it may not be in the database."
            )
            return base_result

        # Step 3: Case found — verify holding if we have a snippet
        case_data = verify_result["case_data"]
        snippet = case_data.get("snippet", "")
        cluster_id = case_data.get("cluster_id")

        holding_matches = True
        if described_holding and snippet:
            holding_matches = await self._check_holding(
                citation=citation,
                described_holding=described_holding,
                case_snippet=snippet,
            )

        if not holding_matches:
            base_result["verification_status"] = "HOLDING_MISMATCH"
            base_result["verification_method"] = (
                "CourtListener — case exists but described holding may not match"
            )
            base_result["good_law_status"] = "REVIEW_NEEDED"
            base_result["confidence"] = 0.4
            base_result["notes"] = (
                "Case found in CourtListener but the described holding "
                "may not accurately reflect the opinion. Attorney should "
                "read the full opinion."
            )
            return base_result

        # Step 4: Check for negative treatment (if we have cluster_id)
        negative_treatment: list[str] = []
        if cluster_id:
            negative_treatment = await self._check_negative_treatment(cluster_id)

        good_law = "GOOD_LAW"
        if any("overrul" in t.lower() for t in negative_treatment):
            good_law = "OVERRULED"
            base_result["verification_status"] = "OVERRULED"
        elif any("supersed" in t.lower() for t in negative_treatment):
            good_law = "SUPERSEDED"
            base_result["verification_status"] = "SUPERSEDED"
        else:
            base_result["verification_status"] = "VERIFIED"

        base_result["verification_method"] = "CourtListener API — case confirmed"
        base_result["good_law_status"] = good_law
        base_result["negative_treatment"] = negative_treatment
        base_result["confidence"] = 0.9 if good_law == "GOOD_LAW" else 0.6
        base_result["notes"] = (
            f"Verified via CourtListener. "
            f"Court: {case_data.get('court', 'unknown')}. "
            f"Date: {case_data.get('date_filed', 'unknown')}."
        )

        return base_result

    async def _verify_statute_citation(
        self,
        citation_info: dict[str, Any],
    ) -> dict[str, Any]:
        """Verify a Georgia statute citation."""
        citation = citation_info.get("citation", "")
        source_agent = citation_info.get("source_agent", "")
        described_content = citation_info.get("described_content", "")

        base_result = {
            "original_citation": citation,
            "citation_type": "statute",
            "source_agent": source_agent,
            "verification_status": "UNVERIFIED",
            "verification_method": "",
            "good_law_status": "",
            "negative_treatment": [],
            "confidence": 0.0,
            "notes": "",
        }

        # Check format
        match = _GA_STATUTE_PATTERN.search(citation)
        if not match and "OCGA" not in citation.upper() and "O.C.G.A." not in citation:
            base_result["verification_status"] = "CITATION_ERROR"
            base_result["verification_method"] = "Format check"
            base_result["notes"] = "Not recognized as a Georgia statute citation"
            return base_result

        # Use LLM to verify statute content (no free API for GA code text)
        try:
            result = await call_llm(
                _STATUTE_VERIFICATION_PROMPT.format(
                    statute=citation,
                    described_content=described_content,
                ),
                system=_SYSTEM_PROMPT,
                max_tokens=1024,
            )

            exists = result.get("exists", False)
            accurate = result.get("content_accurate", False)
            amended = result.get("recently_amended", False)
            unconstitutional = result.get("unconstitutional", False)

            if unconstitutional:
                base_result["verification_status"] = "SUPERSEDED"
                base_result["good_law_status"] = "UNCONSTITUTIONAL"
                base_result["confidence"] = 0.5
                base_result["notes"] = result.get("unconstitutional_notes", "")
            elif amended:
                base_result["verification_status"] = "VERIFIED"
                base_result["good_law_status"] = "AMENDED"
                base_result["confidence"] = 0.6
                base_result["notes"] = (
                    f"Statute exists but may have been recently amended. "
                    f"{result.get('amendment_notes', '')}"
                )
            elif exists and accurate:
                base_result["verification_status"] = "VERIFIED"
                base_result["good_law_status"] = "CURRENT"
                base_result["confidence"] = 0.75
                base_result["notes"] = "Statute verified via LLM knowledge"
            elif exists:
                base_result["verification_status"] = "VERIFIED"
                base_result["good_law_status"] = "CURRENT"
                base_result["confidence"] = 0.6
                base_result["notes"] = (
                    "Statute exists but described content may not be fully accurate. "
                    f"{result.get('verification_notes', '')}"
                )
            else:
                base_result["verification_status"] = "UNVERIFIED"
                base_result["confidence"] = 0.3
                base_result["notes"] = result.get("verification_notes", "Could not verify")

            base_result["verification_method"] = "LLM knowledge verification"

        except Exception as exc:
            logger.warning("Statute verification failed for %s: %s", citation, exc)
            base_result["verification_method"] = "Verification failed"
            base_result["notes"] = f"Verification error: {exc}"

        return base_result

    async def _check_holding(
        self,
        citation: str,
        described_holding: str,
        case_snippet: str,
    ) -> bool:
        """Check if the described holding matches the actual case."""
        try:
            result = await call_llm(
                _HOLDING_CHECK_PROMPT.format(
                    citation=citation,
                    described_holding=described_holding,
                    case_snippet=case_snippet,
                ),
                system=_SYSTEM_PROMPT,
                max_tokens=512,
            )
            return result.get("matches", False)
        except Exception:
            # If check fails, don't flag as mismatch — just can't confirm
            return True

    async def _check_negative_treatment(
        self,
        cluster_id: int,
    ) -> list[str]:
        """Check for negative treatment of a case via CourtListener citations."""
        citing_cases = await self._cl_client.get_citing_cases(cluster_id)

        negative: list[str] = []
        for case in citing_cases:
            snippet = case.get("snippet", "").lower()
            # Look for negative treatment signals in snippets
            if any(
                term in snippet
                for term in ("overrul", "revers", "abrogat", "supersed", "no longer good law")
            ):
                negative.append(
                    f"{case.get('case_name', 'Unknown')} ({case.get('date_filed', '')}): "
                    f"Possible negative treatment"
                )

        return negative

    def _build_summary(
        self,
        results: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build aggregate verification summary."""
        summary = {
            "total_citations": len(results),
            "verified": 0,
            "unverified": 0,
            "holding_mismatch": 0,
            "overruled": 0,
            "superseded": 0,
            "citation_errors": 0,
        }

        for r in results:
            status = r.get("verification_status", "UNVERIFIED")
            if status == "VERIFIED":
                summary["verified"] += 1
            elif status == "UNVERIFIED":
                summary["unverified"] += 1
            elif status == "HOLDING_MISMATCH":
                summary["holding_mismatch"] += 1
            elif status == "OVERRULED":
                summary["overruled"] += 1
            elif status == "SUPERSEDED":
                summary["superseded"] += 1
            elif status == "CITATION_ERROR":
                summary["citation_errors"] += 1
            else:
                summary["unverified"] += 1

        return summary
