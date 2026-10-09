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
from src.models.responses.research import ConstitutionalIssues, DoctrinalFramework
from src.prompts import compose_version, load_prompt
from src.services.courtlistener import CourtListenerClient, GEORGIA_COURTS
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "REAL"

logger = logging.getLogger(__name__)

# Prompts: src/prompts/constitutional_case_law/
_SYSTEM = load_prompt("constitutional_case_law.system", "v1")
_ISSUE_IDENTIFICATION = load_prompt("constitutional_case_law.issue_identification", "v1")
_FRAMEWORK_ANALYSIS = load_prompt("constitutional_case_law.framework_analysis", "v1")

# Thinking tokens count toward max_tokens on current models (Phase 1 §2).
_ISSUES_MAX_TOKENS = 12000
_FRAMEWORK_MAX_TOKENS = 12000


class ConstitutionalCaseLawAgent(BaseAgent):
    """Finds federal and state constitutional authority for rights violations."""

    agent_id = "constitutional_case_law"
    agent_name = "Constitutional Law Case Law Agent"

    def __init__(self) -> None:
        super().__init__()
        self._cl_client = CourtListenerClient(agent_id=self.agent_id)

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
        """Identify constitutional issues and foundational cases. Raises on failure."""
        result = await call_model(
            ModelCallRequest(
                prompt=_ISSUE_IDENTIFICATION.text.format(
                    rights_flags=json.dumps(rights_flags, default=str),
                    factual_allegations=json.dumps(factual_allegations, default=str),
                    case_summary=case_summary,
                ),
                system=_SYSTEM.text,
                max_tokens=_ISSUES_MAX_TOKENS,
                response_model=ConstitutionalIssues,
                prompt_id="constitutional_case_law.issue_identification",
                prompt_version=compose_version(_SYSTEM, _ISSUE_IDENTIFICATION),
                agent_id=self.agent_id,
            )
        )
        return [issue.model_dump() for issue in result.data.constitutional_issues]

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

        # Build the doctrinal framework. A failure raises; there is no empty framework.
        result = await call_model(
            ModelCallRequest(
                prompt=_FRAMEWORK_ANALYSIS.text.format(
                    amendment=amendment,
                    issue=issue_desc,
                    legal_standard=legal_standard,
                    foundational_cases=json.dumps(foundational_cases, default=str),
                    circuit_results=json.dumps(circuit_results, default=str),
                    state_results=json.dumps(state_results, default=str),
                    case_summary=case_summary,
                ),
                system=_SYSTEM.text,
                max_tokens=_FRAMEWORK_MAX_TOKENS,
                response_model=DoctrinalFramework,
                prompt_id="constitutional_case_law.framework_analysis",
                prompt_version=compose_version(_SYSTEM, _FRAMEWORK_ANALYSIS),
                agent_id=self.agent_id,
            )
        )
        framework = result.data.model_dump()

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
