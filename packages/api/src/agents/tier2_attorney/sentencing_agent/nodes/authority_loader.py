"""Node 1: Verified Authority Loader — Loads verified statute data for downstream nodes.

Deterministic retrieval from local seed data. No LLM calls.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..config import STATUTES_PATH
from ..models.outputs import NodeAuditRecord
from ..models.state import SentencingGraphState

# Statutes needed for the MVP
MVP_STATUTES = [
    "O.C.G.A. § 16-13-30(j)(1)",
    "O.C.G.A. § 16-13-2(a)",
    "O.C.G.A. § 16-13-2(b)",
    "O.C.G.A. § 17-10-3",
    "O.C.G.A. § 42-8-34",
    "O.C.G.A. § 15-18-80 et seq.",
    "O.C.G.A. § 15-1-15",
    "O.C.G.A. § 15-1-17",
    "O.C.G.A. § 15-1-18",
    "O.C.G.A. § 35-3-37",
]


def load_statutes() -> dict[str, Any]:
    """Load the Georgia statutes seed data."""
    with open(STATUTES_PATH) as f:
        return json.load(f)


def build_authority_bundle(all_statutes: dict[str, Any]) -> dict[str, Any]:
    """Build a compact authority bundle containing only MVP-relevant statutes."""
    bundle: dict[str, Any] = {}
    missing: list[str] = []

    for citation in MVP_STATUTES:
        if citation in all_statutes:
            bundle[citation] = all_statutes[citation]
        else:
            missing.append(citation)

    return {
        "statutes": bundle,
        "missing_statutes": missing,
        "loaded_count": len(bundle),
        "expected_count": len(MVP_STATUTES),
    }


def authority_loader(state: SentencingGraphState) -> SentencingGraphState:
    """Authority loader node — loads verified statute data into state."""
    started_at = datetime.now(timezone.utc).isoformat()
    warnings: list[str] = list(state.get("warnings") or [])
    audit_records: list[NodeAuditRecord] = list(state.get("audit_records") or [])

    # Skip if out of scope
    if state.get("scope_status") != "in_scope":
        audit_records.append(
            NodeAuditRecord(
                node_name="authority_loader",
                status="skipped",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                warnings=["Skipped: case is not in scope"],
                output_keys=[],
            )
        )
        state["audit_records"] = audit_records
        return state

    try:
        all_statutes = load_statutes()
        bundle = build_authority_bundle(all_statutes)

        if bundle["missing_statutes"]:
            warnings.append(
                f"Missing statutes from corpus: {', '.join(bundle['missing_statutes'])}"
            )

        state["authority_bundle"] = bundle
        state["warnings"] = warnings
        audit_records.append(
            NodeAuditRecord(
                node_name="authority_loader",
                status="ok" if not bundle["missing_statutes"] else "warning",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                warnings=warnings,
                output_keys=["authority_bundle"],
            )
        )
    except Exception as e:
        warnings.append(f"Authority loader error: {e}")
        state["authority_bundle"] = {
            "statutes": {},
            "missing_statutes": MVP_STATUTES,
            "loaded_count": 0,
            "expected_count": len(MVP_STATUTES),
        }
        state["warnings"] = warnings
        audit_records.append(
            NodeAuditRecord(
                node_name="authority_loader",
                status="error",
                started_at=started_at,
                completed_at=datetime.now(timezone.utc).isoformat(),
                warnings=[str(e)],
                output_keys=["authority_bundle"],
            )
        )

    state["audit_records"] = audit_records
    return state
