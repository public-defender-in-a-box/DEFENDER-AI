"""Constitutional Law Case Law Agent — Tier 2 Research.

Finds controlling federal constitutional authority (US Supreme Court, 11th
Circuit) and Georgia state court applications for rights violations
identified in the case. Provides the full doctrinal framework, not just
individual citations.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.courtlistener import CourtListenerClient, GEORGIA_COURTS
from src.services.llm_service import call_llm

STATUS = "REAL"

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a constitutional criminal procedure specialist working for a public \
defender's office. Your expertise is 4th, 5th, 6th, and 14th Amendment law \
as applied to criminal cases in Georgia (11th Circuit).

Your job is to provide the FULL DOCTRINAL FRAMEWORK for each constitutional \
issue — the attorney needs to understand the legal standard, the hierarchy \
of authority, and how it applies to the client's specific facts.

PRINCIPLES:
1. Start with foundational US Supreme Court authority (e.g., Terry v. Ohio \
for reasonable suspicion).
2. Then find 11th Circuit cases applying those standards.
3. Then find Georgia appellate cases applying those standards.
4. Provide the legal STANDARD, not just case names — the attorney needs to \
understand the test.
5. Assess the strength of the constitutional argument honestly.
6. Only cite cases you are confident are real.

OUTPUT FORMAT: Always respond with valid JSON."""

_ISSUE_IDENTIFICATION_PROMPT = """\
Identify the constitutional criminal procedure issues in this case.

RIGHTS VIOLATION FLAGS:
{rights_flags}

FACTUAL ALLEGATIONS ABOUT STOP/SEARCH/ARREST/INTERROGATION:
{factual_allegations}

CASE SUMMARY:
{case_summary}

For each constitutional issue, identify:
1. Which amendment is implicated (fourth_amendment, fifth_amendment, \
sixth_amendment, fourteenth_amendment)
2. The specific issue (e.g., "reasonable suspicion for investigative detention")
3. The legal standard that applies
4. The foundational Supreme Court cases the attorney MUST cite
5. What 11th Circuit and Georgia search queries would find relevant applications

Return JSON:
{{
  "constitutional_issues": [
    {{
      "amendment": "fourth_amendment",
      "issue": "Reasonable suspicion for investigative detention",
      "legal_standard": "Under Terry v. Ohio, an officer may briefly detain...",
      "foundational_cases": [
        {{
          "case_name": "Terry v. Ohio",
          "citation": "392 U.S. 1 (1968)",
          "holding": "An officer may conduct a brief investigative stop..."
        }}
      ],
      "circuit_queries": ["11th Circuit reasonable suspicion Terry stop"],
      "state_queries": ["Georgia reasonable suspicion investigative detention"]
    }}
  ]
}}"""

_FRAMEWORK_ANALYSIS_PROMPT = """\
Build the complete doctrinal framework for this constitutional issue.

CONSTITUTIONAL ISSUE:
Amendment: {amendment}
Issue: {issue}
Legal Standard: {legal_standard}

FOUNDATIONAL AUTHORITY (already identified):
{foundational_cases}

11TH CIRCUIT SEARCH RESULTS:
{circuit_results}

GEORGIA STATE SEARCH RESULTS:
{state_results}

CLIENT'S FACTS:
{case_summary}

Analyze the search results and build a complete framework:

1. For circuit authority: identify the most relevant 11th Circuit cases \
applying the foundational standard. Extract holdings, assess factual \
similarity to our case.
2. For state authority: identify the most relevant Georgia cases. Extract \
holdings, assess factual similarity.
3. Apply the framework to our client's specific facts — how strong is the \
constitutional argument?
4. Identify both helpful AND harmful precedent.

Return JSON:
{{
  "circuit_authority": [
    {{
      "case_name": "...",
      "citation": "...",
      "court": "United States Court of Appeals for the Eleventh Circuit",
      "date": "...",
      "holding": "...",
      "source": "COURTLISTENER",
      "verification_status": "PENDING"
    }}
  ],
  "state_authority": [
    {{
      "case_name": "...",
      "citation": "...",
      "court": "Supreme Court of Georgia|Court of Appeals of Georgia",
      "date": "...",
      "holding": "...",
      "source": "COURTLISTENER",
      "verification_status": "PENDING"
    }}
  ],
  "application_to_client": "Detailed analysis of how this standard applies...",
  "strength_assessment": "strong|moderate|weak",
  "strength_explanation": "Why the argument is strong or weak on these facts"
}}"""


