"""GA Criminal Statutes Agent — Tier 2 Research.

Retrieves and analyzes the full statutory framework relevant to the charges:
charged statutes, elements, penalties, lesser included offenses, diversion
eligibility, and procedural requirements.
"""

from __future__ import annotations

import json
import logging
from typing import Any, cast

from pydantic import BaseModel

from src.agents.base_agent import BaseAgent
from src.models.responses.research import (
    DiversionAnalysis,
    ProceduralAnalysis,
    StatutoryAnalysis,
)
from src.prompts import Prompt, compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "REAL"

logger = logging.getLogger(__name__)

# Prompts: src/prompts/ga_statutes_agent/
_SYSTEM = load_prompt("ga_statutes_agent.system", "v1")
_STATUTORY_ANALYSIS = load_prompt("ga_statutes_agent.statutory_analysis", "v1")
_DIVERSION_ANALYSIS = load_prompt("ga_statutes_agent.diversion_analysis", "v1")
_PROCEDURAL = load_prompt("ga_statutes_agent.procedural", "v1")

# Thinking tokens count toward max_tokens on current models (Phase 1 §2).
_MAX_TOKENS = 12000


class GAStatutesAgent(BaseAgent):
    """Retrieves and analyzes the full statutory framework for charged offenses."""

    agent_id = "ga_statutes_agent"
    agent_name = "GA Criminal Statutes Agent"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Analyze all relevant statutes for the case.

        Input keys:
            charges: list of parsed charge dicts (from Charge Processing)
            enhancements: list of enhancement flag dicts
            defendant_info: dict with any known defendant background

        Output: GAStatutesOutput as dict
        """
        self.log_action("statutes_analysis_started")

        charges = input_data.get("charges", [])
        enhancements = input_data.get("enhancements", [])
        defendant_info = input_data.get("defendant_info", {})

        charges_json = json.dumps(charges, default=str)
        enhancements_json = json.dumps(enhancements, default=str)
        defendant_json = json.dumps(defendant_info, default=str)

        # Run all three analyses (statutory, diversion, procedural)
        # These are independent LLM calls — run sequentially to manage cost
        charged_offenses = await self._analyze_statutes(
            charges_json, enhancements_json, defendant_json
        )
        diversion_options = await self._analyze_diversion(charges_json, defendant_json)
        procedural_data = await self._analyze_procedural(charges_json)

        output = {
            "charged_offenses": charged_offenses,
            "diversion_options": diversion_options,
            "procedural_requirements": procedural_data.get("procedural_requirements", []),
            "recent_amendments": procedural_data.get("recent_amendments", []),
        }

        self.log_action(
            "statutes_analysis_completed",
            {
                "offenses_analyzed": len(charged_offenses),
                "diversion_options": len(diversion_options),
            },
        )

        # Confidence: LLM-based statutory knowledge is reliable for well-known
        # GA statutes but should still be verified
        confidence = 0.7

        return self.wrap_output(output, confidence=confidence)

    def _request(
        self, prompt: str, template: Prompt, response_model: type[BaseModel]
    ) -> ModelCallRequest[BaseModel]:
        return ModelCallRequest(
            prompt=prompt,
            system=_SYSTEM.text,
            max_tokens=_MAX_TOKENS,
            response_model=response_model,
            prompt_id=template.id,
            prompt_version=compose_version(_SYSTEM, template),
            agent_id=self.agent_id,
        )

    async def _analyze_statutes(
        self,
        charges_json: str,
        enhancements_json: str,
        defendant_json: str,
    ) -> list[dict[str, Any]]:
        """Get full statutory analysis of each charged offense. Raises on failure."""
        prompt = _STATUTORY_ANALYSIS.text.format(
            charges=charges_json,
            enhancements=enhancements_json,
            defendant_info=defendant_json,
        )
        result = await call_model(self._request(prompt, _STATUTORY_ANALYSIS, StatutoryAnalysis))
        return cast(StatutoryAnalysis, result.data).model_dump()["charged_offenses"]

    async def _analyze_diversion(
        self,
        charges_json: str,
        defendant_json: str,
    ) -> list[dict[str, Any]]:
        """Analyze diversion and alternative sentencing eligibility. Raises on failure."""
        prompt = _DIVERSION_ANALYSIS.text.format(
            charges=charges_json, defendant_info=defendant_json
        )
        result = await call_model(self._request(prompt, _DIVERSION_ANALYSIS, DiversionAnalysis))
        return cast(DiversionAnalysis, result.data).model_dump()["diversion_options"]

    async def _analyze_procedural(
        self,
        charges_json: str,
    ) -> dict[str, Any]:
        """Identify procedural requirements and deadlines. Raises on failure."""
        prompt = _PROCEDURAL.text.format(charges=charges_json)
        result = await call_model(self._request(prompt, _PROCEDURAL, ProceduralAnalysis))
        return result.data.model_dump()
