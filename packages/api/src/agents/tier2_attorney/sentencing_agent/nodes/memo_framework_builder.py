"""Node 8: Memo Framework Builder — Template-based sentencing memo structure.

Template-based. No LLM calls for structure; content pulled from prior nodes.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models.outputs import (
    GuidelineRange,
    MitigationNarrative,
    NodeAuditRecord,
    SentencingMemoFramework,
)
from ..models.state import SentencingGraphState


def build_memo_framework(state: SentencingGraphState) -> SentencingMemoFramework:
    """Build the sentencing memo framework from prior node outputs."""
    input_data = state["input"]
    guideline_range: GuidelineRange | None = state.get("guideline_range")
    narrative: MitigationNarrative | None = state.get("mitigation_narrative")
    diversion_options = state.get("diversion_options") or []
    comparables = state.get("comparable_sentences") or []
    departure_args = state.get("departure_arguments") or []

    has_unsupported_claims = bool(narrative and narrative.unsupported_claim_warnings)

    sections = [
        {
            "heading": "Introduction",
            "content": (
                f"This memorandum is submitted on behalf of the defendant in Case {input_data.case_id}, "
                f"charged with simple possession of marijuana (one ounce or less) in "
                f"{input_data.jurisdiction_context.county} County, Georgia. "
                "Defense counsel respectfully requests that the Court consider the following "
                "mitigating factors and alternative sentencing options."
            ),
            "attorney_action": "ANNOTATION_REQUIRED",
            "engagement_level": "HIGH",
        },
        {
            "heading": "Offense Context",
            "content": (
                f"The defendant is charged under {input_data.offense_details.statute} with "
                f"{input_data.offense_details.charge_description}. "
                f"The quantity alleged is {input_data.offense_details.quantity_text or 'as stated in the charging instrument'}."
            ),
            "attorney_action": "REVIEW",
            "engagement_level": "LOW",
        },
        {
            "heading": "Statutory Sentencing Exposure",
            "content": (
                (
                    f"Under O.C.G.A. § 16-13-2(b), this offense carries a maximum of "
                    f"{guideline_range.statutory_maximum} days imprisonment and/or a fine up to "
                    f"${guideline_range.fine_maximum:,.2f}. "
                    f"There is no mandatory minimum. "
                    f"Time-served credit: {guideline_range.time_served_credit_days} day(s). "
                    + (
                        "Weekend service is available if any jail sentence imposed is six months or less. "
                        if guideline_range.weekend_service_possible
                        else ""
                    )
                    + "Probation and suspended sentences are available at the Court's discretion."
                )
                if guideline_range
                else "[Exposure calculation unavailable — attorney must calculate manually]"
            ),
            "attorney_action": "ANNOTATION_REQUIRED",
            "engagement_level": "HIGH",
        },
        {
            "heading": "Diversion and Deferral Options",
            "content": _format_diversion_section(diversion_options),
            "attorney_action": "ANNOTATION_REQUIRED",
            "engagement_level": "HIGH",
        },
        {
            "heading": "Mitigating Factors",
            "content": (
                narrative.full_narrative
                if narrative
                else "[Mitigation narrative pending — attorney input required]"
            ),
            "attorney_action": "EDIT_REQUIRED" if has_unsupported_claims else "EDIT_REQUIRED",
            "engagement_level": "MEDIUM",
        },
        {
            "heading": "Comparable Outcomes",
            "content": _format_comparables_section(comparables),
            "attorney_action": "REVIEW",
            "engagement_level": "LOW",
        },
        {
            "heading": "Requested Alternative Sentence",
            "content": _format_alternative_sentence_section(departure_args),
            "attorney_action": "FILL_IN",
            "engagement_level": "HIGH",
        },
        {
            "heading": "Conclusion",
            "content": (
                "For the foregoing reasons, defense counsel respectfully requests that the Court "
                "consider the mitigating circumstances, the defendant's personal history, and the "
                "available alternative sentencing options in fashioning an appropriate disposition. "
                "[ATTORNEY: Insert specific sentencing request here.]"
            ),
            "attorney_action": "FILL_IN",
            "engagement_level": "HIGH",
        },
    ]

    recommended_attachments = [
        "Character reference letters (if available)",
        "Employment verification",
        "Treatment records (if applicable, with appropriate releases)",
        "Educational records (if applicable)",
    ]

    return SentencingMemoFramework(
        title=f"Sentencing Memorandum — Case {input_data.case_id}",
        sections=sections,
        recommended_attachments=recommended_attachments,
        filing_notes=(
            "DRAFT — ATTORNEY REVIEW REQUIRED. This memo framework must be reviewed, "
            "annotated, and approved by supervising attorney before filing."
        ),
    )


def _format_diversion_section(diversion_options: list) -> str:
    """Format diversion options into memo text."""
    if not diversion_options:
        return "[No diversion options assessed — attorney should evaluate manually]"

    lines = ["The following diversion and deferral options have been identified:\n"]
    for opt in diversion_options:
        avail = getattr(opt, "availability_status", "unknown")
        elig = getattr(opt, "preliminary_eligibility", "unknown")
        lines.append(
            f"**{opt.program_name}** ({opt.statutory_basis}): "
            f"Availability: {avail.replace('_', ' ')}. "
            f"Preliminary eligibility: {elig}. "
            f"{opt.outcome_if_completed}"
        )

    return "\n\n".join(lines)


def _format_comparables_section(comparables: list) -> str:
    """Format comparable sentences into memo text."""
    if not comparables:
        return "No comparable sentencing outcomes are available in the current corpus for this county or circuit."

    lines = ["The following comparable outcomes have been identified:\n"]
    for comp in comparables:
        lines.append(
            f"- **{comp.jurisdiction}**: {comp.sentence_imposed} "
            f"(Source: {comp.source}, Status: {comp.verification_status})"
        )

    return "\n".join(lines)


def _format_alternative_sentence_section(departure_args: list) -> str:
    """Format alternative sentence arguments into memo text."""
    if not departure_args:
        return "[ATTORNEY: Specify the requested alternative sentence based on the above analysis.]"

    lines = [
        "Based on the analysis above, the following alternative sentencing arguments are available:\n"
    ]
    for arg in departure_args:
        lines.append(f"- **{arg.basis}** (Strength: {arg.strength}): {arg.notes}")

    lines.append(
        "\n[ATTORNEY: Select and refine the appropriate sentencing request for this case.]"
    )
    return "\n".join(lines)


def memo_framework_builder(state: SentencingGraphState) -> SentencingGraphState:
    """Memo framework builder node — creates template-based memo structure."""
    started_at = datetime.now(timezone.utc).isoformat()
    audit_records: list[NodeAuditRecord] = list(state.get("audit_records") or [])

    if state.get("scope_status") != "in_scope":
        audit_records.append(
            NodeAuditRecord(
                node_name="memo_framework_builder",
                status="skipped",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                warnings=["Skipped: case is not in scope"],
                output_keys=[],
            )
        )
        state["audit_records"] = audit_records
        return state

    memo = build_memo_framework(state)
    state["sentencing_memo"] = memo

    audit_records.append(
        NodeAuditRecord(
            node_name="memo_framework_builder",
            status="ok",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            output_keys=["sentencing_memo"],
        )
    )
    state["audit_records"] = audit_records
    return state
