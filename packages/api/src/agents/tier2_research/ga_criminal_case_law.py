"""GA Criminal Case Law Agent — Tier 2 Research.

Finds controlling Georgia appellate authority relevant to the specific
charges and defense theories identified by upstream agents. Searches
CourtListener as primary source and Google Scholar as secondary.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.services.courtlistener import CourtListenerClient, GEORGIA_COURTS
from src.services.llm_service import call_llm

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a Georgia criminal case law research specialist working for a public \
defender's office. Your job is to identify the most relevant Georgia appellate \
court decisions for the legal issues in a criminal case.

JURISDICTION: Georgia (Supreme Court of Georgia, Court of Appeals of Georgia)

PRINCIPLES:
1. Surface BOTH favorable AND unfavorable precedent — the attorney must know \
what they are up against, not just what helps.
2. Assess factual similarity honestly — how close are the precedent facts to \
our client's facts.
3. Only cite cases you are confident are real. If you are unsure whether a \
case exists, say "further research needed" rather than fabricate a citation.
4. For each legal issue, think about MULTIPLE angles — the statute at issue, \
the specific legal doctrine, the factual pattern, and procedural posture.

OUTPUT FORMAT: Always respond with valid JSON."""

_QUERY_GENERATION_PROMPT = """\
Generate targeted search queries for Georgia appellate case law research.

CASE DATA:
{case_data}

LEGAL ISSUES TO RESEARCH:
{legal_issues}

For EACH legal issue, generate 3-5 distinct search queries optimized for \
finding relevant Georgia appellate decisions. Think about:
- The specific statute being interpreted
- The legal doctrine at issue (e.g., constructive possession, reasonable suspicion)
- The factual pattern (e.g., parking lot stop, nervous behavior, pat-down)
- Procedural issues (e.g., motion to suppress, sufficiency of evidence)

Return JSON:
{{
  "issue_queries": [
    {{
      "legal_issue": "description of the issue",
      "issue_source": "charge|rights_violation_flag|defense_theory",
      "queries": ["query 1", "query 2", "query 3"]
    }}
  ]
}}"""

_ANALYSIS_PROMPT = """\
Analyze these Georgia case law search results for relevance to our client's case.

CLIENT'S CASE:
{case_summary}

LEGAL ISSUE: {legal_issue}

SEARCH RESULTS:
{search_results}

For each result that is relevant, extract:
1. The case name and citation
2. The court that decided it
3. The date of the decision
4. The relevant holding (specific to our legal issue)
5. How factually similar the case is to our client's situation (high/medium/low)
6. Why it is similar or distinguishable
7. Whether it is favorable or unfavorable to our client
8. How specifically it applies to our client's facts

IMPORTANT:
- Only include cases that are actually relevant to the legal issue
- Be honest about unfavorable cases — the attorney needs to know
- Assess factual similarity carefully — a case about drug possession in a car \
is different from drug possession on a person
- If a search result snippet is too short to determine relevance, note that \
the full opinion should be reviewed

Return JSON:
{{
  "cases": [
    {{
      "case_name": "State v. Example",
      "citation": "300 Ga. App. 123 (2019)",
      "court": "Court of Appeals of Georgia",
      "date": "2019-06-15",
      "holding": "The court held that...",
      "factual_similarity": "high|medium|low",
      "similarity_explanation": "Why similar or distinguishable",
      "favorable": true,
      "relevance_to_client": "How this applies to our facts"
    }}
  ]
}}"""


