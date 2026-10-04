"""Motion Drafter Agent — Tier 2 Attorney Prep.

Generates preliminary motion drafts based on intake facts and legal research.
Drafts are 70% complete — attorney reviews, edits, and files.

All data flows through CaseState. This agent never communicates directly
with other agents.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.motions import (
    DraftMotion,
    MotionDrafterOutput,
    MotionSection,
    MotionType,
)
from src.services.llm_service import call_llm

from .prompts import MOTION_DRAFTER_SYSTEM_PROMPT, build_motion_user_prompt
from .templates import TEMPLATES

STATUS = "REAL"

logger = logging.getLogger(__name__)


class MotionDrafterAgent(BaseAgent):
    """Generates draft motions from synthesized case data.

    Reads: charges, rights_violation_analysis, intake_summary, case_law_research,
           statute_analysis, brady_analysis from CaseState.
    Writes: draft_motions on CaseState.
    """

    agent_id = "motion_drafter"
    agent_name = "Motion Drafter Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate draft motions based on case analysis.

        Args:
            input_data: Dict extracted from CaseState fields. Expected keys:
                - case_id: str
                - jurisdiction: str
                - charges: list[dict] (from charge_processing)
                - rights_violations: list[dict] (from rights_violation_analysis)
                - intake_summary: dict (from intake_summary)
                - legal_research: dict (statute_analysis + case_law_research)
                - brady_analysis: dict
                - case_number: str | None

        Returns:
            Wrapped output containing MotionDrafterOutput data.
        """
        self.log_action(
            "motion_drafting_started",
            {"case_id": input_data.get("case_id", "")},
        )

        # Extract upstream data
        charges = input_data.get("charges", [])
        rights_violations = input_data.get("rights_violations", [])
        intake_summary = input_data.get("intake_summary", {})
        legal_research = input_data.get("legal_research", {})
        brady_analysis = input_data.get("brady_analysis", {})
        jurisdiction = input_data.get("jurisdiction", "GA")
        case_id = input_data.get("case_id", "")
        case_number = input_data.get("case_number")

        # Determine applicable motions
        applicable = self._determine_applicable_motions(
            charges=charges,
            rights_violations=rights_violations,
            intake_summary=intake_summary,
            brady_analysis=brady_analysis,
            legal_research=legal_research,
        )

        motions: list[DraftMotion] = []
        motions_not_generated: list[dict[str, str]] = []
        all_flags: list[str] = []

        for motion_type, reason_applicable in applicable:
            template = TEMPLATES.get(motion_type.value)
            if template is None:
                motions_not_generated.append(
                    {"motion_type": motion_type.value, "reason": "No template available"}
                )
                continue

            case_data = self._build_case_data_for_motion(
                motion_type=motion_type,
                charges=charges,
                rights_violations=rights_violations,
                intake_summary=intake_summary,
                legal_research=legal_research,
                brady_analysis=brady_analysis,
                jurisdiction=jurisdiction,
                case_number=case_number,
            )

            draft = await self._generate_motion(
                motion_type=motion_type,
                template=template,
                case_data=case_data,
            )

            if draft is not None:
                # Score confidence
                confidence_score = self._calculate_confidence(
                    motion_type=motion_type,
                    charges=charges,
                    rights_violations=rights_violations,
                    intake_summary=intake_summary,
                    legal_research=legal_research,
                    brady_analysis=brady_analysis,
                    draft=draft,
                )
                confidence_level = self.score_confidence(confidence_score)

                # Determine flags
                motion_flags = self._determine_flags(
                    draft=draft,
                    confidence_score=confidence_score,
                    intake_summary=intake_summary,
                    rights_violations=rights_violations,
                    legal_research=legal_research,
                    motion_type=motion_type,
                )

                final_motion = DraftMotion(
                    motion_type=motion_type,
                    title=draft.get("title", ""),
                    case_caption=draft.get("case_caption", ""),
                    court=draft.get("court", ""),
                    sections=[
                        MotionSection(
                            heading=s.get("heading", ""),
                            content=s.get("content", ""),
                            citations=s.get("citations", []),
                        )
                        for s in draft.get("sections", [])
                    ],
                    prayer_for_relief=draft.get("prayer_for_relief", ""),
                    filing_deadline=draft.get("filing_deadline"),
                    filing_deadline_basis=draft.get("filing_deadline_basis"),
                    confidence=confidence_score,
                    confidence_level=confidence_level.value,
                    confidence_reasoning=draft.get(
                        "confidence_reasoning",
                        f"Auto-scored based on data completeness: {confidence_score:.2f}",
                    ),
                    flags=motion_flags,
                )
                motions.append(final_motion)
                all_flags.extend(motion_flags)

        # Record motions not generated
        skipped = self._get_skipped_motions(
            applicable_types={m.value for m, _ in applicable},
            charges=charges,
            rights_violations=rights_violations,
            intake_summary=intake_summary,
            brady_analysis=brady_analysis,
            legal_research=legal_research,
        )
        motions_not_generated.extend(skipped)

        # Calculate overall confidence
        if motions:
            overall_confidence = sum(m.confidence for m in motions) / len(motions)
        else:
            overall_confidence = 0.0
        overall_level = self.score_confidence(overall_confidence)

        output = MotionDrafterOutput(
            motions=motions,
            motions_not_generated=motions_not_generated,
            overall_confidence=overall_confidence,
            overall_confidence_level=overall_level.value,
            flags=list(set(all_flags)),
            warnings=self._generate_warnings(motions, motions_not_generated),
        )

        self.log_action(
            "motion_drafting_completed",
            {
                "case_id": case_id,
                "motions_generated": len(motions),
                "motions_skipped": len(motions_not_generated),
            },
        )

        return self.wrap_output(
            output.model_dump(),
            confidence=overall_confidence,
        )

    # ------------------------------------------------------------------
    # Motion applicability logic
    # ------------------------------------------------------------------

    def _determine_applicable_motions(
        self,
        charges: list[dict[str, Any]],
        rights_violations: list[dict[str, Any]],
        intake_summary: dict[str, Any],
        brady_analysis: dict[str, Any],
        legal_research: dict[str, Any],
    ) -> list[tuple[MotionType, str]]:
        """Determine which motions should be generated for this case."""
        applicable: list[tuple[MotionType, str]] = []

        # Suppression: if rights violations with viability >= 0.6
        viable_violations = [
            v for v in rights_violations if v.get("suppression_viability", 0) >= 0.6
        ]
        if viable_violations:
            applicable.append(
                (
                    MotionType.SUPPRESS,
                    f"{len(viable_violations)} rights violation(s) with viable suppression",
                )
            )

        # Discovery / Brady: always generated
        applicable.append(
            (
                MotionType.DISCOVERY_BRADY,
                "Discovery demand generated for every case",
            )
        )

        # Bail reduction: if client is in custody or bail/bond issues
        personal = intake_summary.get("personal_circumstances", {})
        in_custody = (
            personal.get("custody_status") == "IN_CUSTODY"
            or intake_summary.get("in_custody", False)
            or any(
                "bail" in str(f).lower() or "bond" in str(f).lower()
                for f in intake_summary.get("inconsistencies", [])
            )
        )
        if in_custody:
            applicable.append(
                (
                    MotionType.BAIL_REDUCTION,
                    "Client is in custody or bail/bond issues identified",
                )
            )

        # Dismiss: charging defects, speedy trial, or statute of limitations
        procedural_flags = []
        for charge in charges:
            procedural_flags.extend(charge.get("procedural_requirements", []))
            procedural_flags.extend(charge.get("procedural_flags", []))
        statutes = legal_research.get("statutes", [])
        has_dismissal_basis = any(
            "speedy" in str(f).lower()
            or "limitation" in str(f).lower()
            or "defect" in str(f).lower()
            or "deficient" in str(f).lower()
            for f in procedural_flags
        ) or any("speedy" in str(s).lower() or "limitation" in str(s).lower() for s in statutes)
        if has_dismissal_basis:
            applicable.append(
                (
                    MotionType.DISMISS,
                    "Procedural or limitations basis for dismissal identified",
                )
            )

        # Limine: evidentiary issues flagged
        case_law = legal_research.get("case_law", []) or legal_research.get("authorities", [])
        has_evidentiary_issues = any(
            "evidentiary" in str(f).lower()
            or "prejudic" in str(f).lower()
            or "character" in str(f).lower()
            or "hearsay" in str(f).lower()
            or "prior bad" in str(f).lower()
            or "404" in str(f).lower()
            for f in procedural_flags
        ) or any(
            "limine" in str(c).lower()
            or "403" in str(c).lower()
            or "404" in str(c).lower()
            or "prejudic" in str(c).lower()
            for c in case_law
        )
        if has_evidentiary_issues:
            applicable.append(
                (
                    MotionType.LIMINE,
                    "Evidentiary issues identified for pretrial exclusion",
                )
            )

        return applicable

    def _get_skipped_motions(
        self,
        applicable_types: set[str],
        charges: list[dict[str, Any]],
        rights_violations: list[dict[str, Any]],
        intake_summary: dict[str, Any],
        brady_analysis: dict[str, Any],
        legal_research: dict[str, Any],
    ) -> list[dict[str, str]]:
        """Report on motion types NOT generated and why."""
        skipped: list[dict[str, str]] = []
        all_types = {mt.value for mt in MotionType}
        for mt_value in all_types - applicable_types:
            if mt_value == MotionType.SUPPRESS.value:
                viable = [v for v in rights_violations if v.get("suppression_viability", 0) >= 0.6]
                if not rights_violations:
                    reason = "No rights violations identified by upstream agents"
                elif not viable:
                    reason = (
                        "Rights violations present but suppression viability below 0.6 threshold"
                    )
                else:
                    reason = "Unknown"
            elif mt_value == MotionType.BAIL_REDUCTION.value:
                reason = "No indication client is in custody or has bail/bond issues"
            elif mt_value == MotionType.DISMISS.value:
                reason = "No charging defects, speedy trial issues, or statute of limitations flags identified"
            elif mt_value == MotionType.LIMINE.value:
                reason = "No anticipated evidentiary issues flagged by research agents"
            else:
                reason = "Not applicable based on current case data"
            skipped.append({"motion_type": mt_value, "reason": reason})
        return skipped

    # ------------------------------------------------------------------
    # Case data assembly
    # ------------------------------------------------------------------

    def _build_case_data_for_motion(
        self,
        motion_type: MotionType,
        charges: list[dict[str, Any]],
        rights_violations: list[dict[str, Any]],
        intake_summary: dict[str, Any],
        legal_research: dict[str, Any],
        brady_analysis: dict[str, Any],
        jurisdiction: str,
        case_number: str | None,
    ) -> dict[str, Any]:
        """Build the case data dict passed to the LLM for a specific motion."""
        base: dict[str, Any] = {
            "jurisdiction": jurisdiction,
            "case_number": case_number or "[CASE NUMBER]",
            "charges": charges,
        }

        if motion_type == MotionType.SUPPRESS:
            base["rights_violations"] = [
                v for v in rights_violations if v.get("suppression_viability", 0) >= 0.6
            ]
            base["client_account"] = intake_summary.get("client_account", "")
            base["fact_timeline"] = intake_summary.get("fact_timeline", [])
            base["facts"] = intake_summary.get("facts", [])
            base["inconsistencies"] = intake_summary.get("inconsistencies", [])
            base["case_law"] = legal_research.get("case_law", []) or legal_research.get(
                "authorities", []
            )
            base["statutes"] = legal_research.get("statutes", [])

        elif motion_type == MotionType.BAIL_REDUCTION:
            base["personal_circumstances"] = intake_summary.get("personal_circumstances", {})
            base["client_account"] = intake_summary.get("client_account", "")
            base["facts"] = intake_summary.get("facts", [])

        elif motion_type == MotionType.DISMISS:
            base["case_law"] = legal_research.get("case_law", []) or legal_research.get(
                "authorities", []
            )
            base["statutes"] = legal_research.get("statutes", [])
            base["procedural_flags"] = []
            for charge in charges:
                base["procedural_flags"].extend(charge.get("procedural_requirements", []))
                base["procedural_flags"].extend(charge.get("procedural_flags", []))

        elif motion_type == MotionType.DISCOVERY_BRADY:
            base["brady_analysis"] = brady_analysis
            base["case_law"] = legal_research.get("case_law", []) or legal_research.get(
                "authorities", []
            )

        elif motion_type == MotionType.LIMINE:
            base["case_law"] = legal_research.get("case_law", []) or legal_research.get(
                "authorities", []
            )
            base["client_account"] = intake_summary.get("client_account", "")
            base["facts"] = intake_summary.get("facts", [])
            base["inconsistencies"] = intake_summary.get("inconsistencies", [])

        return base

    # ------------------------------------------------------------------
    # LLM call
    # ------------------------------------------------------------------

    async def _generate_motion(
        self,
        motion_type: MotionType,
        template: dict[str, Any],
        case_data: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Call the LLM to generate a single motion draft."""
        user_prompt = build_motion_user_prompt(
            motion_type=motion_type.value,
            template=template,
            case_data=case_data,
        )

        try:
            result = await call_llm(
                prompt=user_prompt,
                system=MOTION_DRAFTER_SYSTEM_PROMPT,
                max_tokens=4096,
            )
            return result
        except (json.JSONDecodeError, KeyError) as exc:
            # Log only case_id and motion_type — no client data
            logger.error(
                "Failed to parse LLM response for motion_type=%s: %s",
                motion_type.value,
                type(exc).__name__,
            )
            return None
        except Exception as exc:
            logger.error(
                "LLM call failed for motion_type=%s: %s",
                motion_type.value,
                type(exc).__name__,
            )
            return None

    # ------------------------------------------------------------------
    # Confidence scoring
    # ------------------------------------------------------------------

    def _calculate_confidence(
        self,
        motion_type: MotionType,
        charges: list[dict[str, Any]],
        rights_violations: list[dict[str, Any]],
        intake_summary: dict[str, Any],
        legal_research: dict[str, Any],
        brady_analysis: dict[str, Any],
        draft: dict[str, Any],
    ) -> float:
        """Calculate a confidence score for a generated motion.

        Factors:
        - Completeness of upstream data
        - Citation verification status
        - Fact corroboration
        - Discrepancies between accounts
        """
        score = 0.7  # Base score for a successfully generated motion

        # Upstream data completeness (+0.15 max)
        data_bonus = 0.0
        if charges:
            data_bonus += 0.03
        if rights_violations and motion_type == MotionType.SUPPRESS:
            data_bonus += 0.03
        if intake_summary and intake_summary.get("facts") or intake_summary.get("client_account"):
            data_bonus += 0.03
        case_law = legal_research.get("case_law", []) or legal_research.get("authorities", [])
        if case_law:
            data_bonus += 0.03
        if brady_analysis and motion_type == MotionType.DISCOVERY_BRADY:
            data_bonus += 0.03
        score += data_bonus

        # Citation verification (+0.1 if all verified, -0.1 if mostly unverified)
        all_citations: list[str] = []
        for section in draft.get("sections", []):
            all_citations.extend(section.get("citations", []))
        if all_citations:
            verified_count = sum(1 for c in all_citations if "[VERIFIED]" in c.upper())
            verification_ratio = verified_count / len(all_citations)
            score += 0.1 * (verification_ratio - 0.5)  # +0.05 if all verified, -0.05 if none

        # Discrepancies penalty
        inconsistencies = intake_summary.get("inconsistencies", [])
        if inconsistencies:
            score -= min(0.05 * len(inconsistencies), 0.15)

        # Clamp
        return max(0.0, min(1.0, score))

    # ------------------------------------------------------------------
    # Flags
    # ------------------------------------------------------------------

    def _determine_flags(
        self,
        draft: dict[str, Any],
        confidence_score: float,
        intake_summary: dict[str, Any],
        rights_violations: list[dict[str, Any]],
        legal_research: dict[str, Any],
        motion_type: MotionType,
    ) -> list[str]:
        """Determine flags for attorney attention."""
        flags: list[str] = []

        # LOW confidence
        if confidence_score < 0.6:
            flags.append("LOW_CONFIDENCE_MOTION")

        # Unverified citations
        all_citations: list[str] = []
        for section in draft.get("sections", []):
            all_citations.extend(section.get("citations", []))
        if any("[UNVERIFIED" in c.upper() for c in all_citations):
            flags.append("UNVERIFIED_CITATIONS")

        # Fact discrepancy
        inconsistencies = intake_summary.get("inconsistencies", [])
        if inconsistencies:
            flags.append("FACT_DISCREPANCY")

        # Missing upstream data
        missing: list[str] = []
        if not intake_summary or (
            not intake_summary.get("facts") and not intake_summary.get("client_account")
        ):
            missing.append("intake_summary")
        case_law = legal_research.get("case_law", []) or legal_research.get("authorities", [])
        if not case_law:
            missing.append("case_law")
        if motion_type == MotionType.SUPPRESS and not rights_violations:
            missing.append("rights_violations")
        if missing:
            flags.append("MISSING_UPSTREAM_DATA")

        # Deadline imminent (from LLM flags)
        for flag in draft.get("flags", []):
            if "deadline" in str(flag).lower() and "imminent" in str(flag).lower():
                flags.append("DEADLINE_IMMINENT")
                break

        # Include LLM-generated flags
        for flag in draft.get("flags", []):
            if flag not in flags:
                flags.append(flag)

        return flags

    # ------------------------------------------------------------------
    # Warnings
    # ------------------------------------------------------------------

    def _generate_warnings(
        self,
        motions: list[DraftMotion],
        motions_not_generated: list[dict[str, str]],
    ) -> list[str]:
        """Generate top-level warnings for the output."""
        warnings: list[str] = []

        low_confidence = [m for m in motions if m.confidence < 0.6]
        if low_confidence:
            types = ", ".join(m.motion_type.value for m in low_confidence)
            warnings.append(f"LOW confidence on {len(low_confidence)} motion(s): {types}")

        if motions_not_generated:
            types = ", ".join(m["motion_type"] for m in motions_not_generated)
            warnings.append(f"{len(motions_not_generated)} motion type(s) not generated: {types}")

        if not motions:
            warnings.append("No motions were generated — review case data completeness")

        return warnings
