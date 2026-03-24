import os


class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "./uploads")
    CONFIDENCE_THRESHOLD: float = 0.6  # Below this = LOW confidence, flagged
    DEFAULT_JURISDICTION: str = "IL"

    # CourtListener API — free, register at courtlistener.com
    COURTLISTENER_API_KEY: str = os.getenv("COURTLISTENER_API_KEY", "")

    # Research agent settings
    RESEARCH_MAX_QUERIES_PER_ISSUE: int = 5
    RESEARCH_MAX_CASES_PER_QUERY: int = 10
    RESEARCH_COST_BUDGET_USD: float = 1.00


settings = Settings()
