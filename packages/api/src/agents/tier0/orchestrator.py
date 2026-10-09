"""Case Orchestrator — Tier 0 Master Agent.

The Orchestrator is an active state manager, not a passive router. It:
- Owns the single CaseState object
- Enforces sequencing (agents cannot run until dependencies complete)
- Flags LOW-confidence outputs for attorney review (merged, never withheld)
- Runs the Ethics Monitor on every output as a sensor, not a filter: a CRITICAL
  flag is merged with the output and recorded as ``would_have_blocked``
  (CLAUDE.md §3.1, PHASE_1_MODEL_GATEWAY.md §4)
- Exposes pipeline status for the frontend
- Records agent failures with their error type
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from src.agents.base_agent import BaseAgent
from src.agents.cross_cutting.ethics_monitor import EthicsMonitorAgent
from src.models.case_state import CaseState, ConfidenceLevel, PipelineStage
from src.services import measurements
from src.services.model_gateway import ModelCallError

STATUS = "REAL"

logger = logging.getLogger(__name__)

# Confidence threshold — outputs below this are LOW: merged and flagged for review
_CONFIDENCE_THRESHOLD = 0.6


class MergeDecision(str, Enum):
    """Result of the Orchestrator's merge evaluation."""

    MERGED = "MERGED"
    BLOCKED_LOW_CONFIDENCE = "BLOCKED_LOW_CONFIDENCE"
    MERGED_WITH_FLAG = "MERGED_WITH_FLAG"
    # A CRITICAL ethics flag: merged, carrying the flag. Replaces BLOCKED_ETHICS_P1,
    # which no stored record references (there is no persistence before Phase 2a).
    MERGED_WITH_CRITICAL_FLAG = "MERGED_WITH_CRITICAL_FLAG"
    FAILED = "FAILED"


class PipelineStatus:
    """Snapshot of where a case is in the pipeline."""

    def __init__(
        self,
        case_id: str,
        current_stage: PipelineStage,
        completed_stages: list[str],
        blocked: bool,
        blocked_reason: str | None,
        human_review_required: bool,
        ethical_flags: list[dict[str, Any]],
        error: str | None,
    ) -> None:
        self.case_id = case_id
        self.current_stage = current_stage
        self.completed_stages = completed_stages
        self.blocked = blocked
        self.blocked_reason = blocked_reason
        self.human_review_required = human_review_required
        self.ethical_flags = ethical_flags
        self.error = error

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "current_stage": self.current_stage.value,
            "completed_stages": self.completed_stages,
            "blocked": self.blocked,
            "blocked_reason": self.blocked_reason,
            "human_review_required": self.human_review_required,
            "ethical_flags_count": len(self.ethical_flags),
            "error": self.error,
        }


