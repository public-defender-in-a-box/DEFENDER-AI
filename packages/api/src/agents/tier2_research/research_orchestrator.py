"""Research Orchestrator — runs all research agents and verification.

Coordinates the parallel execution of the three research agents
(GA Criminal Case Law, Constitutional Case Law, GA Statutes), collects
their outputs, passes all citations to the Citation Verification Agent,
and returns a combined, verified research output.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.agents.tier2_research.ga_criminal_case_law import GACriminalCaseLawAgent
from src.agents.tier2_research.constitutional_case_law import ConstitutionalCaseLawAgent
from src.agents.tier2_research.ga_statutes_agent import GAStatutesAgent
from src.agents.tier2_research.citation_verification import CitationVerificationAgent
from src.services.cost_tracker import CostTracker

STATUS = "REAL"

logger = logging.getLogger(__name__)


class ResearchOrchestrator(BaseAgent):
    """Orchestrates all research agents and citation verification.

    Data flow:
    1. Receives structured case data from the upstream pipeline
    2. Runs GA Case Law, Constitutional Case Law, and GA Statutes IN PARALLEL
    3. Collects all citations from the three agents
    4. Passes citations to Citation Verification Agent
    5. Tags all research output with verification status
    6. Returns combined, verified output with cost report
    """

    agent_id = "research_orchestrator"
    agent_name = "Research Orchestrator"

    def __init__(self) -> None:
        super().__init__()
        self._ga_case_law = GACriminalCaseLawAgent()
        self._constitutional = ConstitutionalCaseLawAgent()
        self._statutes = GAStatutesAgent()
        self._verifier = CitationVerificationAgent()

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run the full research pipeline.

        Input keys:
            case_id: str — case identifier for cost tracking
            charges: list[dict] — parsed charges from Charge Processing
            factual_allegations: list[dict] — from Charge Processing
            rights_violation_flags: list[dict] — from Rights Scanner
            defense_theories: list[str] — from Pre-Interview Research
            case_summary: str — brief factual summary
            enhancements: list[dict] — enhancement flags
            defendant_info: dict — any known defendant background

        Output: CombinedResearchOutput as dict
        """
        case_id = input_data.get("case_id", "unknown")
        cost_tracker = CostTracker(case_id=case_id)

        self.log_action("research_pipeline_started", {"case_id": case_id})

        # ---- Phase 1: Run 3 research agents in parallel ----
        ga_case_law_input = {
            "charges": input_data.get("charges", []),
            "factual_allegations": input_data.get("factual_allegations", []),
            "rights_violation_flags": input_data.get("rights_violation_flags", []),
            "defense_theories": input_data.get("defense_theories", []),
            "case_summary": input_data.get("case_summary", ""),
        }

        constitutional_input = {
            "rights_violation_flags": input_data.get("rights_violation_flags", []),
            "factual_allegations": input_data.get("factual_allegations", []),
            "case_summary": input_data.get("case_summary", ""),
        }

        statutes_input = {
            "charges": input_data.get("charges", []),
            "enhancements": input_data.get("enhancements", []),
            "defendant_info": input_data.get("defendant_info", {}),
        }

        # Track costs for each agent
        cost_tracker.start_agent("ga_criminal_case_law")
        cost_tracker.start_agent("constitutional_case_law")
        cost_tracker.start_agent("ga_statutes_agent")

        # Run all three in parallel
        ga_result, const_result, statutes_result = await asyncio.gather(
            self._run_agent_safe(self._ga_case_law, ga_case_law_input),
            self._run_agent_safe(self._constitutional, constitutional_input),
            self._run_agent_safe(self._statutes, statutes_input),
        )

        cost_tracker.finish_agent("ga_criminal_case_law")
        cost_tracker.finish_agent("constitutional_case_law")
        cost_tracker.finish_agent("ga_statutes_agent")

        self.log_action(
            "research_phase_completed",
            {
                "ga_case_law_confidence": ga_result.get("confidence", "UNKNOWN"),
                "constitutional_confidence": const_result.get("confidence", "UNKNOWN"),
                "statutes_confidence": statutes_result.get("confidence", "UNKNOWN"),
            },
        )

        # ---- Phase 2: Citation Verification ----
        cost_tracker.start_agent("citation_verification")

        verification_input = {
            "ga_case_law_output": ga_result.get("data", {}),
            "constitutional_output": const_result.get("data", {}),
            "statutes_output": statutes_result.get("data", {}),
        }

        verification_result = await self._run_agent_safe(self._verifier, verification_input)

        cost_tracker.finish_agent("citation_verification")

        # ---- Phase 3: Tag research results with verification status ----
        verification_data = verification_result.get("data", {})
        verified_ga = self._apply_verification_tags(
            ga_result.get("data", {}),
            verification_data,
        )
        verified_const = self._apply_verification_tags(
            const_result.get("data", {}),
            verification_data,
        )

        # ---- Phase 4: Assemble combined output ----
        cost_report = cost_tracker.get_report()

        combined_output = {
            "ga_criminal_case_law": verified_ga,
            "constitutional_case_law": verified_const,
            "ga_statutes": statutes_result.get("data", {}),
            "citation_verification": verification_data,
            "cost_report": {
                "ga_case_law_cost": cost_report["agents"]
                .get("ga_criminal_case_law", {})
                .get("total_cost_usd", 0),
                "constitutional_cost": cost_report["agents"]
                .get("constitutional_case_law", {})
                .get("total_cost_usd", 0),
                "statutes_cost": cost_report["agents"]
                .get("ga_statutes_agent", {})
                .get("total_cost_usd", 0),
                "verification_cost": cost_report["agents"]
                .get("citation_verification", {})
                .get("total_cost_usd", 0),
                "courtlistener_calls": cost_report.get("total_courtlistener_calls", 0),
                "total_cost": cost_report.get("total_cost_usd", 0),
            },
        }

        self.log_action(
            "research_pipeline_completed",
            {
                "case_id": case_id,
                "total_cost": cost_report.get("total_cost_usd", 0),
                "courtlistener_calls": cost_report.get("total_courtlistener_calls", 0),
            },
        )

        # Overall confidence: average of the four agents
        confidences = []
        for r in (ga_result, const_result, statutes_result, verification_result):
            c = r.get("confidence", "MEDIUM")
            if c == "HIGH":
                confidences.append(0.9)
            elif c == "MEDIUM":
                confidences.append(0.7)
            elif c == "LOW":
                confidences.append(0.4)
            else:
                confidences.append(0.5)

        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.5

        return self.wrap_output(combined_output, confidence=avg_confidence)

    async def _run_agent_safe(
        self,
        agent: BaseAgent,
        input_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Run an agent with error handling — partial failures don't crash the pipeline."""
        try:
            return await agent.run(input_data)
        except Exception as exc:
            logger.error(
                "Research agent %s failed: %s",
                agent.agent_id,
                exc,
                exc_info=True,
            )
            self.log_action(
                "agent_failed",
                {"agent_id": agent.agent_id, "error": str(exc)},
            )
            return {
                "data": {},
                "confidence": "LOW",
                "source": agent.agent_id,
                "error": str(exc),
            }

    def _apply_verification_tags(
        self,
        research_output: dict[str, Any],
        verification_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update verification_status on research results based on verification output."""
        # Build a lookup of citation → verification status
        verification_lookup: dict[str, str] = {}
        for result in verification_data.get("verification_results", []):
            citation = result.get("original_citation", "")
            status = result.get("verification_status", "UNVERIFIED")
            if citation:
                verification_lookup[citation] = status

        # Apply to GA case law results
        for issue in research_output.get("research_results", []):
            for case in issue.get("cases_found", []):
                citation = case.get("citation", "")
                case_name = case.get("case_name", "")
                full = f"{case_name}, {citation}" if case_name else citation

                if full in verification_lookup:
                    case["verification_status"] = verification_lookup[full]
                elif citation in verification_lookup:
                    case["verification_status"] = verification_lookup[citation]

        # Apply to constitutional research results
        for issue in research_output.get("constitutional_research", []):
            for level in ("foundational_authority", "circuit_authority", "state_authority"):
                for case in issue.get(level, []):
                    citation = case.get("citation", "")
                    case_name = case.get("case_name", "")
                    full = f"{case_name}, {citation}" if case_name else citation

                    if full in verification_lookup:
                        case["verification_status"] = verification_lookup[full]
                    elif citation in verification_lookup:
                        case["verification_status"] = verification_lookup[citation]

        return research_output
