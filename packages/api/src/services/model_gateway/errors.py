"""Failure taxonomy for model calls (PHASE_1_MODEL_GATEWAY.md §3.1).

Every failure of a model call raises one of these. Agent code must never catch
``ModelCallError`` and return a valid-looking output: a failure propagates to
``Orchestrator.handle_agent_failure``, which records it as ``FAILED`` with the error
type. An abstention ("the record does not address this") is not an error; it is a
valid response with ``abstained=True``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.services.model_gateway.types import ModelCallRecord


class ModelCallError(Exception):
    """Base. Never caught by a bare ``except Exception`` in agent code."""

    def __init__(self, message: str, *, record: ModelCallRecord | None = None) -> None:
        super().__init__(message)
        # The accounting record for the failed call, when one exists (a call that never
        # reached the API, such as a missing key, has none).
        self.record = record

    @property
    def error_type(self) -> str:
        return type(self).__name__


class TransportError(ModelCallError):
    """Network failure, timeout, rate limit, or 5xx, after the configured retries."""


class AuthError(ModelCallError):
    """401/403 from the API, or no API key in a mode that needs one. Never retried."""


class InvalidRequestError(ModelCallError):
    """The API rejected the request itself (400, 404, 413, 422).

    Not in the spec's original taxonomy: a request the API refuses to accept, such
    as an unsupported schema or an unknown model, is neither a transport failure nor
    a malformed response, and folding it into either would misreport it.
    """


class ModelNotAllowedError(ModelCallError):
    """The requested model is not on CLAUDE_MODELS_ALLOWED (§8). Raised before any call."""


class RefusalError(ModelCallError):
    """``stop_reason == "refusal"``."""


class TruncatedResponseError(ModelCallError):
    """``stop_reason == "max_tokens"``. Raise ``max_tokens`` at the call site."""


class MalformedResponseError(ModelCallError):
    """The response has no text block, or its text is not parseable JSON."""


class SchemaMismatchError(ModelCallError):
    """The response parsed as JSON but failed ``response_model`` validation."""


class CassetteMissError(ModelCallError):
    """Replay mode found no recording for this request (§5.2). Never falls through."""
