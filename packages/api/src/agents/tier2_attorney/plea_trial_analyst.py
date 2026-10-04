"""Plea / Trial Assessment Agent — Tier 2 Attorney Prep.

Structured decision-support tool for the plea vs. trial calculus.
ALL outputs marked: DECISION SUPPORT ONLY — ATTORNEY AND CLIENT DECIDE.
"""

from __future__ import annotations

import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.agents.tier2_attorney.plea_trial_prompts import (
    PLEA_TRIAL_SYSTEM_PROMPT,
    build_plea_trial_user_prompt,
)
from src.services.llm_service import call_llm

logger = logging.getLogger(__name__)

# Default attorney assessment values when not provided
_DEFAULT_ATTORNEY_ASSESSMENTS: dict[str, Any] = {
    "estimated_acquittal_probability": 0.25,
    "judge_sentencing_tendency": "MODERATE",
    "witness_credibility_assessment": "UNKNOWN",
    "client_testimony_viability": "UNKNOWN",
    "jury_pool_assessment": "",
    "plea_negotiation_room": "UNKNOWN",
}

# Upstream data sources tracked for confidence scoring
_UPSTREAM_SOURCES = [
    "charges",
    "rights_violations",
    "intake_summary",
    "legal_research",
    "collateral_consequences",
    "draft_motions",
    "brady_analysis",
]


