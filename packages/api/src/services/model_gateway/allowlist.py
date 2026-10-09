"""Model selection: the primary, the allowlist, and the per-run choice (§8).

A run may select a cheaper model to manage its own cost, but only from
``CLAUDE_MODELS_ALLOWED``. Anything else is rejected with a clear error, so runs stay
comparable and costs predictable. There are no automatic fallbacks (§0.3): the model
a call asks for is the model it gets, or the call fails.
"""

from __future__ import annotations

import contextlib
import contextvars
from collections.abc import Iterator

from src.config import settings
from src.services.model_gateway.errors import ModelNotAllowedError
from src.services.model_gateway.pricing import pricing_table

_run_model: contextvars.ContextVar[str | None] = contextvars.ContextVar("run_model", default=None)


def allowed_models() -> tuple[str, ...]:
    return tuple(settings.CLAUDE_MODELS_ALLOWED)


def validate_model(model: str) -> str:
    allowed = allowed_models()
    if model not in allowed:
        raise ModelNotAllowedError(
            f"Model {model!r} is not on the allowlist. Allowed: {', '.join(allowed)}. "
            "Set CLAUDE_MODELS_ALLOWED to change it."
        )
    return model


def resolve_model(requested: str | None = None) -> str:
    """The model a call will use: explicit request, else the run's, else the primary."""
    return validate_model(requested or _run_model.get() or settings.CLAUDE_MODEL_PRIMARY)


@contextlib.contextmanager
def use_model(model: str | None) -> Iterator[str]:
    """Run the enclosed calls (and tasks they spawn) on ``model``, validated."""
    resolved = resolve_model(model)
    token = _run_model.set(resolved)
    try:
        yield resolved
    finally:
        _run_model.reset(token)


def check_configuration() -> None:
    """Fail at startup on a primary outside the allowlist or an unpriced model."""
    validate_model(settings.CLAUDE_MODEL_PRIMARY)
    priced = pricing_table().models
    unpriced = [m for m in allowed_models() if m not in priced]
    if unpriced:
        raise ModelNotAllowedError(
            f"Allowlisted models without pricing: {', '.join(unpriced)}. "
            "Add them to services/model_gateway/pricing.json."
        )