# Map of which CaseState field each agent writes to,
# and which stage it transitions through
_AGENT_CONFIG: dict[str, dict[str, Any]] = {
    "charge_processing": {
        "state_field": "charge_processing",
        "start_stage": PipelineStage.CHARGES_PROCESSING,
        "complete_stage": PipelineStage.CHARGES_PROCESSED,
        "is_client_facing": False,
        "required_stage": PipelineStage.CREATED,
    },
    "pre_interview_research": {
        "state_field": "pre_interview_research",
        "start_stage": PipelineStage.PRE_INTERVIEW_RESEARCH,
        "complete_stage": PipelineStage.PRE_INTERVIEW_COMPLETE,
        "is_client_facing": False,
        "required_stage": PipelineStage.CHARGES_PROCESSED,
    },
    "intake_conductor": {
        "state_field": "intake_summary",
        "start_stage": PipelineStage.INTAKE_IN_PROGRESS,
        "complete_stage": PipelineStage.INTAKE_COMPLETE,
        "is_client_facing": True,
        "required_stage": PipelineStage.PRE_INTERVIEW_COMPLETE,
    },
    "case_prep": {
        "state_field": "case_prep_memo",
        "start_stage": PipelineStage.CASE_PREP_IN_PROGRESS,
        "complete_stage": PipelineStage.CASE_PREP_COMPLETE,
        "is_client_facing": False,
        "required_stage": PipelineStage.INTAKE_COMPLETE,
    },
    # Alias: CasePrepAgent.agent_id is "case_prep_conductor" (see tier1/case_prep.py).
    # Keep both keys pointing at the same config so callers using either id work.
    "case_prep_conductor": {
        "state_field": "case_prep_memo",
        "start_stage": PipelineStage.CASE_PREP_IN_PROGRESS,
        "complete_stage": PipelineStage.CASE_PREP_COMPLETE,
        "is_client_facing": False,
        "required_stage": PipelineStage.INTAKE_COMPLETE,
    },
    "disclosure_tracking": {
        "state_field": "disclosure_tracking",
        "start_stage": PipelineStage.CASE_PREP_IN_PROGRESS,
        "complete_stage": PipelineStage.CASE_PREP_COMPLETE,
        "is_client_facing": False,
        "required_stage": PipelineStage.INTAKE_COMPLETE,
    },
    # Research agents — run after pre-interview produces charges + rights flags
    "research_orchestrator": {
        "state_field": "combined_research",
        "start_stage": PipelineStage.LEGAL_RESEARCH_IN_PROGRESS,
        "complete_stage": PipelineStage.LEGAL_RESEARCH_COMPLETE,
        "is_client_facing": False,
        "required_stage": PipelineStage.PRE_INTERVIEW_COMPLETE,
    },
    "ga_criminal_case_law": {
        "state_field": "case_law_research",
        "start_stage": PipelineStage.LEGAL_RESEARCH_IN_PROGRESS,
        "complete_stage": PipelineStage.LEGAL_RESEARCH_IN_PROGRESS,
        "is_client_facing": False,
        "required_stage": PipelineStage.PRE_INTERVIEW_COMPLETE,
    },
    "constitutional_case_law": {
        "state_field": "constitutional_research",
        "start_stage": PipelineStage.LEGAL_RESEARCH_IN_PROGRESS,
        "complete_stage": PipelineStage.LEGAL_RESEARCH_IN_PROGRESS,
        "is_client_facing": False,
        "required_stage": PipelineStage.PRE_INTERVIEW_COMPLETE,
    },
    "ga_statutes_agent": {
        "state_field": "statute_analysis",
        "start_stage": PipelineStage.LEGAL_RESEARCH_IN_PROGRESS,
        "complete_stage": PipelineStage.LEGAL_RESEARCH_IN_PROGRESS,
        "is_client_facing": False,
        "required_stage": PipelineStage.PRE_INTERVIEW_COMPLETE,
    },
    "citation_verification": {
        "state_field": "citation_verification",
        "start_stage": PipelineStage.LEGAL_RESEARCH_IN_PROGRESS,
        "complete_stage": PipelineStage.LEGAL_RESEARCH_COMPLETE,
        "is_client_facing": False,
        "required_stage": PipelineStage.PRE_INTERVIEW_COMPLETE,
    },
}