class PleaTrialAnalyst(BaseAgent):
    """Plea/Trial Assessment Agent — decision support, never recommendation."""

    agent_id = "plea_trial_analyst"
    agent_name = "Plea / Trial Assessment Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate structured plea vs. trial comparison.

        Reads from CaseState fields, calls the LLM, validates output,
        and returns wrapped results with confidence scoring and flags.
        """
        case_id = input_data.get("case_id") or input_data.get("id", "unknown")
        self.log_action("plea_trial_analysis_started", {"case_id": case_id})

        # --- 1. Normalize field names ---
        case_data = self._normalize_fields(input_data)

        # --- 2. Determine flags early ---
        flags: list[str] = ["DECISION_SUPPORT_ONLY"]
        warnings: list[str] = []

        plea_offer = case_data.get("plea_offer", {})
        if not plea_offer:
            flags.append("MISSING_PLEA_OFFER")

        if not input_data.get("attorney_assessments"):
            flags.append("MISSING_ATTORNEY_INPUTS")

        attorney_assessments = case_data.get("attorney_assessments", {})

        collateral = case_data.get("collateral_consequences", {})
        if not collateral:
            flags.append("MISSING_COLLATERAL_DATA")

        # --- 3. Call LLM ---
        try:
            user_prompt = build_plea_trial_user_prompt(case_data)
            llm_result = await call_llm(
                user_prompt,
                system=PLEA_TRIAL_SYSTEM_PROMPT,
                max_tokens=4096,
            )
        except Exception:
            logger.error("LLM call failed for case %s", case_id)
            self.log_action("plea_trial_llm_error", {"case_id": case_id})
            error_output = self._build_error_output(flags)
            return self.wrap_output(error_output, confidence=0.0)

        # --- 4. Parse and validate ---
        try:
            parsed = self._parse_llm_response(llm_result, plea_offer)
        except Exception:
            logger.error("Failed to parse LLM response for case %s", case_id)
            self.log_action("plea_trial_parse_error", {"case_id": case_id})
            error_output = self._build_error_output(flags)
            return self.wrap_output(error_output, confidence=0.0)

        # --- 5. Validate trial outcome probabilities ---
        trial_outcomes = parsed.get("trial_scenario", {}).get("outcomes", [])
        trial_outcomes, prob_flags = self._validate_probabilities(trial_outcomes)
        flags.extend(prob_flags)
        if trial_outcomes:
            parsed.setdefault("trial_scenario", {})["outcomes"] = trial_outcomes

        # --- 6. Calculate confidence (after probability validation) ---
        confidence = self._calculate_confidence(
            case_data, attorney_assessments, probability_flags=prob_flags
        )

        confidence_level = self.score_confidence(confidence).value

        if confidence < 0.6:
            flags.append("LOW_CONFIDENCE_ASSESSMENT")

        # --- 7. Suppression motion check ---
        draft_motions = case_data.get("draft_motions", [])
        suppression_motions = [
            m for m in draft_motions if "suppress" in str(m.get("motion_type", "")).lower()
        ]
        for motion in suppression_motions:
            viability = motion.get("confidence", motion.get("viability", 0.0))
            if isinstance(viability, (int, float)) and viability >= 0.7:
                flags.append("SUPPRESSION_MOTION_CRITICAL")
                break

        # --- 8. Bias check ---
        comparison_matrix = parsed.get("comparison_matrix", {})
        if self._check_plea_bias(comparison_matrix):
            flags.append("BIAS_CHECK")

        # --- 9. Trial-may-be-warranted check ---
        dimensions = comparison_matrix.get("dimensions", [])
        trial_advantages = sum(1 for d in dimensions if d.get("advantage") == "TRIAL")
        if trial_advantages >= 4:
            flags.append("TRIAL_MAY_BE_WARRANTED")

        # --- 10. Collateral consequences severity check ---
        plea_scenario = parsed.get("plea_scenario", {})
        collateral_details = plea_scenario.get("collateral_consequences_detail", [])
        if any(c.get("severity") == "HIGH" for c in collateral_details):
            flags.append("SIGNIFICANT_COLLATERAL_CONSEQUENCES")

        # --- 11. First offender eligibility check ---
        if plea_scenario.get("diversion_eligible") or parsed.get("trial_scenario", {}).get(
            "first_offender_eligible"
        ):
            flags.append("FIRST_OFFENDER_ELIGIBLE")
        # Also check from LLM flags
        llm_flags = parsed.get("flags", [])
        for f in llm_flags:
            if "FIRST_OFFENDER" in str(f).upper() and "FIRST_OFFENDER_ELIGIBLE" not in flags:
                flags.append("FIRST_OFFENDER_ELIGIBLE")

        # --- 12. Record attorney inputs used ---
        attorney_inputs_used: dict[str, Any] = {}
        if input_data.get("attorney_assessments"):
            for key, value in attorney_assessments.items():
                attorney_inputs_used[key] = value
        else:
            attorney_inputs_used["_note"] = "No attorney inputs provided; defaults used"

        # --- 13. Build final output ---
        parsed["confidence"] = confidence
        parsed["confidence_level"] = confidence_level
        parsed["confidence_reasoning"] = parsed.get(
            "confidence_reasoning",
            self._build_confidence_reasoning(
                case_data, attorney_assessments, confidence, probability_flags=prob_flags
            ),
        )
        parsed["flags"] = flags
        parsed["warnings"] = warnings
        parsed["attorney_inputs_used"] = attorney_inputs_used
        parsed["agent_name"] = "plea_trial_analyst"
        parsed["decision_support_warning"] = "DECISION SUPPORT ONLY — ATTORNEY AND CLIENT DECIDE"
        parsed["privilege_warning"] = "ATTORNEY-CLIENT PRIVILEGED MATERIAL"
        parsed["draft_warning"] = "DRAFT — ATTORNEY REVIEW REQUIRED"

        self.log_action("plea_trial_analysis_completed", {"case_id": case_id})

        return self.wrap_output(parsed, confidence=confidence)

    # ------------------------------------------------------------------
    # Field normalization
    # ------------------------------------------------------------------

    def _normalize_fields(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Accept multiple field name conventions from CaseState."""
        data: dict[str, Any] = dict(input_data)

        # charges
        data.setdefault(
            "charges",
            input_data.get("charge_processing", {}).get("charges", []),
        )

        # rights violations
        data.setdefault(
            "rights_violations",
            input_data.get("rights_violation_analysis", input_data.get("rights_violations", [])),
        )

        # intake
        data.setdefault(
            "intake_summary",
            input_data.get("intake", input_data.get("intake_summary", {})),
        )

        # legal research
        data.setdefault(
            "legal_research",
            input_data.get("case_law_research", input_data.get("legal_research", {})),
        )

        # collateral consequences
        data.setdefault(
            "collateral_consequences",
            input_data.get("collateral_consequences", {}),
        )

        # draft motions — handle both dict-wrapped and list forms
        raw_motions = input_data.get("draft_motions", {})
        if isinstance(raw_motions, dict):
            data["draft_motions"] = raw_motions.get(
                "motions", raw_motions.get("data", {}).get("motions", [])
            )
        elif isinstance(raw_motions, list):
            data["draft_motions"] = raw_motions
        else:
            data["draft_motions"] = []

        # brady
        data.setdefault(
            "brady_analysis",
            input_data.get("brady", input_data.get("brady_analysis", {})),
        )

        # plea offer
        data.setdefault("plea_offer", input_data.get("plea_offer", {}))

        # attorney assessments — apply defaults if missing
        raw_assessments = input_data.get("attorney_assessments", {})
        if not raw_assessments:
            data["attorney_assessments"] = dict(_DEFAULT_ATTORNEY_ASSESSMENTS)
        else:
            # Fill in any missing keys with defaults
            merged = dict(_DEFAULT_ATTORNEY_ASSESSMENTS)
            merged.update(raw_assessments)
            data["attorney_assessments"] = merged

        return data

    # ------------------------------------------------------------------
    # LLM response parsing
    # ------------------------------------------------------------------

    def _parse_llm_response(
        self, llm_result: dict[str, Any], plea_offer: dict[str, Any]
    ) -> dict[str, Any]:
        """Parse and lightly validate the LLM JSON response."""
        # The LLM should return the structure matching PleaTrialOutput fields.
        # We do a best-effort parse — missing fields get defaults.
        parsed: dict[str, Any] = {}

        # Plea scenario
        plea_raw = llm_result.get("plea_scenario", {})
        if plea_raw and plea_offer:
            parsed["plea_scenario"] = plea_raw
        else:
            # Build minimal plea scenario when no offer
            parsed["plea_scenario"] = {
                "offer_description": "No plea offer provided",
                "plea_charge": "",
                "plea_charge_statute": "",
                "original_charges": [],
                "sentences": {
                    "label": "N/A — no plea offer",
                    "probability": 0.0,
                    "probability_reasoning": "No plea offer available for analysis",
                    "incarceration_months": 0,
                    "probation_months": 0,
                    "fine_amount": 0,
                    "criminal_record_impact": "N/A",
                },
                "collateral_consequences_detail": [],
                "diversion_eligible": False,
                "diversion_details": "",
                "expungement_eligible": False,
                "expungement_details": "",
            }

        # Trial scenario
        parsed["trial_scenario"] = llm_result.get(
            "trial_scenario",
            {
                "outcomes": [],
                "expected_incarceration_months": 0,
                "expected_probation_months": 0,
                "trial_penalty_estimate": "Unable to assess",
                "key_strengths": [],
                "key_weaknesses": [],
                "suppression_motion_impact": "No suppression motion filed",
            },
        )

        # Comparison matrix
        parsed["comparison_matrix"] = llm_result.get(
            "comparison_matrix",
            {
                "dimensions": [],
            },
        )

        # Risk factors
        parsed["risk_factors"] = llm_result.get("risk_factors", [])

        # LLM-generated flags and confidence reasoning
        parsed["flags"] = llm_result.get("flags", [])
        parsed["confidence_reasoning"] = llm_result.get("confidence_reasoning", "")

        return parsed

    # ------------------------------------------------------------------
    # Probability validation
    # ------------------------------------------------------------------

    def _validate_probabilities(
        self, outcomes: list[dict[str, Any]]
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Validate and normalize trial outcome probabilities."""
        flags: list[str] = []
        if not outcomes:
            return outcomes, flags

        total = sum(o.get("probability", 0) for o in outcomes)
        if abs(total - 1.0) > 0.1:
            flags.append(f"PROBABILITY_SUM_ERROR: outcomes sum to {total:.2f}, normalized to 1.0")
            if total > 0:
                for o in outcomes:
                    o["probability"] = o["probability"] / total
        return outcomes, flags

    # ------------------------------------------------------------------
    # Bias check
    # ------------------------------------------------------------------

    def _check_plea_bias(self, matrix: dict[str, Any]) -> bool:
        """Return True if every dimension favors PLEA — a red flag for systemic bias."""
        dimensions = matrix.get("dimensions", [])
        if not dimensions:
            return False
        return all(d.get("advantage") == "PLEA" for d in dimensions)

    # ------------------------------------------------------------------
    # Confidence scoring
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self,
        case_data: dict[str, Any],
        attorney_assessments: dict[str, Any],
        probability_flags: list[str] | None = None,
    ) -> float:
        """Calculate confidence based on data completeness and attorney inputs."""
        base = 0.60

        # +0.05 per present upstream source (max 7 sources = +0.35)
        for source in _UPSTREAM_SOURCES:
            if case_data.get(source):
                base += 0.05

        # +0.10 if most attorney inputs are present
        if attorney_assessments:
            expected_keys = {
                "estimated_acquittal_probability",
                "judge_sentencing_tendency",
                "witness_credibility_assessment",
                "client_testimony_viability",
            }
            present = sum(1 for k in expected_keys if k in attorney_assessments)
            if present >= 3:
                base += 0.10

        # Citation verification: check legal research for unverified citations
        legal = case_data.get("legal_research", {})
        all_citations: list[Any] = []
        for key in ("relevant_case_law", "case_law", "relevant_statutes", "statutes"):
            items = legal.get(key, [])
            if isinstance(items, list):
                all_citations.extend(items)
        if all_citations:
            unverified = sum(1 for c in all_citations if "UNVERIFIED" in str(c).upper())
            if unverified == 0:
                base += 0.05
            elif unverified > len(all_citations) / 2:
                base -= 0.05

        # Probability consistency penalty
        if probability_flags:
            prob_errors = [f for f in probability_flags if "PROBABILITY_SUM_ERROR" in f]
            if prob_errors:
                base -= 0.10

        return max(0.0, min(base, 1.0))

    def _build_confidence_reasoning(
        self,
        case_data: dict[str, Any],
        attorney_assessments: dict[str, Any],
        confidence: float,
        probability_flags: list[str] | None = None,
    ) -> str:
        """Build a human-readable explanation of the confidence score."""
        parts: list[str] = ["Base confidence: 0.60."]

        present_sources = [s for s in _UPSTREAM_SOURCES if case_data.get(s)]
        parts.append(
            f"Upstream sources present: {len(present_sources)}/{len(_UPSTREAM_SOURCES)} "
            f"(+{len(present_sources) * 0.05:.2f})."
        )

        if attorney_assessments:
            parts.append("Attorney subjective inputs provided (+0.10).")
        else:
            parts.append("Attorney subjective inputs not provided (+0.00).")

        # Citation verification status
        legal = case_data.get("legal_research", {})
        all_citations: list[Any] = []
        for key in ("relevant_case_law", "case_law", "relevant_statutes", "statutes"):
            items = legal.get(key, [])
            if isinstance(items, list):
                all_citations.extend(items)
        if all_citations:
            unverified = sum(1 for c in all_citations if "UNVERIFIED" in str(c).upper())
            if unverified == 0:
                parts.append("All citations verified (+0.05).")
            elif unverified > len(all_citations) / 2:
                parts.append(
                    f"Majority of citations unverified ({unverified}/{len(all_citations)}) (-0.05)."
                )
            else:
                parts.append(
                    f"Some citations unverified ({unverified}/{len(all_citations)}) (+0.00)."
                )

        # Probability consistency
        if probability_flags:
            prob_errors = [f for f in probability_flags if "PROBABILITY_SUM_ERROR" in f]
            if prob_errors:
                parts.append("Trial outcome probabilities required normalization (-0.10).")

        parts.append(f"Final confidence: {confidence:.2f}.")
        return " ".join(parts)

    # ------------------------------------------------------------------
    # Error output
    # ------------------------------------------------------------------

    def _build_error_output(self, flags: list[str]) -> dict[str, Any]:
        """Build a minimal output when the LLM call or parsing fails."""
        return {
            "plea_scenario": {
                "offer_description": "Analysis failed",
                "plea_charge": "",
                "plea_charge_statute": "",
                "original_charges": [],
                "sentences": {
                    "label": "Error",
                    "probability": 0.0,
                    "probability_reasoning": "LLM analysis failed",
                    "incarceration_months": 0,
                    "probation_months": 0,
                    "fine_amount": 0,
                    "criminal_record_impact": "Unable to assess",
                },
            },
            "trial_scenario": {
                "outcomes": [],
                "expected_incarceration_months": 0,
                "expected_probation_months": 0,
                "trial_penalty_estimate": "Unable to assess",
                "key_strengths": [],
                "key_weaknesses": [],
                "suppression_motion_impact": "Unable to assess",
            },
            "comparison_matrix": {"dimensions": []},
            "risk_factors": [],
            "confidence": 0.0,
            "confidence_level": "LOW",
            "confidence_reasoning": "Analysis failed due to LLM or parsing error",
            "flags": flags + ["LOW_CONFIDENCE_ASSESSMENT"],
            "warnings": ["Analysis could not be completed"],
            "agent_name": "plea_trial_analyst",
            "decision_support_warning": "DECISION SUPPORT ONLY — ATTORNEY AND CLIENT DECIDE",
            "privilege_warning": "ATTORNEY-CLIENT PRIVILEGED MATERIAL",
            "draft_warning": "DRAFT — ATTORNEY REVIEW REQUIRED",
            "attorney_inputs_used": {},
        }
