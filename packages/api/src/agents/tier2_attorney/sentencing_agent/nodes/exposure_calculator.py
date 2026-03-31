"""Node 2: Exposure Calculator — Deterministic sentencing exposure for GA misdemeanor.

No LLM calls. Calculates statutory range for simple marijuana possession <= 1 oz.
"""

from __future__ import annotations

from datetime import datetime, timezone

from ..models.inputs import OffenseDetails, PriorRecord
from ..models.outputs import GuidelineRange, NodeAuditRecord
from ..models.state import SentencingGraphState


def calculate_guideline_range(
    offense: OffenseDetails,
    history: PriorRecord,
    pretrial_custody_days: int,
) -> GuidelineRange:
    """Calculate the statutory sentencing exposure for GA marijuana misdemeanor."""
    return GuidelineRange(
        statutory_minimum=0,
        statutory_maximum=365,
        fine_minimum=0.0,
        fine_maximum=1000.0,
        has_mandatory_minimum=False,
        mandatory_minimum_days=None,
        probation_possible=True,
        suspended_sentence_possible=True,
        weekend_service_possible=True,
        weekend_service_threshold_days=180,
        time_served_credit_days=pretrial_custody_days,
        typical_range_description=(
            "Georgia misdemeanor sentencing is discretionary within the statutory "
            "range. No verified county-specific typical-sentence pattern is available "
            "in the current corpus."
        ),
        data_basis=[
            "O.C.G.A. § 16-13-2(b)",
            "O.C.G.A. § 17-10-3",
            "O.C.G.A. § 42-8-34",
        ],
        special_fees=[
            {
                "amount": 25.0,
                "basis": "O.C.G.A. § 42-8-34(d)(2)",
                "condition": "applies if probation or suspended sentence is imposed for § 16-13-2(b)",
            }
        ],
        notes=[
            "Weekend confinement is only available if the imposed sentence is six months or less.",
            "Probation or suspension remains discretionary.",
        ],
    )


def exposure_calculator(state: SentencingGraphState) -> SentencingGraphState:
    """Exposure calculator node — computes statutory sentencing range."""
    started_at = datetime.now(timezone.utc).isoformat()
    audit_records: list[NodeAuditRecord] = list(state.get("audit_records") or [])

    if state.get("scope_status") != "in_scope":
        audit_records.append(
            NodeAuditRecord(
                node_name="exposure_calculator",
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
    guideline_range = calculate_guideline_range(
        offense=input_data.offense_details,
        history=input_data.criminal_history,
        pretrial_custody_days=input_data.pretrial_custody_days,
    )

    state["guideline_range"] = guideline_range
    audit_records.append(
        NodeAuditRecord(
            node_name="exposure_calculator",
            status="ok",
            started_at=started_at,
            completed_at=datetime.now(timezone.utc).isoformat(),
            output_keys=["guideline_range"],
        )
    )
    state["audit_records"] = audit_records
    return state
