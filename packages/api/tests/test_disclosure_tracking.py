"""Tests for the Disclosure Tracking Agent.

Covers: model validation, agent output wrapping, confidence scoring,
checklist generation patterns, gap detection, and compliance report structure.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from src.agents.tier2_attorney.disclosure_tracking import DisclosureTrackingAgent
from src.models.case_state import ConfidenceLevel
from src.models.disclosure import (
    BradyComplianceReport,
    ChecklistItem,
    ChecklistItemStatus,
    DisclosureGap,
    DisclosureMaterialType,
    DisclosureTrackingOutput,
    DiscoveryLedgerEntry,
    DiscoveryRequest,
    DocumentCategory,
    GapSeverity,
    OfficerRecord,
    RequestStatus,
    TimelineEvent,
)

# ---------------------------------------------------------------------------
# Model validation tests
# ---------------------------------------------------------------------------


class TestDisclosureModels:
    """Validate Pydantic models serialize/deserialize correctly."""

    def test_discovery_ledger_entry(self) -> None:
        entry = DiscoveryLedgerEntry(
            id="DL-001",
            document_name="APD Arrest Report",
            category=DocumentCategory.POLICE_REPORT,
            source="Atlanta Police Department",
            received_date="2024-02-01",
            disclosure_types=[DisclosureMaterialType.BRADY],
            page_count=12,
            summary="Arrest report for Jan 15 incident",
            flags=["witness stated uncertainty on p.8"],
            confidence=0.85,
        )
        assert entry.id == "DL-001"
        assert entry.category == DocumentCategory.POLICE_REPORT
        assert DisclosureMaterialType.BRADY in entry.disclosure_types
        assert len(entry.flags) == 1

    def test_checklist_item(self) -> None:
        item = ChecklistItem(
            id="CK-001",
            description="Eyewitness identification procedures (photo arrays, lineups)",
            material_type=DisclosureMaterialType.BRADY,
            status=ChecklistItemStatus.PENDING,
            triggered_by="Eyewitness identification mentioned in arrest report",
        )
        assert item.status == ChecklistItemStatus.PENDING
        assert item.material_type == DisclosureMaterialType.BRADY

    def test_checklist_item_status_transitions(self) -> None:
        item = ChecklistItem(
            id="CK-002",
            description="Officer disciplinary records",
            material_type=DisclosureMaterialType.GIGLIO,
        )
        # Simulate status progression
        item.status = ChecklistItemStatus.REQUESTED
        assert item.status == ChecklistItemStatus.REQUESTED
        item.status = ChecklistItemStatus.RECEIVED
        assert item.status == ChecklistItemStatus.RECEIVED

    def test_disclosure_gap(self) -> None:
        gap = DisclosureGap(
            id="GAP-001",
            material_type=DisclosureMaterialType.GIGLIO,
            severity=GapSeverity.CRITICAL,
            description="No Giglio notice filed for witness with prior felony",
            expected_evidence="Giglio disclosure for prosecution witness John Smith",
            basis="Witness listed in complaint has prior drug conviction per GCIC",
            source_reference="Arrest report p.3, witness list",
            suggested_action="Send targeted Giglio demand letter",
            related_checklist_items=["CK-005"],
        )
        assert gap.severity == GapSeverity.CRITICAL
        assert gap.material_type == DisclosureMaterialType.GIGLIO

    def test_discovery_request(self) -> None:
        req = DiscoveryRequest(
            id="REQ-001",
            date_sent="2024-02-10",
            method="formal letter",
            items_requested=["Bodycam footage", "911 call recordings"],
            recipient="Fulton County DA's Office",
            status=RequestStatus.NO_RESPONSE,
            deadline="2024-02-20",
        )
        assert req.status == RequestStatus.NO_RESPONSE
        assert len(req.items_requested) == 2

    def test_timeline_event(self) -> None:
        event = TimelineEvent(
            date="2024-02-15",
            description="No response to bodycam request — 14 days elapsed",
            event_type="alert",
            is_alert=True,
            related_ids=["REQ-001"],
        )
        assert event.is_alert is True

    def test_officer_record(self) -> None:
        officer = OfficerRecord(
            name="Officer James Smith",
            badge_number="4521",
            agency="Atlanta Police Department",
            disciplinary_record_requested=False,
            disciplinary_record_status="not_requested",
            giglio_relevant=True,
        )
        assert officer.giglio_relevant is True

    def test_brady_compliance_report(self) -> None:
        report = BradyComplianceReport(
            case_id="test_001",
            generated_at=datetime.utcnow().isoformat(),
            total_items_tracked=15,
            items_received=10,
            items_outstanding=5,
            unresolved_gaps=["GAP-001", "GAP-003"],
            suggested_motions=["Motion to Compel"],
            compliance_assessment="Prosecution has disclosed most items but key gaps remain.",
            appellate_preservation_notes="Brady objection preserved at pretrial hearing.",
            attorney_action_items=["File Motion to Compel for bodycam footage"],
        )
        assert report.items_outstanding == 5
        assert len(report.unresolved_gaps) == 2

    def test_disclosure_tracking_output(self) -> None:
        output = DisclosureTrackingOutput(
            discovery_ledger=[
                DiscoveryLedgerEntry(
                    id="DL-001",
                    document_name="Arrest Report",
                    category=DocumentCategory.POLICE_REPORT,
                    source="APD",
                    received_date="2024-02-01",
                    confidence=0.9,
                )
            ],
            checklist=[
                ChecklistItem(
                    id="CK-001",
                    description="Officer disciplinary records",
                    material_type=DisclosureMaterialType.GIGLIO,
                )
            ],
            gaps=[],
            draft_demand_letter="DRAFT — ATTORNEY REVIEW REQUIRED\n\nDear Counsel...",
            client_summary="Your attorney is tracking all evidence in your case.",
        )
        assert len(output.discovery_ledger) == 1
        assert "ATTORNEY REVIEW REQUIRED" in output.draft_demand_letter

    def test_all_document_categories_valid(self) -> None:
        """Ensure all DocumentCategory enum values are accessible."""
        assert len(DocumentCategory) >= 20
        assert DocumentCategory.POLICE_REPORT.value == "POLICE_REPORT"
        assert DocumentCategory.INFORMANT_AGREEMENT.value == "INFORMANT_AGREEMENT"

    def test_all_gap_severities(self) -> None:
        for severity in GapSeverity:
            gap = DisclosureGap(
                id=f"GAP-{severity.value}",
                material_type=DisclosureMaterialType.BRADY,
                severity=severity,
                description=f"Test gap at {severity.value}",
                expected_evidence="test",
                basis="test",
            )
            assert gap.severity == severity


# ---------------------------------------------------------------------------
# Agent unit tests
# ---------------------------------------------------------------------------


class TestDisclosureTrackingAgent:
    """Test the agent's wrapping, confidence, and integration."""

    def test_agent_metadata(self) -> None:
        agent = DisclosureTrackingAgent()
        assert agent.agent_id == "disclosure_tracking"
        assert agent.agent_name == "Disclosure Tracking Agent"

    def test_confidence_no_documents(self) -> None:
        agent = DisclosureTrackingAgent()
        conf = agent._compute_confidence([], [], [])
        assert conf == 0.55  # base only

    def test_confidence_with_documents(self) -> None:
        agent = DisclosureTrackingAgent()
        docs = [{"id": f"doc-{i}"} for i in range(5)]
        checklist = [{"id": f"ck-{i}"} for i in range(10)]
        gaps = [{"id": "gap-1"}]
        conf = agent._compute_confidence(docs, checklist, gaps)
        # 0.55 base + 0.10 (5 docs) + 0.07 (10 items) + 0.05 (gaps found)
        assert conf == pytest.approx(0.77, abs=0.01)

    def test_confidence_many_documents(self) -> None:
        agent = DisclosureTrackingAgent()
        docs = [{"id": f"doc-{i}"} for i in range(15)]
        checklist = [{"id": f"ck-{i}"} for i in range(20)]
        gaps = [{"id": "gap-1"}]
        conf = agent._compute_confidence(docs, checklist, gaps)
        # 0.55 + 0.15 + 0.10 + 0.05 = 0.85 (capped)
        assert conf == pytest.approx(0.85, abs=0.01)

    def test_confidence_caps_at_085(self) -> None:
        agent = DisclosureTrackingAgent()
        docs = [{"id": f"doc-{i}"} for i in range(100)]
        checklist = [{"id": f"ck-{i}"} for i in range(100)]
        gaps = [{"id": f"gap-{i}"} for i in range(50)]
        conf = agent._compute_confidence(docs, checklist, gaps)
        assert conf <= 0.85

    def test_wrap_output(self) -> None:
        agent = DisclosureTrackingAgent()
        data = {"gaps": [], "checklist": []}
        wrapped = agent.wrap_output(data, confidence=0.7)
        assert wrapped["confidence"] == ConfidenceLevel.MEDIUM.value
        assert wrapped["source"] == "disclosure_tracking"
        assert "data" in wrapped
        assert "timestamp" in wrapped

    def test_audit_logging(self) -> None:
        agent = DisclosureTrackingAgent()
        agent.log_action("test_action", {"key": "value"})
        log = agent.get_audit_log()
        assert len(log) == 1
        assert log[0].action == "test_action"
        assert log[0].agent_id == "disclosure_tracking"

    @pytest.mark.asyncio
    async def test_run_returns_wrapped_output(self) -> None:
        """Test that run() returns a properly wrapped output dict."""
        agent = DisclosureTrackingAgent()

        # Mock all LLM calls to return valid structured data
        mock_classify = {
            "discovery_ledger": [
                {
                    "id": "DL-001",
                    "document_name": "Arrest Report",
                    "category": "POLICE_REPORT",
                    "source": "APD",
                    "received_date": "2024-02-01",
                    "disclosure_types": ["BRADY"],
                    "page_count": 12,
                    "summary": "Arrest report for cocaine possession",
                    "flags": ["witness uncertainty noted on p.8"],
                    "confidence": 0.85,
                }
            ],
            "exculpatory_highlights": ["Arrest report p.8: 'witness stated she was not certain'"],
        }

        mock_checklist = [
            {
                "id": "CK-001",
                "description": "Officer disciplinary records for Officer Smith #4521",
                "material_type": "GIGLIO",
                "status": "PENDING",
                "triggered_by": "Officer Smith listed as arresting officer",
                "related_ledger_entries": [],
                "notes": "",
            },
            {
                "id": "CK-002",
                "description": "Field test kit calibration records",
                "material_type": "BRADY",
                "status": "PENDING",
                "triggered_by": "Field test used to confirm cocaine",
                "related_ledger_entries": [],
                "notes": "",
            },
        ]

        mock_gaps = {
            "gaps": [
                {
                    "id": "GAP-001",
                    "material_type": "GIGLIO",
                    "severity": "HIGH",
                    "description": "No officer disciplinary records disclosed",
                    "expected_evidence": "Disciplinary file for Officer Smith #4521",
                    "basis": "Giglio v. United States requires disclosure",
                    "source_reference": "Officer roster",
                    "suggested_action": "Send Giglio demand letter",
                    "related_checklist_items": ["CK-001"],
                }
            ],
            "officer_records": [
                {
                    "name": "Officer James Smith",
                    "badge_number": "4521",
                    "agency": "Atlanta Police Department",
                    "disciplinary_record_requested": False,
                    "disciplinary_record_status": "not_requested",
                    "prior_case_flags": [],
                    "giglio_relevant": True,
                }
            ],
        }

        mock_compliance = {
            "discovery_requests": [],
            "timeline": [
                {
                    "date": "2024-01-20",
                    "description": "Arraignment",
                    "event_type": "arraignment",
                    "is_alert": False,
                    "related_ids": [],
                }
            ],
            "compliance_report": {
                "case_id": "test_001",
                "generated_at": "2024-03-01T00:00:00",
                "total_items_tracked": 2,
                "items_received": 1,
                "items_outstanding": 1,
                "unresolved_gaps": ["GAP-001"],
                "suggested_motions": ["Motion to Compel"],
                "compliance_assessment": "Key Giglio gaps remain.",
                "appellate_preservation_notes": "Brady objection preserved.",
                "attorney_action_items": ["Request officer disciplinary records"],
            },
            "client_summary": (
                "Your attorney has received the arrest report but is still "
                "waiting for important records about the arresting officer."
            ),
        }

        mock_drafts = {
            "draft_demand_letter": "Dear Counsel,\n\nPursuant to Brady v. Maryland...",
            "draft_motion_to_compel": "IN THE STATE COURT OF FULTON COUNTY...",
        }

        with patch("src.agents.tier2_attorney.disclosure_tracking.call_llm") as mock_llm:
            mock_llm.side_effect = [
                mock_classify,
                mock_checklist,
                mock_gaps,
                mock_compliance,
                mock_drafts,
            ]

            result = await agent.run(
                {
                    "case_id": "test_001",
                    "discovery_documents": [{"id": "doc-1", "name": "Arrest Report"}],
                    "charges": "Possession of cocaine, O.C.G.A. § 16-13-30(a)",
                    "case_type": "drug_possession",
                    "intake_facts": "Client denies knowledge of substance",
                    "officer_roster": [{"name": "Officer James Smith", "badge": "4521"}],
                    "jurisdiction": "GA",
                    "case_timeline": {"arraignment": "2024-01-20"},
                    "prior_requests": [],
                }
            )

        # Verify wrapped structure
        assert "data" in result
        assert "confidence" in result
        assert "source" in result
        assert result["source"] == "disclosure_tracking"
        assert result["confidence"] in ("HIGH", "MEDIUM", "LOW")

        data = result["data"]

        # Verify all output sections present
        assert "discovery_ledger" in data
        assert "checklist" in data
        assert "gaps" in data
        assert "timeline" in data
        assert "officer_records" in data
        assert "compliance_report" in data
        assert "draft_demand_letter" in data
        assert "draft_motion_to_compel" in data
        assert "client_summary" in data
        assert "exculpatory_highlights" in data

        # Verify DRAFT headers
        assert data["draft_demand_letter"].startswith("DRAFT — ATTORNEY REVIEW REQUIRED")
        assert data["draft_motion_to_compel"].startswith("DRAFT — ATTORNEY REVIEW REQUIRED")

        # Verify content
        assert len(data["discovery_ledger"]) == 1
        assert len(data["gaps"]) == 1
        assert data["gaps"][0]["material_type"] == "GIGLIO"
        assert len(data["exculpatory_highlights"]) == 1
        assert "witness stated she was not certain" in data["exculpatory_highlights"][0]

    @pytest.mark.asyncio
    async def test_run_with_empty_inputs(self) -> None:
        """Agent should handle empty/minimal inputs gracefully."""
        agent = DisclosureTrackingAgent()

        with patch("src.agents.tier2_attorney.disclosure_tracking.call_llm") as mock_llm:
            mock_llm.side_effect = [
                {"discovery_ledger": [], "exculpatory_highlights": []},
                [],  # empty checklist
                {"gaps": [], "officer_records": []},
                {
                    "discovery_requests": [],
                    "timeline": [],
                    "compliance_report": {
                        "case_id": "",
                        "generated_at": "2024-03-01T00:00:00",
                        "total_items_tracked": 0,
                        "items_received": 0,
                        "items_outstanding": 0,
                        "unresolved_gaps": [],
                        "suggested_motions": [],
                        "compliance_assessment": "No discovery documents to analyze.",
                        "appellate_preservation_notes": "",
                        "attorney_action_items": [],
                    },
                    "client_summary": "No discovery documents have been received yet.",
                },
                {"draft_demand_letter": "", "draft_motion_to_compel": ""},
            ]

            result = await agent.run({"case_id": "empty_case"})

        assert result["confidence"] == ConfidenceLevel.LOW.value
        assert result["data"]["discovery_ledger"] == []


