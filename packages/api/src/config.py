import os


class Settings:
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    STORAGE_PATH: str = os.getenv("STORAGE_PATH", "./uploads")
    CONFIDENCE_THRESHOLD: float = 0.6  # Below this = LOW confidence, flagged
    DEFAULT_JURISDICTION: str = "GA"


settings = Settings()
