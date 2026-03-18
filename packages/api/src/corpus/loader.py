"""Legal corpus loader — loads verified statutes and case law."""

import json
from pathlib import Path
from typing import Any

CORPUS_DIR = Path(__file__).parent / "data"


def load_statutes(jurisdiction: str = "IL") -> list[dict[str, Any]]:
    """Load verified statutes for a jurisdiction."""
    file_path = CORPUS_DIR / f"{jurisdiction.lower()}_statutes.json"
    if not file_path.exists():
        return []
    return json.loads(file_path.read_text())


def load_case_law(jurisdiction: str = "IL") -> list[dict[str, Any]]:
    """Load verified case law for a jurisdiction."""
    file_path = CORPUS_DIR / f"{jurisdiction.lower()}_case_law.json"
    if not file_path.exists():
        return []
    return json.loads(file_path.read_text())
