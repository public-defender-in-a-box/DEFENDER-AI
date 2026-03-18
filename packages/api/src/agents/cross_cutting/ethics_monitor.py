"""Ethics & Compliance Monitor — Cross-Cutting Guardrail.

Runs across all tiers and all agents. Enforces legal, ethical, and
constitutional boundaries. Cannot be overridden by any other agent.
"""

import uuid
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.case_state import ConfidenceLevel
from src.models.ethics import EthicalFlag


# Confidence threshold — outputs below this are flagged
CONFIDENCE_THRESHOLD = 0.6

# UPL keywords that should never appear in client-facing outputs
UPL_VIOLATION_PHRASES = [
    "you should plead",
    "i recommend",
    "i advise",
    "my legal opinion",
    "you must",
    "you need to",
    "the best option is",
    "you should take the deal",
]


class EthicsMonitorAgent(BaseAgent):
    agent_id = "ethics_monitor"
    agent_name = "Ethics & Compliance Monitor"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Validate agent output against ethical and legal standards.

        Input: agent output to validate, agent_id, is_client_facing
        Output: ethical flags, blocked status, audit entries
        """
        self.log_action(
            "ethics_check_started",
            {
                "target_agent": input_data.get("agent_id"),
            },
        )

        flags: list[dict[str, Any]] = []
        output = input_data.get("output", {})
        agent_id = input_data.get("agent_id", "unknown")
        is_client_facing = input_data.get("is_client_facing", False)

        # Check 1: Confidence threshold
        confidence = output.get("confidence", "UNRATED")
        if confidence == ConfidenceLevel.LOW.value:
            flags.append(
                self._create_flag(
                    agent_id,
                    "COMPETENCE",
                    "MEDIUM",
                    f"Agent {agent_id} output has LOW confidence. Flagged for attorney review.",
                    blocked=False,
                )
            )

        # Check 2: UPL violations in client-facing outputs
        if is_client_facing:
            content = str(output.get("data", "")).lower()
            for phrase in UPL_VIOLATION_PHRASES:
                if phrase in content:
                    flags.append(
                        self._create_flag(
                            agent_id,
                            "UPL",
                            "CRITICAL",
                            f"Potential UPL violation: client-facing output contains '{phrase}'",
                            blocked=True,
                        )
                    )

        # Check 3: Privilege warning present
        if not is_client_facing:
            data_str = str(output.get("data", ""))
            if "DRAFT" in data_str and "ATTORNEY REVIEW REQUIRED" not in data_str:
                flags.append(
                    self._create_flag(
                        agent_id,
                        "PRIVILEGE",
                        "LOW",
                        "Draft output missing ATTORNEY REVIEW REQUIRED disclaimer.",
                        blocked=False,
                    )
                )

        # Check 4: Decision support disclaimer on plea/trial outputs
        if agent_id == "plea_trial_analyst":
            recommendation = str(output.get("data", {}).get("recommendation", ""))
            if recommendation and "DECISION SUPPORT ONLY" not in recommendation:
                flags.append(
                    self._create_flag(
                        agent_id,
                        "IAC",
                        "HIGH",
                        "Plea/trial recommendation missing DECISION SUPPORT ONLY disclaimer.",
                        blocked=True,
                    )
                )

        blocked = any(f["blocked"] for f in flags)

        self.log_action(
            "ethics_check_completed",
            {
                "flags_count": len(flags),
                "blocked": blocked,
            },
        )

        return {
            "flags": flags,
            "blocked": blocked,
            "audit_entries": [e.model_dump(mode="json") for e in self.get_audit_log()],
        }

    def _create_flag(
        self,
        agent_source: str,
        category: str,
        priority: str,
        description: str,
        blocked: bool,
    ) -> dict[str, Any]:
        return EthicalFlag(
            id=str(uuid.uuid4()),
            agent_source=agent_source,
            category=category,
            priority=priority,
            description=description,
            blocked=blocked,
        ).model_dump(mode="json")
