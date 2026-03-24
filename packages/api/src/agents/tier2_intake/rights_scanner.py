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
from src.services.llm_service import call_llm

logger = logging.getLogger(__name__)

# Violations at or above this severity are flagged for immediate attorney attention
_CRITICAL_SEVERITIES = {"CRITICAL", "SIGNIFICANT"}

# Confidence floor — below this, individual violation flags get LOW confidence
_VIOLATION_CONFIDENCE_FLOOR = 0.4

_SYSTEM_PROMPT = (
    "You are a constitutional rights violation scanner for a public defender's "
    "office in Georgia. You analyze arrest reports, officer conduct records, and "
    "client narratives to identify potential violations of constitutional rights.\n\n"
    "JURISDICTION KNOWLEDGE:\n"
    "- Georgia Constitution Art. I, § I (Bill of Rights)\n"
    "- O.C.G.A. Title 17 — Criminal Procedure\n"
    "- O.C.G.A. § 17-5-1 et seq. — Search and Seizure\n"
    "- O.C.G.A. § 17-5-30 — Motion to Suppress\n"
    "- O.C.G.A. § 24-5-506 — Privileged communications\n"
    "- O.C.G.A. § 17-4-20 — Arrest by law enforcement officers\n"
    "- O.C.G.A. § 17-4-21 — Arrest by private person\n"
    "- O.C.G.A. § 17-7-50 — Right to counsel\n"
    "- O.C.G.A. § 17-7-170 — Speedy trial demand\n"
    "- O.C.G.A. § 17-6-1 — Bail in non-capital cases\n"
    "- Federal: 4th, 5th, 6th, 8th, 14th Amendments\n"
    "- Key cases: Mapp v. Ohio, Miranda v. Arizona, Gideon v. Wainwright, "
    "Terry v. Ohio, Katz v. United States, Strickland v. Washington, "
    "Berghuis v. Thompkins, Salinas v. Texas, Riley v. California, "
    "Carpenter v. United States\n\n"
    "ANALYSIS PRINCIPLES:\n"
    "1. Be thorough — a missed violation is worse than a false positive.\n"
    "2. Assign confidence scores (0.0-1.0) to every finding.\n"
    "3. Apply equal analytical rigor to officer and defendant accounts.\n"
    "4. Actively look for violations — do not just passively note obvious ones.\n"
    "5. Flag uncertainty rather than ignoring it.\n"
    "6. Never make legal conclusions — identify issues for attorney review.\n"
    "7. Every output that reaches the attorney must include: "
    "'ATTORNEY REVIEW REQUIRED — This analysis is decision support only.'\n\n"
    "OUTPUT FORMAT: Always respond with valid JSON matching the requested schema. "
    "Do not include any text outside the JSON object."
)