class GACriminalCaseLawAgent(BaseAgent):
    """Finds controlling Georgia appellate authority for each legal issue."""

    agent_id = "ga_criminal_case_law"
    agent_name = "GA Criminal Case Law Agent"

    def __init__(self) -> None:
        super().__init__()
        self._cl_client = CourtListenerClient()

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Research Georgia case law for all legal issues in the case.

        Input keys:
            charges: list of parsed charge dicts
            factual_allegations: list of factual allegation dicts
            rights_violation_flags: list of rights violation flag dicts
            defense_theories: list of defense theory strings
            case_summary: str — brief summary of the case facts

        Output: GACriminalCaseLawOutput as dict
        """
        self.log_action("ga_case_law_research_started")
        self._cl_client.reset_call_count()

        charges = input_data.get("charges", [])
        rights_flags = input_data.get("rights_violation_flags", [])
        defense_theories = input_data.get("defense_theories", [])
        case_summary = input_data.get("case_summary", "")

        # Step 1: Identify legal issues and generate search queries
        legal_issues = self._build_legal_issues(charges, rights_flags, defense_theories)

        issue_queries = await self._generate_queries(
            case_data=json.dumps(
                {
                    "charges": charges,
                    "rights_flags": rights_flags,
                    "defense_theories": defense_theories,
                },
                default=str,
            ),
            legal_issues=legal_issues,
        )

        # Step 2: Execute searches on CourtListener for each issue
        research_results = []
        for issue_data in issue_queries:
            issue_result = await self._research_issue(
                legal_issue=issue_data["legal_issue"],
                issue_source=issue_data.get("issue_source", "charge"),
                queries=issue_data.get("queries", []),
                case_summary=case_summary,
            )
            research_results.append(issue_result)

        self.log_action(
            "ga_case_law_research_completed",
            {
                "issues_researched": len(research_results),
                "total_cases_found": sum(
                    len(r.get("cases_found", [])) for r in research_results
                ),
                "courtlistener_calls": self._cl_client.call_count,
            },
        )

        # Compute confidence based on how many issues got results
        issues_with_results = sum(
            1 for r in research_results if r.get("cases_found")
        )
        if not research_results:
            confidence = 0.3
        elif issues_with_results == len(research_results):
            confidence = 0.75
        elif issues_with_results > 0:
            confidence = 0.6
        else:
            confidence = 0.4

        return self.wrap_output(
            {"research_results": research_results},
            confidence=confidence,
        )

    def _build_legal_issues(
        self,
        charges: list[dict],
        rights_flags: list[dict],
        defense_theories: list[str],
    ) -> list[dict[str, str]]:
        """Extract legal issues from charges, rights flags, and defense theories."""
        issues = []

        for charge in charges:
            statute = charge.get("statute_section", "")
            title = charge.get("offense_title", "")
            issues.append(
                {
                    "issue": f"Elements and defenses for {title} under {statute}",
                    "source": "charge",
                }
            )

        for flag in rights_flags:
            description = flag.get("description", "")
            if isinstance(flag, dict):
                description = flag.get("description", flag.get("violation", str(flag)))
            issues.append({"issue": str(description), "source": "rights_violation_flag"})

        for theory in defense_theories:
            issues.append({"issue": str(theory), "source": "defense_theory"})

        return issues

    async def _generate_queries(
        self,
        case_data: str,
        legal_issues: list[dict[str, str]],
    ) -> list[dict[str, Any]]:
        """Use LLM to generate targeted search queries for each legal issue."""
        issues_text = "\n".join(
            f"- [{i['source']}] {i['issue']}" for i in legal_issues
        )

        try:
            result = await call_llm(
                _QUERY_GENERATION_PROMPT.format(
                    case_data=case_data,
                    legal_issues=issues_text,
                ),
                system=_SYSTEM_PROMPT,
                max_tokens=2048,
            )
            return result.get("issue_queries", [])
        except Exception as exc:
            logger.warning("Query generation failed, using fallback queries: %s", exc)
            # Fallback: use the issue descriptions directly as queries
            return [
                {
                    "legal_issue": i["issue"],
                    "issue_source": i["source"],
                    "queries": [f"Georgia {i['issue']}"],
                }
                for i in legal_issues
            ]

    async def _research_issue(
        self,
        legal_issue: str,
        issue_source: str,
        queries: list[str],
        case_summary: str,
    ) -> dict[str, Any]:
        """Research a single legal issue by running all its queries."""
        all_results: list[dict[str, Any]] = []
        seen_citations: set[str] = set()

        for query in queries[:5]:  # Cap at 5 queries per issue
            # Add Georgia qualifier if not present
            ga_query = query if "georgia" in query.lower() else f"Georgia {query}"

            results = await self._cl_client.search_opinions(
                query=ga_query,
                court_ids=list(GEORGIA_COURTS.keys()),
                max_results=5,
            )

            for r in results:
                citation = r.get("citation", "")
                if citation and citation not in seen_citations:
                    seen_citations.add(citation)
                    all_results.append(r)

        # Use LLM to analyze relevance of search results
        if all_results:
            analyzed_cases = await self._analyze_results(
                legal_issue=legal_issue,
                search_results=all_results,
                case_summary=case_summary,
            )
        else:
            analyzed_cases = []

        # Tag each case with source
        for case in analyzed_cases:
            case["source"] = "COURTLISTENER"
            case["verification_status"] = "PENDING"

        return {
            "legal_issue": legal_issue,
            "issue_source": issue_source,
            "queries_run": queries,
            "cases_found": analyzed_cases,
        }

    async def _analyze_results(
        self,
        legal_issue: str,
        search_results: list[dict[str, Any]],
        case_summary: str,
    ) -> list[dict[str, Any]]:
        """Use LLM to analyze search results for relevance."""
        # Format results for the LLM
        formatted = []
        for r in search_results:
            formatted.append(
                {
                    "case_name": r.get("case_name", ""),
                    "citation": r.get("citation", ""),
                    "court": r.get("court", ""),
                    "date": r.get("date_filed", ""),
                    "snippet": r.get("snippet", ""),
                }
            )

        try:
            result = await call_llm(
                _ANALYSIS_PROMPT.format(
                    case_summary=case_summary,
                    legal_issue=legal_issue,
                    search_results=json.dumps(formatted, indent=2),
                ),
                system=_SYSTEM_PROMPT,
                max_tokens=4096,
            )
            return result.get("cases", [])
        except Exception as exc:
            logger.warning("Case analysis failed: %s", exc)
            # Return raw results without analysis
            return [
                {
                    "case_name": r.get("case_name", ""),
                    "citation": r.get("citation", ""),
                    "court": r.get("court", ""),
                    "date": r.get("date_filed", ""),
                    "holding": r.get("snippet", ""),
                    "factual_similarity": "unknown",
                    "similarity_explanation": "Analysis unavailable",
                    "favorable": True,
                    "relevance_to_client": "Manual review needed",
                }
                for r in search_results
            ]
