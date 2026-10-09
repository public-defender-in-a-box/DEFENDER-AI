import os


def _csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


class Settings:
    # Bring your own key (PHASE_1_MODEL_GATEWAY.md §8.1): read from the environment of
    # whoever runs the backend. Never committed, never configured in CI, never logged.
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")

    # Models (PHASE_1_MODEL_GATEWAY.md §8). A run uses CLAUDE_MODEL_PRIMARY unless it
    # selects another model from CLAUDE_MODELS_ALLOWED; anything else is rejected.
    CLAUDE_MODEL_PRIMARY: str = os.getenv("CLAUDE_MODEL_PRIMARY", "claude-opus-5-5")
    CLAUDE_MODELS_ALLOWED: tuple[str, ...] = _csv(
        os.getenv(
            "CLAUDE_MODELS_ALLOWED",
            "claude-opus-5-5,claude-sonnet-5-5,claude-haiku-5-5",
        )
    )

    # Gateway mode (PHASE_1_MODEL_GATEWAY.md §5.2): "live" for development and normal
    # use, "record" to write cassettes with your own key, "replay" for tests and CI.
    MODEL_GATEWAY_MODE: str = os.getenv("MODEL_GATEWAY_MODE", "live")
    MODEL_GATEWAY_MAX_RETRIES: int = int(os.getenv("MODEL_GATEWAY_MAX_RETRIES", "2"))
    MODEL_GATEWAY_TIMEOUT_S: float = float(os.getenv("MODEL_GATEWAY_TIMEOUT_S", "600"))
    # Empty = packages/api/tests/cassettes.
    MODEL_GATEWAY_CASSETTE_DIR: str = os.getenv("MODEL_GATEWAY_CASSETTE_DIR", "")

    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "./uploads")
    CONFIDENCE_THRESHOLD: float = 0.6  # Below this = LOW confidence, flagged
    DEFAULT_JURISDICTION: str = "GA"

    # CourtListener API — free, register at courtlistener.com. Same rules as the
    # Anthropic key: supplied by whoever runs the backend.
    COURTLISTENER_API_KEY: str = os.getenv("COURTLISTENER_API_KEY", "")

    # Research agent settings
    RESEARCH_MAX_QUERIES_PER_ISSUE: int = 5
    RESEARCH_MAX_CASES_PER_QUERY: int = 10
    RESEARCH_COST_BUDGET_USD: float = 1.00


settings = Settings()
