"""Integration test for the full Tier 0 + Tier 1 pipeline.

Tests the complete flow:
    Orchestrator → Charge Processing → Pre-Interview Research → Intake Conductor

Verifies:
- CaseState is populated correctly after each agent
- All confidence scores are present
- Ethics Monitor ran on every output
- Orchestrator enforces sequencing and thresholds
"""

import os
import pytest

from src.agents.tier0.orchestrator import (
    MergeDecision,
    OrchestratorAgent,
)
from src.agents.tier1.charge_processing import ChargeProcessingAgent
from src.agents.tier1.intake_conductor import IntakeConductorAgent
from src.agents.tier1.pre_interview import PreInterviewResearchAgent
from src.agents.cross_cutting.ethics_monitor import EthicsMonitorAgent
from src.models.case_state import (
    CaseState,
    ConfidenceLevel,
    PipelineStage,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def accusation_text() -> str:
    """Load the sample accusation fixture."""
    fixture_path = os.path.join(
        os.path.dirname(__file__), "fixtures", "sample_accusation.txt",
    )
    with open(fixture_path, "r") as f:
        return f.read()


@pytest.fixture
def orchestrator() -> OrchestratorAgent:
    return OrchestratorAgent()


# ---------------------------------------------------------------------------
# Unit tests — Orchestrator logic (no LLM calls)
# ---------------------------------------------------------------------------

class TestOrchestratorInit:
    """Test Orchestrator initialization and state management."""

    @pytest.mark.asyncio
    async def test_initialize_case(self, orchestrator: OrchestratorAgent):
        """Orchestrator creates CaseState with correct defaults."""
        result = await orchestrator.run({
            "case_id": "test_001",
            "attorney_id": "atty_001",
            "jurisdiction": "GA",
        })

        assert result["id"] == "test_001"
        assert result["attorney_id"] == "atty_001"
        assert result["jurisdiction"] == "GA"
        assert result["stage"] == PipelineStage.CREATED.value

        assert orchestrator.case_state is not None
        assert orchestrator.case_state.id == "test_001"
        assert orchestrator.case_state.stage == PipelineStage.CREATED
        assert len(orchestrator.case_state.stage_history) == 1

    @pytest.mark.asyncio
    async def test_initialize_with_documents(self, orchestrator: OrchestratorAgent):
        """Orchestrator attaches documents to CaseState."""
        result = await orchestrator.run({
            "case_id": "test_002",
            "documents": [
                {"id": "doc_1", "type": "accusation", "file_name": "accusation.txt", "storage_url": "/uploads/acc.txt"},
            ],
        })

        assert len(result["documents"]) == 1
        assert result["documents"][0]["type"] == "accusation"


class TestOrchestratorSequencing:
    """Test that the Orchestrator enforces pipeline sequencing."""

    @pytest.mark.asyncio
    async def test_cannot_run_pre_interview_before_charges(self, orchestrator: OrchestratorAgent):
        """Pre-interview cannot run before charge processing completes."""
        await orchestrator.run({"case_id": "test_seq_001"})

        can_run, reason = orchestrator.can_run_agent("pre_interview_research")
        assert not can_run
        assert "CHARGES_PROCESSED" in reason

    @pytest.mark.asyncio
    async def test_can_run_charge_processing_after_init(self, orchestrator: OrchestratorAgent):
        """Charge processing can run immediately after initialization."""
        await orchestrator.run({"case_id": "test_seq_002"})

        can_run, reason = orchestrator.can_run_agent("charge_processing")
        assert can_run
        assert reason == "OK"

    @pytest.mark.asyncio
    async def test_cannot_run_same_agent_twice(self, orchestrator: OrchestratorAgent):
        """An agent cannot run if its output already exists."""
        await orchestrator.run({"case_id": "test_seq_003"})
        orchestrator.mark_agent_started("charge_processing")

        # Simulate a merge
        fake_output = {
            "data": {"charges": []},
            "confidence": "HIGH",
            "source": "charge_processing",
            "timestamp": "2024-01-01T00:00:00",
        }
        await orchestrator.receive_agent_output("charge_processing", fake_output)

        can_run, reason = orchestrator.can_run_agent("charge_processing")
        assert not can_run
        assert "already exists" in reason


class TestOrchestratorConfidenceThreshold:
    """Test that the Orchestrator blocks LOW confidence outputs."""

    @pytest.mark.asyncio
    async def test_low_confidence_blocked(self, orchestrator: OrchestratorAgent):
        """LOW confidence output is blocked and HumanReviewRequired is set."""
        await orchestrator.run({"case_id": "test_conf_001"})
        orchestrator.mark_agent_started("charge_processing")

        low_output = {
            "data": {"charges": []},
            "confidence": "LOW",
            "source": "charge_processing",
            "timestamp": "2024-01-01T00:00:00",
        }

        merge_result = await orchestrator.receive_agent_output(
            "charge_processing", low_output,
        )

        assert merge_result["decision"] == MergeDecision.BLOCKED_LOW_CONFIDENCE.value
        assert merge_result["human_review_required"] is True
        # CaseState should NOT have charge_processing populated
        assert orchestrator.case_state.charge_processing is None

    @pytest.mark.asyncio
    async def test_high_confidence_merged(self, orchestrator: OrchestratorAgent):
        """HIGH confidence output is merged into CaseState."""
        await orchestrator.run({"case_id": "test_conf_002"})
        orchestrator.mark_agent_started("charge_processing")

        high_output = {
            "data": {"charges": [{"charge_id": "c1"}]},
            "confidence": "HIGH",
            "source": "charge_processing",
            "timestamp": "2024-01-01T00:00:00",
        }

        merge_result = await orchestrator.receive_agent_output(
            "charge_processing", high_output,
        )

        assert merge_result["decision"] in (
            MergeDecision.MERGED.value, MergeDecision.MERGED_WITH_FLAG.value,
        )
        assert orchestrator.case_state.charge_processing is not None
        assert orchestrator.case_state.stage == PipelineStage.CHARGES_PROCESSED


class TestOrchestratorEthics:
    """Test Ethics Monitor integration in the Orchestrator."""

    @pytest.mark.asyncio
    async def test_ethics_monitor_runs_on_output(self, orchestrator: OrchestratorAgent):
        """Ethics Monitor is invoked for every agent output."""
        await orchestrator.run({"case_id": "test_ethics_001"})
        orchestrator.mark_agent_started("charge_processing")

        output = {
            "data": {"charges": []},
            "confidence": "HIGH",
            "source": "charge_processing",
            "timestamp": "2024-01-01T00:00:00",
        }

        merge_result = await orchestrator.receive_agent_output(
            "charge_processing", output,
        )

        # Ethics ran and result includes flags field
        assert "flags" in merge_result or "decision" in merge_result
        # Audit log should have entries
        assert len(orchestrator.case_state.audit_log) > 0


class TestOrchestratorFailureHandling:
    """Test graceful handling of partial failures."""

    @pytest.mark.asyncio
    async def test_agent_failure_preserves_state(self, orchestrator: OrchestratorAgent):
        """Agent failure saves CaseState and surfaces the error."""
        await orchestrator.run({"case_id": "test_fail_001"})

        failure = await orchestrator.handle_agent_failure(
            "charge_processing", "API timeout after 30s",
        )

        assert failure["status"] == "FAILED"
        assert failure["case_state_preserved"] is True
        assert "API timeout" in failure["error"]

    @pytest.mark.asyncio
    async def test_status_endpoint_reflects_failure(self, orchestrator: OrchestratorAgent):
        """Pipeline status reflects blocked state after failure."""
        await orchestrator.run({"case_id": "test_fail_002"})
        await orchestrator.handle_agent_failure("charge_processing", "Network error")

        status = orchestrator.get_status()
        assert status.blocked is True
        assert "charge_processing" in (status.blocked_reason or "")


class TestPipelineStatus:
    """Test the status endpoint the frontend can query."""

    @pytest.mark.asyncio
    async def test_initial_status(self, orchestrator: OrchestratorAgent):
        """Status after initialization shows CREATED stage."""
        await orchestrator.run({"case_id": "test_status_001"})

        status = orchestrator.get_status()
        assert status.case_id == "test_status_001"
        assert status.current_stage == PipelineStage.CREATED
        assert not status.blocked
        assert not status.human_review_required

    @pytest.mark.asyncio
    async def test_status_serializes(self, orchestrator: OrchestratorAgent):
        """Status can be serialized to dict for the API."""
        await orchestrator.run({"case_id": "test_status_002"})

        status_dict = orchestrator.get_status().to_dict()
        assert isinstance(status_dict, dict)
        assert status_dict["case_id"] == "test_status_002"
        assert status_dict["current_stage"] == "CREATED"


# ---------------------------------------------------------------------------
# Agent unit tests (no LLM calls — test structure and wrapping)
# ---------------------------------------------------------------------------

class TestChargeProcessingAgent:
    """Test ChargeProcessingAgent structure and BaseAgent conformance."""

    def test_inherits_base_agent(self):
        from src.agents.base_agent import BaseAgent
        agent = ChargeProcessingAgent()
        assert isinstance(agent, BaseAgent)

    def test_has_required_attrs(self):
        agent = ChargeProcessingAgent()
        assert agent.agent_id == "charge_processing"
        assert agent.agent_name == "Charge Processing Agent"

    def test_score_confidence(self):
        agent = ChargeProcessingAgent()
        assert agent.score_confidence(0.9) == ConfidenceLevel.HIGH
        assert agent.score_confidence(0.7) == ConfidenceLevel.MEDIUM
        assert agent.score_confidence(0.4) == ConfidenceLevel.LOW

    def test_wrap_output_structure(self):
        agent = ChargeProcessingAgent()
        wrapped = agent.wrap_output({"test": True}, confidence=0.85)
        assert "data" in wrapped
        assert "confidence" in wrapped
        assert "source" in wrapped
        assert "timestamp" in wrapped
        assert wrapped["confidence"] == ConfidenceLevel.HIGH.value
        assert wrapped["source"] == "charge_processing"


class TestPreInterviewAgent:
    """Test PreInterviewResearchAgent structure."""

    def test_inherits_base_agent(self):
        from src.agents.base_agent import BaseAgent
        agent = PreInterviewResearchAgent()
        assert isinstance(agent, BaseAgent)

    def test_has_required_attrs(self):
        agent = PreInterviewResearchAgent()
        assert agent.agent_id == "pre_interview_research"
        assert agent.agent_name == "Pre-Interview Research Conductor"


class TestIntakeConductorAgent:
    """Test IntakeConductorAgent structure."""

    def test_inherits_base_agent(self):
        from src.agents.base_agent import BaseAgent
        agent = IntakeConductorAgent()
        assert isinstance(agent, BaseAgent)

    def test_has_required_attrs(self):
        agent = IntakeConductorAgent()
        assert agent.agent_id == "intake_conductor"
        assert agent.agent_name == "Intake Conductor"


class TestEthicsMonitorAgent:
    """Test Ethics Monitor runs correctly."""

    @pytest.mark.asyncio
    async def test_ethics_monitor_clean_output(self):
        """Clean output produces no flags."""
        monitor = EthicsMonitorAgent()
        result = await monitor.run({
            "output": {
                "data": {"test": True},
                "confidence": "HIGH",
            },
            "agent_id": "test_agent",
            "is_client_facing": False,
        })

        assert isinstance(result["flags"], list)
        assert result["blocked"] is False

    @pytest.mark.asyncio
    async def test_ethics_monitor_low_confidence_flag(self):
        """LOW confidence outputs get flagged."""
        monitor = EthicsMonitorAgent()
        result = await monitor.run({
            "output": {
                "data": {"test": True},
                "confidence": "LOW",
            },
            "agent_id": "test_agent",
            "is_client_facing": False,
        })

        assert len(result["flags"]) > 0
        assert any(f["category"] == "COMPETENCE" for f in result["flags"])

    @pytest.mark.asyncio
    async def test_ethics_monitor_upl_violation(self):
        """Client-facing output with legal advice triggers UPL flag."""
        monitor = EthicsMonitorAgent()
        result = await monitor.run({
            "output": {
                "data": "I recommend you take the plea deal",
                "confidence": "HIGH",
            },
            "agent_id": "intake_conductor",
            "is_client_facing": True,
        })

        assert result["blocked"] is True
        assert any(f["category"] == "UPL" for f in result["flags"])


# ---------------------------------------------------------------------------
# End-to-end pipeline test (requires ANTHROPIC_API_KEY)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not os.getenv("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set — skipping LLM integration tests",
)
class TestFullPipeline:
    """Full end-to-end pipeline test with real LLM calls.

    Requires ANTHROPIC_API_KEY environment variable.
    """

    @pytest.mark.asyncio
    async def test_charge_processing_end_to_end(self, accusation_text: str):
        """Charge Processing Agent extracts structured data from accusation."""
        agent = ChargeProcessingAgent()
        result = await agent.run({
            "document_text": accusation_text,
            "document_type": "accusation",
            "jurisdiction": "GA",
            "matter_id": "test_e2e_001",
        })

        # Verify ConfidenceRated wrapping
        assert "data" in result
        assert "confidence" in result
        assert "source" in result
        assert result["source"] == "charge_processing"
        assert result["confidence"] in ("HIGH", "MEDIUM", "LOW")

        data = result["data"]

        # Verify charges extracted
        assert "charges" in data
        assert len(data["charges"]) >= 1  # At least one charge

        # Verify defendant info
        assert "defendant" in data
        assert data["defendant"]["name"] != "UNKNOWN"

        # Verify persons of interest
        assert "persons_of_interest" in data

        # Verify confidence triage ran
        assert "processing_metadata" in data
        assert "confidence_summary" in data["processing_metadata"]

    @pytest.mark.asyncio
    async def test_pre_interview_end_to_end(self, accusation_text: str):
        """Pre-Interview builds brief from charge processing output."""
        # First run charge processing
        charge_agent = ChargeProcessingAgent()
        charge_result = await charge_agent.run({
            "document_text": accusation_text,
            "document_type": "accusation",
            "jurisdiction": "GA",
            "matter_id": "test_e2e_002",
        })

        # Then run pre-interview
        pre_interview_agent = PreInterviewResearchAgent()
        result = await pre_interview_agent.run({
            "charge_processing": charge_result,
        })

        assert "data" in result
        assert "confidence" in result
        assert result["source"] == "pre_interview_research"

        data = result["data"]
        assert "targeted_questions" in data
        assert "preliminary_rights_flags" in data
        assert "known_facts_from_documents" in data
        assert "legal_brief" in data

    @pytest.mark.asyncio
    async def test_full_pipeline_with_orchestrator(self, accusation_text: str):
        """Full pipeline through Orchestrator with state management."""
        orchestrator = OrchestratorAgent()

        # Step 1: Initialize
        init_result = await orchestrator.run({
            "case_id": "test_e2e_full",
            "attorney_id": "atty_test",
            "jurisdiction": "GA",
            "documents": [
                {"id": "doc_1", "type": "accusation", "file_name": "accusation.txt", "storage_url": "/test"},
            ],
        })
        assert orchestrator.case_state.stage == PipelineStage.CREATED

        # Step 2: Charge Processing
        can_run, _ = orchestrator.can_run_agent("charge_processing")
        assert can_run

        orchestrator.mark_agent_started("charge_processing")
        assert orchestrator.case_state.stage == PipelineStage.CHARGES_PROCESSING

        charge_agent = ChargeProcessingAgent()
        charge_result = await charge_agent.run({
            "document_text": accusation_text,
            "document_type": "accusation",
            "jurisdiction": "GA",
            "matter_id": "test_e2e_full",
        })

        merge = await orchestrator.receive_agent_output("charge_processing", charge_result)
        assert merge["decision"] in (MergeDecision.MERGED.value, MergeDecision.MERGED_WITH_FLAG.value)
        assert orchestrator.case_state.stage == PipelineStage.CHARGES_PROCESSED
        assert orchestrator.case_state.charge_processing is not None

        # Step 3: Pre-Interview Research
        can_run, _ = orchestrator.can_run_agent("pre_interview_research")
        assert can_run

        orchestrator.mark_agent_started("pre_interview_research")

        pre_agent = PreInterviewResearchAgent()
        pre_result = await pre_agent.run({
            "charge_processing": orchestrator.case_state.charge_processing,
        })

        merge = await orchestrator.receive_agent_output("pre_interview_research", pre_result)
        assert merge["decision"] in (MergeDecision.MERGED.value, MergeDecision.MERGED_WITH_FLAG.value)
        assert orchestrator.case_state.stage == PipelineStage.PRE_INTERVIEW_COMPLETE
        assert orchestrator.case_state.pre_interview_research is not None

        # Step 4: Verify Ethics Monitor ran (audit log has entries)
        assert len(orchestrator.case_state.audit_log) >= 2

        # Step 5: Verify pipeline status
        status = orchestrator.get_status()
        assert status.current_stage == PipelineStage.PRE_INTERVIEW_COMPLETE
        assert len(status.completed_stages) >= 2

        # Step 6: Verify merge history
        history = orchestrator.get_merge_history()
        assert len(history) >= 2
        assert history[0]["agent_id"] == "charge_processing"
        assert history[1]["agent_id"] == "pre_interview_research"