class OrchestratorAgent(BaseAgent):
    agent_id = "orchestrator"
    agent_name = "Case Orchestrator"

    def __init__(self) -> None:
        super().__init__()
        self._case_state: CaseState | None = None
        self._ethics_monitor = EthicsMonitorAgent()
        self._blocked = False
        self._blocked_reason: str | None = None
        self._human_review_required = False
        self._merge_history: list[dict[str, Any]] = []
        # The allowlisted model this case's runs use (PHASE_1_MODEL_GATEWAY.md §8); None
        # means the primary. Lives on the object like _blocked until Phase 2a persists it.
        self.run_model: str | None = None

    @property
    def case_state(self) -> CaseState | None:
        return self._case_state

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Initialize a new case and return the initial CaseState.

        Input keys:
            case_id: str
            attorney_id: str
            jurisdiction: str (default GA)
            attorney_config: dict
            documents: list[dict] — uploaded document records

        Output: initialized CaseState as dict
        """
        self.log_action("case_initialized", {"input_keys": list(input_data.keys())})

        case_id = input_data.get("case_id", str(uuid.uuid4()))
        self._case_state = CaseState(
            id=case_id,
            attorney_id=input_data.get("attorney_id", ""),
            jurisdiction=input_data.get("jurisdiction", "GA"),
            attorney_config=input_data.get("attorney_config", {}),
        )
        self._case_state.advance_stage(PipelineStage.CREATED)

        # Attach documents if provided
        documents = input_data.get("documents", [])
        for doc in documents:
            from src.models.case_state import DocumentRecord

            self._case_state.documents.append(
                DocumentRecord(
                    id=doc.get("id", str(uuid.uuid4())),
                    type=doc.get("type", "UNKNOWN"),
                    file_name=doc.get("file_name", ""),
                    storage_url=doc.get("storage_url", ""),
                    uploaded_at=datetime.now(timezone.utc),
                )
            )

        return self._case_state.model_dump(mode="json")

    def can_run_agent(self, agent_id: str) -> tuple[bool, str]:
        """Check if an agent is allowed to run given current pipeline state.

        Returns (allowed, reason).
        """
        if self._case_state is None:
            return False, "No case initialized"

        config = _AGENT_CONFIG.get(agent_id)
        if config is None:
            return False, f"Unknown agent: {agent_id}"

        required = config["required_stage"]
        # Allow if we're at or past the required stage
        required_index = list(PipelineStage).index(required)
        current_index = list(PipelineStage).index(self._case_state.stage)

        if current_index < required_index:
            return False, (
                f"Agent {agent_id} requires stage {required.value} but "
                f"current stage is {self._case_state.stage.value}"
            )

        # Check if already completed (field populated)
        field = config["state_field"]
        if getattr(self._case_state, field) is not None:
            return False, f"Agent {agent_id} output already exists in CaseState"

        return True, "OK"

    def mark_agent_started(self, agent_id: str) -> None:
        """Advance CaseState to the agent's start stage."""
        if self._case_state is None:
            return
        config = _AGENT_CONFIG.get(agent_id)
        if config:
            self._case_state.advance_stage(config["start_stage"])
            self.log_action("agent_started", {"agent_id": agent_id})

    async def receive_agent_output(
        self,
        agent_id: str,
        output: dict[str, Any],
    ) -> dict[str, Any]:
        """Validate, ethics-check, and merge an agent's output into CaseState.

        This is the core Orchestrator logic. No agent writes to CaseState
        directly — they return outputs here.

        Returns a merge result dict with decision, flags, and status.
        """
        if self._case_state is None:
            return {"decision": MergeDecision.FAILED.value, "reason": "No case initialized"}

        config = _AGENT_CONFIG.get(agent_id)
        if config is None:
            return {"decision": MergeDecision.FAILED.value, "reason": f"Unknown agent: {agent_id}"}

        self.log_action("output_received", {"agent_id": agent_id})
        now = datetime.now(timezone.utc)

        # Step 1: Confidence. LOW is flagged for attorney review, never withheld, and
        # no longer exempt from the ethics check below.
        confidence_str = output.get("confidence", "UNRATED")
        low_confidence = self._parse_confidence(confidence_str) == ConfidenceLevel.LOW
        if low_confidence:
            self.log_action(
                "output_low_confidence_flagged",
                {"agent_id": agent_id, "confidence": confidence_str},
            )
            self._human_review_required = True
            if output.get("data"):
                output["data"]["_low_confidence_flag"] = True
                output["data"]["_review_required"] = True

        # Step 2: Ethics Sensor — every output is inspected.
        ethics_result = await self._ethics_monitor.run(
            {
                "output": output,
                "agent_id": agent_id,
                "is_client_facing": config["is_client_facing"],
            }
        )
        ethics_flags = ethics_result.get("flags", [])
        p1_flags = [f for f in ethics_flags if f.get("priority") == "CRITICAL"]
        p2_flags = [f for f in ethics_flags if f.get("priority") == "HIGH"]
        p3_flags = [f for f in ethics_flags if f.get("priority") in ("MEDIUM", "LOW")]
        # What a deployable product would have done. Recorded, not acted on: a
        # suppressed output cannot be studied (CLAUDE.md §3).
        would_have_blocked = bool(p1_flags) or bool(ethics_result.get("blocked", False))

        # Step 3: Merge, always.
        if would_have_blocked:
            decision = MergeDecision.MERGED_WITH_CRITICAL_FLAG
        elif p2_flags or low_confidence:
            decision = MergeDecision.MERGED_WITH_FLAG
        else:
            decision = MergeDecision.MERGED
        if decision != MergeDecision.MERGED:
            self._human_review_required = True

        field = config["state_field"]
        setattr(self._case_state, field, output)
        self._case_state.advance_stage(config["complete_stage"])

        self._case_state.ethical_flags.extend(
            {**f, "merge_decision": MergeDecision.MERGED_WITH_CRITICAL_FLAG.value} for f in p1_flags
        )
        self._case_state.ethical_flags.extend(
            {**f, "merge_decision": MergeDecision.MERGED_WITH_FLAG.value} for f in p2_flags
        )
        self._case_state.ethical_flags.extend({**f, "merge_decision": "LOGGED"} for f in p3_flags)

        self._case_state.audit_log.append(
            {
                "id": str(uuid.uuid4()),
                "timestamp": now.isoformat(),
                "agent_id": agent_id,
                "action": "output_merged",
                "decision": decision.value,
                "confidence": confidence_str,
                "ethics_flags_count": len(ethics_flags),
                "would_have_blocked": would_have_blocked,
            }
        )
        self._case_state.updated_at = now
        self._merge_history.append(
            {
                "agent_id": agent_id,
                "decision": decision.value,
                "confidence": confidence_str,
                "ethics_flags": len(ethics_flags),
                "critical_flags": len(p1_flags),
                "would_have_blocked": would_have_blocked,
                "timestamp": now.isoformat(),
            }
        )
        measurements.record(
            measurements.Measurement(
                kind=measurements.MeasurementKind.MERGE_DECISION,
                agent_id=agent_id,
                case_id=self._case_state.id,
                payload={
                    "decision": decision.value,
                    "confidence": str(confidence_str),
                    "low_confidence": low_confidence,
                    "ethics_flags": len(ethics_flags),
                    "critical_flags": len(p1_flags),
                    "would_have_blocked": would_have_blocked,
                },
            )
        )
        self.log_action(
            "output_merged",
            {
                "agent_id": agent_id,
                "decision": decision.value,
                "would_have_blocked": would_have_blocked,
                "stage": self._case_state.stage.value,
            },
        )

        result: dict[str, Any] = {
            "decision": decision.value,
            "stage": self._case_state.stage.value,
            "flags": ethics_flags,
            "human_review_required": self._human_review_required,
            "would_have_blocked": would_have_blocked,
        }
        if low_confidence:
            result["reason"] = (
                f"Agent {agent_id} returned LOW confidence ({confidence_str}). "
                "Output merged but flagged for attorney review."
            )
        elif would_have_blocked:
            description = p1_flags[0].get("description", "") if p1_flags else ""
            result["reason"] = f"CRITICAL ethics flag (merged, recorded): {description}"
        return result

    async def handle_agent_failure(
        self,
        agent_id: str,
        error: str | BaseException,
    ) -> dict[str, Any]:
        """Record a failed agent run as FAILED, with its error type, and surface it.

        Pass the exception itself where there is one: its type is the measurement
        (an AuthError and a CassetteMissError are different findings), and a
        ``ModelCallError`` carries the accounting record of the call that failed.
        """
        error_type = type(error).__name__ if isinstance(error, BaseException) else "Unspecified"
        message = str(error)
        call_record = (
            error.record.model_dump(mode="json")
            if isinstance(error, ModelCallError) and error.record is not None
            else None
        )
        self.log_action(
            "agent_failed", {"agent_id": agent_id, "error_type": error_type, "error": message}
        )

        if self._case_state is not None:
            self._case_state.audit_log.append(
                {
                    "id": str(uuid.uuid4()),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "agent_id": agent_id,
                    "action": "agent_failed",
                    "decision": MergeDecision.FAILED.value,
                    "error_type": error_type,
                    "error": message,
                }
            )
        measurements.record(
            measurements.Measurement(
                kind=measurements.MeasurementKind.AGENT_FAILURE,
                agent_id=agent_id,
                case_id=self._case_state.id if self._case_state else None,
                payload={"error_type": error_type, "error": message, "model_call": call_record},
            )
        )

        self._blocked = True
        self._blocked_reason = f"Agent {agent_id} failed ({error_type}): {message}"

        return {
            "status": "FAILED",
            "decision": MergeDecision.FAILED.value,
            "agent_id": agent_id,
            "error_type": error_type,
            "error": message,
            "case_state_preserved": self._case_state is not None,
            "current_stage": (self._case_state.stage.value if self._case_state else "NONE"),
        }

    def get_status(self) -> PipelineStatus:
        """Return current pipeline status for the frontend."""
        if self._case_state is None:
            return PipelineStatus(
                case_id="",
                current_stage=PipelineStage.CREATED,
                completed_stages=[],
                blocked=False,
                blocked_reason=None,
                human_review_required=False,
                ethical_flags=[],
                error=None,
            )

        completed = [
            entry.stage.value
            for entry in self._case_state.stage_history
            if entry.exited_at is not None
        ]

        return PipelineStatus(
            case_id=self._case_state.id,
            current_stage=self._case_state.stage,
            completed_stages=completed,
            blocked=self._blocked,
            blocked_reason=self._blocked_reason,
            human_review_required=self._human_review_required,
            ethical_flags=self._case_state.ethical_flags,
            error=None,
        )

    def get_case_state_snapshot(self) -> dict[str, Any]:
        """Return the current CaseState as a dict (for persistence or API)."""
        if self._case_state is None:
            return {}
        return self._case_state.model_dump(mode="json")

    def get_merge_history(self) -> list[dict[str, Any]]:
        """Return the history of merge decisions."""
        return self._merge_history

    def _parse_confidence(self, confidence: str | Any) -> ConfidenceLevel:
        """Parse a confidence string or value into a ConfidenceLevel."""
        if isinstance(confidence, ConfidenceLevel):
            return confidence

        confidence_str = str(confidence).upper()

        try:
            return ConfidenceLevel(confidence_str)
        except ValueError:
            pass

        # Try numeric
        try:
            value = float(confidence)
            if value >= 0.85:
                return ConfidenceLevel.HIGH
            elif value >= _CONFIDENCE_THRESHOLD:
                return ConfidenceLevel.MEDIUM
            else:
                return ConfidenceLevel.LOW
        except (ValueError, TypeError):
            return ConfidenceLevel.UNRATED
