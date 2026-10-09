"""Rights Violation Scanner — Tier 2 Intake Specialist.

Identifies potential constitutional rights violations from arrest reports,
client narratives, and officer conduct records. Two-pass system:
  Pass 1 — Document-level extraction (arrest report + officer conduct)
  Pass 2 — Cross-reference with client narrative, discrepancy analysis,
            and suppression viability assessment

Covers:
  - 4th Amendment: Unreasonable search and seizure
  - 5th Amendment: Self-incrimination, Miranda rights
  - 6th Amendment: Right to counsel, speedy trial, confrontation, jury
  - 8th Amendment: Excessive bail, cruel and unusual punishment

Georgia-specific: O.C.G.A. Title 17 (Criminal Procedure), Georgia
Constitution Art. I, § I.
"""

import json
import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.responses.rights import DocumentScan, NarrativeCrossReference
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "REAL"

logger = logging.getLogger(__name__)

# Violations at or above this severity are flagged for immediate attorney attention
_CRITICAL_SEVERITIES = {"CRITICAL", "SIGNIFICANT"}

# Confidence floor — below this, individual violation flags get LOW confidence
_VIOLATION_CONFIDENCE_FLOOR = 0.4

# Prompts: src/prompts/rights_scanner/
_SYSTEM = load_prompt("rights_scanner.system", "v1")
_PASS1 = load_prompt("rights_scanner.pass1", "v1")
_PASS2 = load_prompt("rights_scanner.pass2", "v1")
# Thinking tokens count toward max_tokens on current models (Phase 1 §2).
_MAX_TOKENS = 16000