class ConstitutionalCaseLawAgent(BaseAgent):
    """Finds federal and state constitutional authority for rights violations."""

    agent_id = "constitutional_case_law"
    agent_name = "Constitutional Law Case Law Agent"

    def __init__(self) -> None:
        super().__init__()
        self._cl_client = CourtListenerClient()

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Research constitutional law for all identified rights issues.

        Input keys:
            rights_violation_flags: list of rights violation dicts
            factual_allegations: list of factual allegation dicts
            case_summary: str — brief summary of the case facts

        Output: ConstitutionalCaseLawOutput as dict
        """
        self.log_action("constitutional_research_started")
        self._cl_client.reset_call_count()

        rights_flags = input_data.get("rights_violation_flags", [])
        factual_allegations = input_data.get("factual_allegations", [])
        case_summary = input_data.get("case_summary", "")

        # Step 1: Identify constitutional issues and foundational authority
        issues = await self._identify_issues(
            rights_flags=rights_flags,
            factual_allegations=factual_allegations,
            case_summary=case_summary,
        )

        # Step 2: For each issue, search for circuit and state authority
        constitutional_research = []
        for issue in issues:
            research = await self._research_issue(issue, case_summary)
            constitutional_research.append(research)

        self.log_action(
            "constitutional_research_completed",
            {
                "issues_researched": len(constitutional_research),
                "courtlistener_calls": self._cl_client.call_count,
            },
        )

        # Confidence: higher if we found authority for most issues
        issues_with_authority = sum(
            1
            for r in constitutional_research
            if r.get("foundational_authority")
            or r.get("circuit_authority")
            or r.get("state_authority")
        )
        if not constitutional_research:
            confidence = 0.3
        elif issues_with_authority == len(constitutional_research):
            confidence = 0.75
        else:
            confidence = 0.55

        return self.wrap_output(
            {"constitutional_research": constitutional_research},
            confidence=confidence,
        )

    async def _identify_issues(
        self,
        rights_flags: list[dict[str, Any]],
        factual_allegations: list[dict[str, Any]],
        case_summary: str,
    ) -> list[dict[str, Any]]:
        """Use LLM to identify constitutional issues and foundational cases."""
        try:
            result = await call_llm(
                _ISSUE_IDENTIFICATION_PROMPT.format(
                    rights_flags=json.dumps(rights_flags, default=str),
                    factual_allegations=json.dumps(factual_allegations, default=str),
                    case_summary=case_summary,
                ),
                system=_SYSTEM_PROMPT,
                max_tokens=4096,
            )
            return result.get("constitutional_issues", [])
        except Exception as exc:
            logger.warning("Constitutional issue identification failed: %s", exc)
            return []

    async def _research_issue(
        self,
        issue: dict[str, Any],
        case_summary: str,
    ) -> dict[str, Any]:
        """Research a single constitutional issue across all court levels."""
        amendment = issue.get("amendment", "")
        issue_desc = issue.get("issue", "")
        legal_standard = issue.get("legal_standard", "")
        foundational_cases = issue.get("foundational_cases", [])

        # Search 11th Circuit
        circuit_queries = issue.get("circuit_queries", [])
        circuit_results = await self._search_courts(
            queries=circuit_queries,
            court_ids=["ca11"],
        )

        # Search Georgia courts
        state_queries = issue.get("state_queries", [])
        state_results = await self._search_courts(
            queries=state_queries,
            court_ids=list(GEORGIA_COURTS.keys()),
        )

        # Use LLM to build the doctrinal framework
        try:
            framework = await call_llm(
                _FRAMEWORK_ANALYSIS_PROMPT.format(
                    amendment=amendment,
                    issue=issue_desc,
                    legal_standard=legal_standard,
                    foundational_cases=json.dumps(foundational_cases, default=str),
                    circuit_results=json.dumps(circuit_results, default=str),
                    state_results=json.dumps(state_results, default=str),
                    case_summary=case_summary,
                ),
                system=_SYSTEM_PROMPT,
                max_tokens=4096,
            )
        except Exception as exc:
            logger.warning("Framework analysis failed for %s: %s", issue_desc, exc)
            framework = {}

        # Tag foundational cases as KNOWN_AUTHORITY
        for case in foundational_cases:
            case["source"] = "KNOWN_AUTHORITY"
            case["verification_status"] = "PENDING"

        return {
            "amendment": amendment,
            "issue": issue_desc,
            "legal_standard": legal_standard,
            "foundational_authority": foundational_cases,
            "circuit_authority": framework.get("circuit_authority", []),
            "state_authority": framework.get("state_authority", []),
            "application_to_client": framework.get("application_to_client", ""),
            "strength_assessment": framework.get("strength_assessment", ""),
            "strength_explanation": framework.get("strength_explanation", ""),
        }

    async def _search_courts(
        self,
        queries: list[str],
        court_ids: list[str],
    ) -> list[dict[str, Any]]:
        """Run queries against specified courts on CourtListener."""
        all_results: list[dict[str, Any]] = []
        seen: set[str] = set()

        for query in queries[:3]:  # Cap queries per court level
            results = await self._cl_client.search_opinions(
                query=query,
                court_ids=court_ids,
                max_results=5,
            )
            for r in results:
                key = r.get("citation", r.get("case_name", ""))
                if key and key not in seen:
                    seen.add(key)
                    all_results.append(r)

        return all_results
