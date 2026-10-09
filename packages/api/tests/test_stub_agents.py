"""The five stub agents: the naive single-prompt baseline (PHASE_1_MODEL_GATEWAY.md §9.5).

Each still declares STATUS = "STUB"; each now calls the gateway with a typed response
model and a versioned prompt, so its output is labeled, accounted, and replayable.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from src.agents.tier1.case_prep import CasePrepAgent
from src.agents.tier2_attorney.brady_agent import BradyComplianceAgent
from src.agents.tier2_research.case_law_agent import CaseLawAgent
from src.agents.tier2_research.citation_verifier import CitationVerifierAgent
from src.agents.tier2_research.statute_agent import StatuteAgent
from src.services.model_gateway import TransportError
from src.services.model_gateway.testing import FakeCallModel

CASES: list[tuple[type, str, dict[str, Any], dict[str, Any], str]] = [
    (
        CasePrepAgent,
        "src.agents.tier1.case_prep",
        {"case_state": {"id": "SYN-STUB-001"}},
        {
            "case_theory": "Unlawful stop",
            "preparation_memo": "Memo text.",
            "decision_points": [
                {
                    "id": "DP-1",
                    "description": "File suppression motion?",
                    "options": ["File", "Do not file"],
                    "recommendation": "Attorney judgment required",
                    "human_required": True,
                }
            ],
            "attorney_task_list": [
                {
                    "id": "T-1",
                    "task": "Request bodycam",
                    "priority": "URGENT",
                    "deadline": None,
                    "category": "discovery",
                }
            ],
        },
        "case_theory",
    ),
    (
        BradyComplianceAgent,
        "src.agents.tier2_attorney.brady_agent",
        {"discovery": "Arrest report only", "officer_roster": ["Officer Synthetic"]},
        {
            "gaps": [
                {
                    "id": "G-1",
                    "category": "MISSING_REPORT",
                    "description": "No supplemental report",
                    "expected_evidence": "Supplemental report",
                    "basis": "Arrest report references one",
                }
            ],
            "giglio_checklist": [
                {
                    "officer": "Officer Synthetic",
                    "disciplinary_record_requested": False,
                    "status": "",
                }
            ],
            "draft_demand_letter": "Dear Counsel, ...",
        },
        "gaps",
    ),
    (
        CaseLawAgent,
        "src.agents.tier2_research.case_law_agent",
        {"legal_issues": ["reasonable suspicion"]},
        {"authorities": [], "circuit_splits": [], "recommended_citations": []},
        "authorities",
    ),
    (
        CitationVerifierAgent,
        "src.agents.tier2_research.citation_verifier",
        {"citations": ["392 U.S. 1"]},
        {
            "verified_citations": [
                {
                    "citation": "392 U.S. 1",
                    "status": "UNCONFIRMED",
                    "shepard_signal": "",
                    "notes": "Model knowledge only",
                }
            ],
            "statute_alerts": [],
        },
        "verified_citations",
    ),
    (
        StatuteAgent,
        "src.agents.tier2_research.statute_agent",
        {"charges": ["O.C.G.A. § 16-13-30"]},
        {"statutes": [], "procedural_statutes": [], "enhancement_statutes": []},
        "statutes",
    ),
]


@pytest.mark.parametrize("agent_cls,module,input_data,payload,key", CASES)
async def test_stub_golden_output(
    agent_cls: type, module: str, input_data: dict, payload: dict, key: str
) -> None:
    fake = FakeCallModel(payload)
    with patch(f"{module}.call_model", new=fake):
        result = await agent_cls().run(input_data)
    assert result["agent_status"] == "STUB"
    assert result["data"][key] == payload[key]
    (req,) = fake.requests
    assert req.agent_id == agent_cls.agent_id
    assert req.prompt_version.startswith("json_assistant.v1+")


@pytest.mark.parametrize("agent_cls,module,input_data,payload,key", CASES)
async def test_stub_failure_raises(
    agent_cls: type, module: str, input_data: dict, payload: dict, key: str
) -> None:
    with patch(f"{module}.call_model", new=FakeCallModel(TransportError("down"))):
        with pytest.raises(TransportError):
            await agent_cls().run(input_data)
