"""BaseAgent adapter for the Sentencing & Mitigation Agent.

Wraps the LangGraph pipeline so the Orchestrator can invoke this agent
the same way it invokes the Motion Drafter and Plea/Trial Analyst.
"""

from __future__ import annotations

import logging
from typing import Any

from src.agents.base_agent import BaseAgent

from .graph import run_sentencing_analysis
from .models.inputs import SentencingAgentInput

logger = logging.getLogger(__name__)


class SentencingAgent(BaseAgent):
    """BaseAgent wrapper around the LangGraph sentencing pipeline."""

    agent_id = "sentencing_agent"
    agent_name = "Sentencing & Mitigation Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Run the sentencing analysis pipeline.

        Accepts raw CaseState dict, maps it to SentencingAgentInput,
        runs the LangGraph pipeline, and returns wrapped output.
        """
        case_id = input_data.get("case_id") or input_data.get("id", "unknown")
        self.log_action("sentencing_analysis_started", {"case_id": case_id})

        try:
            agent_input = self._map_case_state_to_input(input_data)
            output = await run_sentencing_analysis(agent_input)
            output_dict = output.model_dump()

            confidence = output.confidence_score
            self.log_action("sentencing_analysis_completed", {
                "case_id": case_id,
                "scope_status": output.scope_status,
                "confidence": confidence,
            })

            return self.wrap_output(output_dict, confidence=confidence)

        except Exception:
            logger.error("Sentencing analysis failed for case %s", case_id)
            self.log_action("sentencing_analysis_error", {"case_id": case_id})
            return self.wrap_output(
                {"error": "Sentencing analysis failed", "case_id": case_id},
                confidence=0.0,
            )

    def _map_case_state_to_input(self, input_data: dict[str, Any]) -> SentencingAgentInput:
        """Map CaseState dict fields to SentencingAgentInput.

        This is the bridge between the Orchestrator's CaseState format
        and the sentencing agent's typed input model.
        """
        # Try direct construction first (if Orchestrator passes pre-mapped data)
        try:
            return SentencingAgentInput(**input_data)
        except Exception:
            pass

        # Fallback: map from CaseState conventions
        from .models.inputs import (
            CasePhase,
            JurisdictionContext,
            OffenseDetails,
            PersonalCircumstances,
            PriorRecord,
        )

        charges = input_data.get("charges", [])
        first_charge = charges[0] if charges else {}
        intake = input_data.get("intake_summary") or input_data.get("intake", {})
        personal = intake.get("personal_circumstances", {})

        return SentencingAgentInput(
            case_id=input_data.get("case_id") or input_data.get("id", "unknown"),
            case_phase=CasePhase.PRETRIAL,
            jurisdiction_context=JurisdictionContext(
                county=input_data.get("county", "Clarke"),
            ),
            offense_details=OffenseDetails(
                statute=first_charge.get("statute_section") or first_charge.get("statute", ""),
                charge_description=first_charge.get("offense_title") or first_charge.get("description", ""),
                enhancements=first_charge.get("enhancements", []),
            ),
            criminal_history=PriorRecord(
                has_prior_convictions=bool(
                    personal.get("prior_record_self_report", "").lower()
                    not in ("no prior", "none", "")
                ),
            ),
            personal_circumstances=PersonalCircumstances(
                employment_status=personal.get("employment_status"),
                housing_stable=personal.get("housing_status") is not None,
            ),
        )
