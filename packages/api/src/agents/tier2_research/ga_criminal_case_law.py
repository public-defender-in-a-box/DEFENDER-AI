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
from src.models.responses.research import CaseAnalysis, QueryPlan
from src.prompts import compose_version, load_prompt
from src.services.courtlistener import CourtListenerClient, GEORGIA_COURTS
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "REAL"

logger = logging.getLogger(__name__)

# Prompts: src/prompts/ga_criminal_case_law/
_SYSTEM = load_prompt("ga_criminal_case_law.system", "v1")
_QUERY_GENERATION = load_prompt("ga_criminal_case_law.query_generation", "v1")
_ANALYSIS = load_prompt("ga_criminal_case_law.analysis", "v1")

# Thinking tokens count toward max_tokens on current models (Phase 1 §2).
_QUERY_MAX_TOKENS = 8000
_ANALYSIS_MAX_TOKENS = 12000


class GACriminalCaseLawAgent(BaseAgent):
    """Finds controlling Georgia appellate authority for each legal issue."""

    agent_id = "ga_criminal_case_law"
    agent_name = "GA Criminal Case Law Agent"

    def __init__(self) -> None:
        super().__init__()
        self._cl_client = CourtListenerClient(agent_id=self.agent_id)

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
                "total_cases_found": sum(len(r.get("cases_found", [])) for r in research_results),
                "courtlistener_calls": self._cl_client.call_count,
            },
        )

        # Compute confidence based on how many issues got results
        issues_with_results = sum(1 for r in research_results if r.get("cases_found"))
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
        """Generate targeted search queries for each legal issue. Raises on failure."""
        issues_text = "\n".join(f"- [{i['source']}] {i['issue']}" for i in legal_issues)

        result = await call_model(
            ModelCallRequest(
                prompt=_QUERY_GENERATION.text.format(
                    case_data=case_data,
                    legal_issues=issues_text,
                ),
                system=_SYSTEM.text,
                max_tokens=_QUERY_MAX_TOKENS,
                response_model=QueryPlan,
                prompt_id="ga_criminal_case_law.query_generation",
                prompt_version=compose_version(_SYSTEM, _QUERY_GENERATION),
                agent_id=self.agent_id,
            )
        )
        return [plan.model_dump() for plan in result.data.issue_queries]

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
        """Analyze search results for relevance. Raises on failure: there is no
        unanalyzed fallback (it used to mark every raw result favorable)."""
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

        result = await call_model(
            ModelCallRequest(
                prompt=_ANALYSIS.text.format(
                    case_summary=case_summary,
                    legal_issue=legal_issue,
                    search_results=json.dumps(formatted, indent=2),
                ),
                system=_SYSTEM.text,
                max_tokens=_ANALYSIS_MAX_TOKENS,
                response_model=CaseAnalysis,
                prompt_id="ga_criminal_case_law.analysis",
                prompt_version=compose_version(_SYSTEM, _ANALYSIS),
                agent_id=self.agent_id,
            )
        )
        return [case.model_dump() for case in result.data.cases]
