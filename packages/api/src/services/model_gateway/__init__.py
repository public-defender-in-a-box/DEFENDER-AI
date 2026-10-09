"""The model gateway (PHASE_1_MODEL_GATEWAY.md). Import from here, not the submodules."""

from src.services.model_gateway.allowlist import (
    allowed_models,
    check_configuration,
    resolve_model,
    use_model,
    validate_model,
)
from src.services.model_gateway.cassettes import using_fixtures
from src.services.model_gateway.errors import (
    AuthError,
    CassetteMissError,
    InvalidRequestError,
    MalformedResponseError,
    ModelCallError,
    ModelNotAllowedError,
    RefusalError,
    SchemaMismatchError,
    TransportError,
    TruncatedResponseError,
)
from src.services.model_gateway.gateway import call_model, current_mode, require_api_key
from src.services.model_gateway.types import (
    AbstainableResponse,
    Effort,
    GatewayResponse,
    ModelCallRecord,
    ModelCallRequest,
    ModelCallResult,
)

__all__ = [
    "AbstainableResponse",
    "AuthError",
    "CassetteMissError",
    "Effort",
    "GatewayResponse",
    "InvalidRequestError",
    "MalformedResponseError",
    "ModelCallError",
    "ModelCallRecord",
    "ModelCallRequest",
    "ModelCallResult",
    "ModelNotAllowedError",
    "RefusalError",
    "SchemaMismatchError",
    "TransportError",
    "TruncatedResponseError",
    "allowed_models",
    "call_model",
    "check_configuration",
    "current_mode",
    "require_api_key",
    "resolve_model",
    "use_model",
    "using_fixtures",
    "validate_model",
]