# ---------------------------------------------------------------------------
# Pass 1 — Document-level extraction
# ---------------------------------------------------------------------------
_PASS1_PROMPT = """Analyze the following documents for potential constitutional rights violations.

ARREST REPORT:
{arrest_report}

OFFICER CONDUCT DETAILS:
{officer_conduct}

CHARGES:
{charges}

PRE-INTERVIEW FLAGS:
{pre_interview_flags}

Perform a thorough constitutional rights analysis. Return a JSON object with:

{{
  "violations": [
    {{
      "id": "V001",
      "amendment": "4TH|5TH|6TH|8TH",
      "category": "string — e.g. WARRANTLESS_SEARCH, MIRANDA_VIOLATION, etc.",
      "description": "detailed description of the potential violation",
      "severity": "CRITICAL|SIGNIFICANT|MODERATE|MINOR",
      "confidence": 0.0-1.0,
      "supporting_facts": ["fact1", "fact2"],
      "source": "ARREST_REPORT|OFFICER_CONDUCT",
      "legal_standard": "applicable legal standard or test",
      "relevant_case_law": ["case1", "case2"],
      "suppression_potential": "HIGH|MEDIUM|LOW"
    }}
  ],
  "miranda_analysis": {{
    "miranda_given": true|false|null,
    "timing": "BEFORE_QUESTIONING|DURING_QUESTIONING|AFTER_QUESTIONING|NOT_GIVEN|UNKNOWN",
    "custodial": true|false|null,
    "statements_before_miranda": ["statement1"],
    "statements_after_miranda": ["statement1"],
    "waiver_validity": "VALID|QUESTIONABLE|INVALID|UNKNOWN",
    "suppression_basis": "string"
  }},
  "search_analysis": {{
    "search_occurred": true|false,
    "warrant_present": true|false|null,
    "probable_cause_articulated": "string describing stated probable cause",
    "consent_given": true|false|null,
    "consent_voluntariness": "VOLUNTARY|COERCED|QUESTIONABLE|NOT_APPLICABLE",
    "scope_exceeded": true|false|null,
    "exigent_circumstances_claimed": true|false,
    "plain_view_claimed": true|false,
    "search_incident_to_arrest": true|false,
    "vehicle_exception": true|false,
    "evidence_found": ["item1", "item2"],
    "suppression_basis": "string"
  }},
  "sixth_amendment_analysis": {{
    "counsel_requested": true|false|null,
    "counsel_provided": true|false|null,
    "counsel_denied_or_delayed": true|false,
    "lineup_conducted": true|false,
    "lineup_procedural_issues": ["issue1"],
    "speedy_trial_concerns": "string",
    "confrontation_issues": ["issue1"]
  }},
  "eighth_amendment_analysis": {{
    "excessive_bail": true|false|null,
    "bail_amount": "string",
    "bail_proportionality": "string",
    "excessive_force": true|false|null,
    "force_description": "string",
    "cruel_conditions": ["condition1"]
  }}
}}

KEY AREAS TO CHECK:

4TH AMENDMENT — Search and Seizure:
- Was a warrant obtained? If so, was it properly scoped?
- Was there probable cause? What facts support it?
- If consent was given, was it truly voluntary (not coerced)?
- Did the search exceed the scope of consent or warrant?
- Were there exigent circumstances justifying a warrantless search?
- Was plain view doctrine properly applied?
- For vehicle searches: was there probable cause or valid exception?
- For digital devices: was a separate warrant obtained (Riley v. California)?
- For cell location data: warrant required (Carpenter v. United States)?

5TH AMENDMENT — Self-Incrimination and Miranda:
- Were Miranda rights read before custodial interrogation?
- Was the person in custody (not free to leave) when questioned?
- Were statements made before Miranda warnings administered?
- Was the Miranda waiver knowing and voluntary?
- Did the person invoke their right to silence? Was it honored?
- Were there any coercive interrogation tactics?

6TH AMENDMENT — Right to Counsel and Fair Trial:
- Was counsel requested? Was request honored?
- Was there any questioning after counsel was requested?
- Were lineup procedures properly conducted?
- Any speedy trial concerns?
- Right to confront accusers preserved?

8TH AMENDMENT — Bail and Punishment:
- Was bail set at an excessive amount given the charges?
- Was excessive force used during arrest or detention?
- Were detention conditions cruel or unusual?

Return valid JSON only."""

