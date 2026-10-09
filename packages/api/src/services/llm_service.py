"""Deprecated: use ``src.services.model_gateway.call_model``.

``call_llm`` survives only while call sites migrate (PHASE_1_MODEL_GATEWAY.md §9). It
is a thin wrapper over the gateway, so unmigrated agents already get thinking-block
parsing, ``stop_reason`` checks, typed errors, cassettes, and accounting — but their
replies are untyped and their prompts unversioned.
"""

from __future__ import annotations

import sys
import warnings
from typing import ClassVar

from pydantic import JsonValue, RootModel

from src.services.model_gateway import ModelCallRequest, call_model

_DEFAULT_SYSTEM = (
    "You are a legal analysis AI assistant for a public defender's office."
    " Always return valid JSON."
)
# Thinking tokens count toward max_tokens on current models; the old 4096 default
# would truncate. Unmigrated callers get at least this much.
_MIN_MAX_TOKENS = 16000


class UntypedJSON(RootModel[JsonValue]):
    """Passthrough response model: any JSON. Not constrained by structured outputs."""

    gateway_structured_output: ClassVar[bool] = False


async def call_llm(
    prompt: str,
    system: str = _DEFAULT_SYSTEM,
    max_tokens: int = 4096,
) -> JsonValue:
    """Deprecated untyped call. Raises ``ModelCallError`` subclasses on failure."""
    warnings.warn(
        "call_llm is deprecated; migrate to model_gateway.call_model with a response model",
        DeprecationWarning,
        stacklevel=2,
    )
    caller = sys._getframe(1).f_globals.get("__name__", "unknown")
    agent_id = str(caller).rsplit(".", 1)[-1]
    result = await call_model(
        ModelCallRequest(
            prompt=prompt,
            system=system,
            max_tokens=max(max_tokens, _MIN_MAX_TOKENS),
            response_model=UntypedJSON,
            prompt_id=f"{agent_id}.unversioned",
            prompt_version="unversioned",
            agent_id=agent_id,
        )
    )
    return result.data.root