# ---------------------------------------------------------------------------
# Orchestrator integration tests
# ---------------------------------------------------------------------------


class TestOrchestratorIntegration:
    """Verify disclosure_tracking is properly registered in the orchestrator."""

    def test_agent_config_registered(self) -> None:
        from src.agents.tier0.orchestrator import _AGENT_CONFIG

        assert "disclosure_tracking" in _AGENT_CONFIG
        config = _AGENT_CONFIG["disclosure_tracking"]
        assert config["state_field"] == "disclosure_tracking"
        assert config["is_client_facing"] is False

    def test_case_state_has_disclosure_field(self) -> None:
        from src.models.case_state import CaseState

        state = CaseState(id="test", attorney_id="atty_001")
        assert hasattr(state, "disclosure_tracking")
        assert state.disclosure_tracking is None

    @pytest.mark.asyncio
    async def test_orchestrator_can_merge_disclosure_output(self) -> None:
        """Test that the orchestrator accepts disclosure tracking output."""
        from src.models.case_state import PipelineStage
        from src.agents.tier0.orchestrator import OrchestratorAgent

        orchestrator = OrchestratorAgent()
        await orchestrator.run(
            {
                "case_id": "test_merge",
                "attorney_id": "atty_001",
                "jurisdiction": "GA",
            }
        )

        # Advance through pipeline to required stage
        orchestrator._case_state.advance_stage(PipelineStage.CHARGES_PROCESSING)
        orchestrator._case_state.advance_stage(PipelineStage.CHARGES_PROCESSED)
        orchestrator._case_state.advance_stage(PipelineStage.PRE_INTERVIEW_RESEARCH)
        orchestrator._case_state.advance_stage(PipelineStage.PRE_INTERVIEW_COMPLETE)
        orchestrator._case_state.advance_stage(PipelineStage.INTAKE_IN_PROGRESS)
        orchestrator._case_state.advance_stage(PipelineStage.INTAKE_COMPLETE)

        # Verify agent can run
        can_run, reason = orchestrator.can_run_agent("disclosure_tracking")
        assert can_run, f"Should be able to run disclosure_tracking: {reason}"

        # Submit output
        mock_output = {
            "data": {
                "discovery_ledger": [],
                "checklist": [],
                "gaps": [],
                "compliance_report": {"case_id": "test_merge"},
                "draft_demand_letter": "DRAFT — ATTORNEY REVIEW REQUIRED\n\nDear Counsel...",
            },
            "confidence": "MEDIUM",
            "source": "disclosure_tracking",
            "timestamp": "2024-03-01T00:00:00",
        }

        result = await orchestrator.receive_agent_output("disclosure_tracking", mock_output)
        assert result["decision"] in ("MERGED", "MERGED_WITH_FLAG")
        assert orchestrator._case_state.disclosure_tracking is not None
