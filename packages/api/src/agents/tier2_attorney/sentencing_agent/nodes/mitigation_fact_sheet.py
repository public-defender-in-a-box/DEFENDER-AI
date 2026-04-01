"""Node 4: Mitigation Fact Sheet Builder — Structured facts with provenance.

Deterministic fact packaging. No LLM calls.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..models.inputs import PersonalCircumstances, SentencingAgentInput, SourceFact
from ..models.outputs import NodeAuditRecord
from ..models.state import MitigationFactSheet, SentencingGraphState

# Mitigation themes for categorization
THEME_MAP: dict[str, list[str]] = {
    "treatment_engagement": ["treatment", "substance_use", "mental_health", "recovery"],
    "employment_stability": ["employment", "employer"],
    "caregiving": ["dependents", "caregiving", "children"],
    "housing_stability": ["housing", "stable"],
    "education": ["education", "student", "school", "college"],
    "military_service": ["military", "veteran", "service"],
    "community_ties": ["community", "church", "volunteer"],
    "insight_responsibility": ["responsibility", "remorse", "insight"],
    "low_public_safety_risk": ["first_offense", "no_prior_record", "minor_offense"],
}


def _extract_facts_from_circumstances(
    circumstances: PersonalCircumstances,
) -> list[dict[str, Any]]:
    """Extract structured mitigation facts from personal circumstances."""
    facts: list[dict[str, Any]] = []
    fact_counter = 0

    def add_fact(
        text: str,
        category: str,
        themes: list[str],
        sensitivity_tags: list[str] | None = None,
    ) -> None:
        nonlocal fact_counter
        fact_counter += 1
        facts.append(
            {
                "fact_id": f"auto-{fact_counter}",
                "text": text,
                "source": "personal_circumstances_agent",
                "category": category,
                "themes": themes,
                "verification_status": "self_reported",
                "sensitivity_tags": sensitivity_tags or [],
            }
        )

    # Employment
    if circumstances.employment_status and circumstances.employment_status.lower() not in ("unknown", "n/a", ""):
        text = f"Employment status: {circumstances.employment_status}"
        if circumstances.employment_details:
            text += f" — {circumstances.employment_details}"
        add_fact(text, "employment", ["employment_stability"])

    if circumstances.employer_supportive is True:
        add_fact("Employer is supportive of defendant", "employment", ["employment_stability"])

    # Housing
    if circumstances.housing_stable is True:
        text = "Housing is stable"
        if circumstances.housing_details:
            text += f" — {circumstances.housing_details}"
        add_fact(text, "housing", ["housing_stability"])
    elif circumstances.housing_stable is False:
        add_fact(
            "Housing instability noted",
            "housing",
            ["housing_stability"],
            sensitivity_tags=["housing_instability"],
        )

    # Dependents / caregiving
    if circumstances.dependents:
        add_fact(
            f"Dependents: {', '.join(circumstances.dependents)}",
            "family",
            ["caregiving"],
        )
    if circumstances.caregiving_obligations:
        add_fact(
            f"Caregiving obligations: {circumstances.caregiving_obligations}",
            "family",
            ["caregiving"],
        )

    # Education
    if circumstances.education_status and circumstances.education_status.lower() not in ("unknown", "n/a", ""):
        text = f"Education status: {circumstances.education_status}"
        if circumstances.education_details:
            text += f" — {circumstances.education_details}"
        add_fact(text, "education", ["education"])

    # Treatment / substance use
    if circumstances.treatment_history:
        add_fact(
            f"Treatment history: {circumstances.treatment_history}",
            "treatment",
            ["treatment_engagement"],
            sensitivity_tags=["substance_use", "medical"],
        )
    if circumstances.currently_in_treatment is True:
        add_fact(
            "Currently engaged in treatment",
            "treatment",
            ["treatment_engagement"],
            sensitivity_tags=["substance_use", "medical"],
        )
    if circumstances.substance_use_history:
        add_fact(
            f"Substance use history: {circumstances.substance_use_history}",
            "treatment",
            ["treatment_engagement"],
            sensitivity_tags=["substance_use", "medical"],
        )

    # Mental health
    if circumstances.mental_health_history:
        add_fact(
            f"Mental health history: {circumstances.mental_health_history}",
            "mental_health",
            ["treatment_engagement"],
            sensitivity_tags=["mental_health", "medical"],
        )

    # Military
    if circumstances.military_service is True:
        text = "Military service"
        if circumstances.military_details:
            text += f": {circumstances.military_details}"
        add_fact(text, "military", ["military_service"])

    # Community ties
    if circumstances.community_ties:
        add_fact(
            f"Community ties: {circumstances.community_ties}",
            "community",
            ["community_ties"],
        )
    if circumstances.character_references_available is True:
        add_fact(
            "Character references available",
            "community",
            ["community_ties"],
        )

    # Additional factors
    for factor in circumstances.additional_mitigating_factors:
        add_fact(factor, "other", ["insight_responsibility"])

    return facts


def _incorporate_structured_facts(
    structured_facts: list[SourceFact],
) -> list[dict[str, Any]]:
    """Convert upstream SourceFact objects into fact sheet entries."""
    return [
        {
            "fact_id": sf.fact_id,
            "text": sf.text,
            "source": sf.source_agent,
            "source_ref": sf.source_ref,
            "category": "upstream",
            "themes": [],
            "verification_status": sf.verification_status.value,
            "sensitivity_tags": sf.sensitivity_tags,
        }
        for sf in structured_facts
    ]


def build_mitigation_fact_sheet(
    input_data: SentencingAgentInput,
) -> MitigationFactSheet:
    """Build a structured mitigation fact sheet from input data."""
    all_facts: list[dict[str, Any]] = []

    # Extract from personal circumstances
    all_facts.extend(_extract_facts_from_circumstances(input_data.personal_circumstances))

    # Incorporate structured upstream facts
    all_facts.extend(
        _incorporate_structured_facts(input_data.personal_circumstances.structured_facts)
    )

    # Add criminal history context for "no prior record" theme
    if not input_data.criminal_history.has_prior_convictions:
        all_facts.append(
            {
                "fact_id": "auto-no-priors",
                "text": "No prior criminal convictions",
                "source": "criminal_history",
                "category": "record",
                "themes": ["low_public_safety_risk"],
                "verification_status": input_data.criminal_history.verification_status.value,
                "sensitivity_tags": [],
            }
        )

    # Collect all themes
    all_themes: set[str] = set()
    sensitive_categories: set[str] = set()
    for fact in all_facts:
        all_themes.update(fact.get("themes", []))
        sensitive_categories.update(fact.get("sensitivity_tags", []))

    return MitigationFactSheet(
        facts=all_facts,
        themes=sorted(all_themes),
        sensitive_categories=sorted(sensitive_categories),
        fact_count=len(all_facts),
    )


def mitigation_fact_sheet_node(state: SentencingGraphState) -> SentencingGraphState:
    """Mitigation fact sheet node — builds structured facts with provenance."""
    started_at = datetime.now(timezone.utc).isoformat()
    audit_records: list[NodeAuditRecord] = list(state.get("audit_records") or [])

    if state.get("scope_status") != "in_scope":
        audit_records.append(
            NodeAuditRecord(
                node_name="mitigation_fact_sheet",
                status="skipped",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                warnings=["Skipped: case is not in scope"],
                output_keys=[],
            )
        )
        state["audit_records"] = audit_records
        return state

    input_data = state["input"]
    fact_sheet = build_mitigation_fact_sheet(input_data)

    state["mitigation_fact_sheet"] = fact_sheet
    audit_records.append(
        NodeAuditRecord(
            node_name="mitigation_fact_sheet",
            status="ok",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            output_keys=["mitigation_fact_sheet"],
        )
    )
    state["audit_records"] = audit_records
    return state