class RightsScannerAgent(BaseAgent):
    """Scans for 4th, 5th, 6th, and 8th Amendment violations.

    Two-pass system:
      Pass 1: Analyze arrest report and officer conduct for violations.
      Pass 2: Cross-reference with client narrative, find discrepancies,
              assess suppression viability.

    Depends on: Pre-Interview Research, Intake Conductor.
    Writes to: CaseState.rights_violation_analysis
    """

    agent_id = "rights_scanner"
    agent_name = "Rights Violation Scanner"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Scan for constitutional violations across all available sources.

        Args:
            input_data: Dict with keys:
                - arrest_report (str): Text of the arrest report
                - client_narrative (str): Client's account from intake
                - officer_conduct (str): Officer conduct details
                - charges (list[dict]): Parsed charges from charge processing
                - pre_interview_flags (list[str]): Flags from pre-interview research

        Returns:
            Wrapped output with violations, discrepancies, suppression viability,
            and detailed amendment-specific analyses.
        """
        arrest_report = input_data.get("arrest_report", "")
        client_narrative = input_data.get("client_narrative", "")
        officer_conduct = input_data.get("officer_conduct", "")
        charges = input_data.get("charges", [])
        pre_interview_flags = input_data.get("pre_interview_flags", [])

        has_official_docs = bool(arrest_report or officer_conduct)
        has_client_narrative = bool(client_narrative)

        if not has_official_docs and not has_client_narrative:
            self.log_action("rights_scan_skipped", {"reason": "no_input_data"})
            return self.wrap_output(
                {
                    "violations": [],
                    "discrepancy_report": [],
                    "suppression_viability": {
                        "score": 0,
                        "confidence": 0.0,
                        "basis": [],
                        "risks": [],
                        "recommended_motions": [],
                    },
                    "miranda_analysis": {},
                    "search_analysis": {},
                    "sixth_amendment_analysis": {},
                    "eighth_amendment_analysis": {},
                    "total_violations_found": 0,
                    "critical_violations": 0,
                    "attorney_flags": ["No source documents provided for analysis."],
                },
                confidence=0.0,
            )

        # ---- Pass 1: Document-level extraction ----
        self.log_action(
            "rights_scan_pass1_started",
            {
                "has_arrest_report": bool(arrest_report),
                "has_officer_conduct": bool(officer_conduct),
                "charge_count": len(charges),
            },
        )

        pass1_result = await self._run_pass1(
            arrest_report, officer_conduct, charges, pre_interview_flags
        )
        self.log_action(
            "rights_scan_pass1_completed",
            {
                "violations_found": len(pass1_result.get("violations", [])),
            },
        )

        # ---- Pass 2: Client narrative cross-reference ----
        if has_client_narrative:
            self.log_action("rights_scan_pass2_started")
            pass2_result = await self._run_pass2(pass1_result, client_narrative, arrest_report)
            self.log_action(
                "rights_scan_pass2_completed",
                {
                    "additional_violations": len(pass2_result.get("additional_violations", [])),
                    "discrepancies": len(pass2_result.get("discrepancy_report", [])),
                },
            )
        else:
            pass2_result = {}

        # ---- Merge results ----
        merged = self._merge_passes(pass1_result, pass2_result)

        # Compute overall confidence
        overall_confidence = self._compute_confidence(merged)

        self.log_action(
            "rights_scan_completed",
            {
                "total_violations": merged["total_violations_found"],
                "critical_violations": merged["critical_violations"],
                "suppression_score": merged["suppression_viability"].get("score", 0),
                "overall_confidence": overall_confidence,
            },
        )

        return self.wrap_output(merged, confidence=overall_confidence)

    async def _run_pass1(
        self,
        arrest_report: str,
        officer_conduct: str,
        charges: list[dict[str, Any]],
        pre_interview_flags: list[str],
    ) -> dict[str, Any]:
        """Pass 1: Analyze official documents for rights violations."""
        charges_text = json.dumps(charges, indent=2) if charges else "No charges provided"
        flags_text = (
            "\n".join(f"- {f}" for f in pre_interview_flags) if pre_interview_flags else "None"
        )

        prompt = _PASS1.text.format(
            arrest_report=arrest_report or "Not provided",
            officer_conduct=officer_conduct or "Not provided",
            charges=charges_text,
            pre_interview_flags=flags_text,
        )

        result = await call_model(
            ModelCallRequest(
                prompt=prompt,
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=DocumentScan,
                prompt_id="rights_scanner.pass1",
                prompt_version=compose_version(_SYSTEM, _PASS1),
                agent_id=self.agent_id,
            )
        )
        return result.data.model_dump()

    async def _run_pass2(
        self,
        pass1_result: dict[str, Any],
        client_narrative: str,
        arrest_report: str,
    ) -> dict[str, Any]:
        """Pass 2: Cross-reference client narrative with official record."""
        prompt = _PASS2.text.format(
            pass1_violations=json.dumps(pass1_result.get("violations", []), indent=2),
            pass1_miranda=json.dumps(pass1_result.get("miranda_analysis", {}), indent=2),
            pass1_search=json.dumps(pass1_result.get("search_analysis", {}), indent=2),
            client_narrative=client_narrative,
            arrest_report=arrest_report or "Not provided",
        )

        result = await call_model(
            ModelCallRequest(
                prompt=prompt,
                system=_SYSTEM.text,
                max_tokens=_MAX_TOKENS,
                response_model=NarrativeCrossReference,
                prompt_id="rights_scanner.pass2",
                prompt_version=compose_version(_SYSTEM, _PASS2),
                agent_id=self.agent_id,
            )
        )
        return result.data.model_dump()

    def _merge_passes(
        self,
        pass1: dict[str, Any],
        pass2: dict[str, Any],
    ) -> dict[str, Any]:
        """Merge Pass 1 and Pass 2 results into a single output."""
        # Combine violations
        all_violations = list(pass1.get("violations", []))
        all_violations.extend(pass2.get("additional_violations", []))

        # Count by severity
        total = len(all_violations)
        critical = sum(1 for v in all_violations if v.get("severity") in _CRITICAL_SEVERITIES)

        # Miranda: merge pass2 updates into pass1 analysis
        miranda = dict(pass1.get("miranda_analysis", {}))
        miranda_updates = pass2.get("miranda_updates", {})
        if miranda_updates:
            extra_statements = miranda_updates.get("statements_before_miranda", [])
            if extra_statements:
                existing = miranda.get("statements_before_miranda", [])
                miranda["statements_before_miranda"] = existing + extra_statements
            if miranda_updates.get("waiver_validity"):
                miranda["waiver_validity"] = miranda_updates["waiver_validity"]
            if miranda_updates.get("suppression_basis"):
                miranda["suppression_basis"] = miranda_updates["suppression_basis"]

        # Search: merge pass2 updates
        search = dict(pass1.get("search_analysis", {}))
        search_updates = pass2.get("search_updates", {})
        if search_updates:
            for key in ("consent_given", "consent_voluntariness", "scope_exceeded"):
                if key in search_updates and search_updates[key] is not None:
                    search[key] = search_updates[key]
            if search_updates.get("suppression_basis"):
                search["suppression_basis"] = search_updates["suppression_basis"]

        # Suppression viability (prefer pass2 which has full picture)
        suppression = pass2.get(
            "suppression_viability",
            {
                "score": 0,
                "confidence": 0.0,
                "basis": [],
                "risks": [],
                "recommended_motions": [],
            },
        )

        # Attorney flags
        attorney_flags = list(pass2.get("attorney_flags", []))
        if critical > 0:
            attorney_flags.insert(
                0,
                f"ATTORNEY REVIEW REQUIRED — {critical} critical/significant "
                f"violation(s) identified. This analysis is decision support only.",
            )

        return {
            "violations": all_violations,
            "discrepancy_report": pass2.get("discrepancy_report", []),
            "suppression_viability": suppression,
            "miranda_analysis": miranda,
            "search_analysis": search,
            "sixth_amendment_analysis": pass1.get("sixth_amendment_analysis", {}),
            "eighth_amendment_analysis": pass1.get("eighth_amendment_analysis", {}),
            "total_violations_found": total,
            "critical_violations": critical,
            "attorney_flags": attorney_flags,
        }

    def _compute_confidence(self, merged: dict[str, Any]) -> float:
        """Compute overall confidence from individual violation confidences.

        Weighted average: critical/significant violations weigh 2x.
        Floor of 0.5 if we have data but no violations (absence of evidence
        is not certainty).
        """
        violations = merged.get("violations", [])
        if not violations:
            # No violations found — moderate confidence in the absence
            return 0.5

        weighted_sum = 0.0
        weight_total = 0.0
        for v in violations:
            conf = v.get("confidence", 0.5)
            weight = 2.0 if v.get("severity") in _CRITICAL_SEVERITIES else 1.0
            weighted_sum += conf * weight
            weight_total += weight

        avg = weighted_sum / weight_total if weight_total > 0 else 0.5

        # Boost confidence if we have discrepancy corroboration
        discrepancies = merged.get("discrepancy_report", [])
        critical_discrepancies = sum(
            1 for d in discrepancies if d.get("significance") == "CRITICAL"
        )
        if critical_discrepancies > 0:
            avg = min(avg + 0.05 * critical_discrepancies, 0.95)

        return round(avg, 2)
