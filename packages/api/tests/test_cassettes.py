"""Committed cassettes are safe to commit (PHASE_1_MODEL_GATEWAY.md §5.1, §10).

``test_cassettes_contain_no_secrets`` scans every committed cassette; until the
recording pass runs there are none, so ``test_scanner_catches`` proves the scanner
itself on deliberately bad cassettes rather than letting the suite pass vacuously.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from src.services.model_gateway.cassettes import DEFAULT_CASSETTE_ROOT

API_ROOT = Path(__file__).resolve().parents[1]

# Real-looking identifiers. Fixtures mark synthetic case numbers with a SYN- prefix.
_CASE_NUMBER = re.compile(
    r"(?<![A-Z0-9-])(?<!SYN-)(?:(?:19|20)?\d{2}[- ]?(?:CR|SC|CV|SU|MD|TR|DR|JV|SR|MI)[- ]?\d{3,7})\b",
    re.IGNORECASE,
)
_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE = re.compile(r"(?:\(\d{3}\)\s?|\b\d{3}[-.])(?!555)\d{3}[-.]\d{4}\b")
_API_KEY = re.compile(r"sk-ant-")


def _has_headers(node: object) -> bool:
    if isinstance(node, dict):
        return any(
            str(k).lower() in ("headers", "x-api-key", "authorization") or _has_headers(v)
            for k, v in node.items()
        )
    if isinstance(node, list):
        return any(_has_headers(v) for v in node)
    return False


def _fixture_resolves(fixture_id: str) -> bool:
    path, _, name = fixture_id.partition("::")
    file = API_ROOT / path
    return file.is_file() and (not name or name in file.read_text(encoding="utf-8"))


def scan(path: Path) -> list[str]:
    """Problems with one cassette file; empty means safe to commit."""
    text = path.read_text(encoding="utf-8")
    problems = [
        f"{label}: {match}"
        for label, rx in (
            ("API key", _API_KEY),
            ("case number", _CASE_NUMBER),
            ("SSN", _SSN),
            ("phone number", _PHONE),
        )
        for match in rx.findall(text)[:3]
    ]
    data = json.loads(text)
    if _has_headers(data):
        problems.append("stores request headers")
    fixture_ids = data.get("fixture_ids") or []
    if not fixture_ids:
        problems.append("no fixture_ids")
    problems += [f"fixture does not resolve: {f}" for f in fixture_ids if not _fixture_resolves(f)]
    return problems


def _cassettes() -> list[Path]:
    return sorted(DEFAULT_CASSETTE_ROOT.rglob("*.json")) if DEFAULT_CASSETTE_ROOT.exists() else []


def test_cassettes_contain_no_secrets() -> None:
    problems = {str(p.relative_to(API_ROOT)): scan(p) for p in _cassettes()}
    assert not {k: v for k, v in problems.items() if v}, problems


@pytest.mark.parametrize(
    "mutation,expected",
    [
        ({"request": {"headers": {"x-api-key": "redacted"}}}, "stores request headers"),
        ({"note": "sk-ant-api03-not-a-real-key"}, "API key"),
        ({"note": "Case No. 2024-CR-004821"}, "case number"),
        ({"note": "SSN 123-45-6789"}, "SSN"),
        ({"note": "call 404-867-5309"}, "phone number"),
        ({"fixture_ids": []}, "no fixture_ids"),
        ({"fixture_ids": ["tests/fixtures/does_not_exist.txt"]}, "fixture does not resolve"),
    ],
)
def test_scanner_catches(tmp_path: Path, mutation: dict, expected: str) -> None:
    clean = {
        "fixture_ids": ["tests/fixtures/sample_accusation.txt"],
        "request": {"messages": [{"role": "user", "content": "Case No. SYN-2024-SC-04821"}]},
        "response": {"content": [{"type": "text", "text": "{}"}]},
    }
    good = tmp_path / "good.json"
    good.write_text(json.dumps(clean))
    assert scan(good) == []

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({**clean, **mutation}))
    assert any(expected in problem for problem in scan(bad)), scan(bad)


def test_fixture_case_numbers_are_marked_synthetic() -> None:
    """Fixtures feed cassettes, so their case numbers must pass the scan too."""
    fixtures = API_ROOT / "tests" / "fixtures"
    hits = {
        str(p.relative_to(API_ROOT)): _CASE_NUMBER.findall(p.read_text(encoding="utf-8"))
        for p in fixtures.rglob("*")
        if p.is_file() and p.suffix in (".txt", ".py", ".json")
    }
    assert not {k: v for k, v in hits.items() if v}, hits