# ---------------------------------------------------------------------------
# Pass 2 — Client narrative cross-reference and discrepancy analysis
# ---------------------------------------------------------------------------
_PASS2_PROMPT = """You are cross-referencing the client's narrative against the official
record to identify discrepancies and additional rights violations.

PASS 1 VIOLATIONS FOUND:
{pass1_violations}

PASS 1 MIRANDA ANALYSIS:
{pass1_miranda}

PASS 1 SEARCH ANALYSIS:
{pass1_search}

CLIENT NARRATIVE:
{client_narrative}

ARREST REPORT:
{arrest_report}

Analyze the client's account against the official record. Return JSON with:

{{
  "additional_violations": [
    {{
      "id": "CV001",
      "amendment": "4TH|5TH|6TH|8TH",
      "category": "string",
      "description": "string",
      "severity": "CRITICAL|SIGNIFICANT|MODERATE|MINOR",
      "confidence": 0.0-1.0,
      "supporting_facts": ["fact1"],
      "source": "CLIENT_NARRATIVE|CROSS_REFERENCE",
      "legal_standard": "string",
      "relevant_case_law": ["case1"],
      "suppression_potential": "HIGH|MEDIUM|LOW"
    }}
  ],
  "discrepancy_report": [
    {{
      "id": "D001",
      "topic": "string — e.g. consent to search, Miranda timing, force used",
      "officer_account": "what the officer/report says",
      "client_account": "what the client says",
      "significance": "CRITICAL|NOTABLE|MINOR",
      "possible_explanations": ["explanation1"],
      "defense_relevance": "how this discrepancy may help the defense"
    }}
  ],
  "miranda_updates": {{
    "statements_before_miranda": ["any additional statements client reports"],
    "waiver_validity": "VALID|QUESTIONABLE|INVALID|UNKNOWN",
    "suppression_basis": "updated basis if client narrative changes analysis"
  }},
  "search_updates": {{
    "consent_given": true|false|null,
    "consent_voluntariness": "VOLUNTARY|COERCED|QUESTIONABLE|NOT_APPLICABLE",
    "scope_exceeded": true|false|null,
    "suppression_basis": "updated basis"
  }},
  "suppression_viability": {{
    "score": 0-100,
    "confidence": 0.0-1.0,
    "basis": ["legal basis for suppression motion"],
    "risks": ["risks or weaknesses in suppression argument"],
    "recommended_motions": ["MOTION_TO_SUPPRESS", "MOTION_TO_DISMISS", etc.]
  }},
  "attorney_flags": [
    "CRITICAL: description of urgent issue for attorney"
  ]
}}

IMPORTANT ANALYSIS NOTES:
- Discrepancies between the officer account and client account are VERY significant.
  Officers may omit details; clients may reveal rights violations not in the report.
- If the client says they did NOT consent to a search but the report says they did,
  this is a CRITICAL discrepancy.
- If the client says they asked for a lawyer but the report doesn't mention it,
  this is a CRITICAL discrepancy.
- If the client says Miranda was not read but the report says it was, flag this.
- Look for indications of coercion, intimidation, or pressure.
- The suppression_viability score should reflect the overall strength of potential
  suppression motions considering ALL violations and discrepancies.

Return valid JSON only."""


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
        self.log_action("rights_scan_pass1_started", {
            "has_arrest_report": bool(arrest_report),
            "has_officer_conduct": bool(officer_conduct),
            "charge_count": len(charges),
        })

        pass1_result = await self._run_pass1(
            arrest_report, officer_conduct, charges, pre_interview_flags
        )
        self.log_action("rights_scan_pass1_completed", {
            "violations_found": len(pass1_result.get("violations", [])),
        })

        # ---- Pass 2: Client narrative cross-reference ----
        if has_client_narrative:
            self.log_action("rights_scan_pass2_started")
            pass2_result = await self._run_pass2(
                pass1_result, client_narrative, arrest_report
            )
            self.log_action("rights_scan_pass2_completed", {
                "additional_violations": len(
                    pass2_result.get("additional_violations", [])
                ),
                "discrepancies": len(pass2_result.get("discrepancy_report", [])),
            })
        else:
            pass2_result = {}

        # ---- Merge results ----
        merged = self._merge_passes(pass1_result, pass2_result)

        # Compute overall confidence
        overall_confidence = self._compute_confidence(merged)

        self.log_action("rights_scan_completed", {
            "total_violations": merged["total_violations_found"],
            "critical_violations": merged["critical_violations"],
            "suppression_score": merged["suppression_viability"].get("score", 0),
            "overall_confidence": overall_confidence,
        })

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
        flags_text = "\n".join(f"- {f}" for f in pre_interview_flags) if pre_interview_flags else "None"

        prompt = _PASS1_PROMPT.format(
            arrest_report=arrest_report or "Not provided",
            officer_conduct=officer_conduct or "Not provided",
            charges=charges_text,
            pre_interview_flags=flags_text,
        )

        result = await call_llm(prompt, system=_SYSTEM_PROMPT, max_tokens=4096)
        return result

    async def _run_pass2(
        self,
        pass1_result: dict[str, Any],
        client_narrative: str,
        arrest_report: str,
    ) -> dict[str, Any]:
        """Pass 2: Cross-reference client narrative with official record."""
        prompt = _PASS2_PROMPT.format(
            pass1_violations=json.dumps(
                pass1_result.get("violations", []), indent=2
            ),
            pass1_miranda=json.dumps(
                pass1_result.get("miranda_analysis", {}), indent=2
            ),
            pass1_search=json.dumps(
                pass1_result.get("search_analysis", {}), indent=2
            ),
            client_narrative=client_narrative,
            arrest_report=arrest_report or "Not provided",
        )

        result = await call_llm(prompt, system=_SYSTEM_PROMPT, max_tokens=4096)
        return result

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
        critical = sum(
            1
            for v in all_violations
            if v.get("severity") in _CRITICAL_SEVERITIES
        )

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
