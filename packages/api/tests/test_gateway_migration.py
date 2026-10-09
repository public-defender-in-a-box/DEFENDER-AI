"""Static guards for the Phase 1 migration (PHASE_1_MODEL_GATEWAY.md §3.2, §9, §10).

- ``test_broad_except_count``: no ``except Exception`` (or bare ``except``) in
  ``src/agents/`` unless listed below with the reason handling it there is correct.
- ``test_shim_callers_decreasing``: the deprecated ``call_llm`` shim's caller count
  only goes down; it reaches zero when migration completes.
"""

from __future__ import annotations

import ast
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
AGENTS = API_ROOT / "src" / "agents"
SRC = API_ROOT / "src"

# path relative to packages/api -> (count, reason). Shrinks; never grows silently.
_PENDING = "not yet migrated (Phase 1 §9 order)"
BROAD_EXCEPT_ALLOWLIST: dict[str, tuple[int, str]] = {
    "src/agents/graph.py": (3, _PENDING),
    "src/agents/tier1/pre_interview.py": (1, _PENDING),
    "src/agents/tier2_attorney/motion_drafter.py": (1, _PENDING),
    "src/agents/tier2_attorney/plea_trial_analyst.py": (2, _PENDING),
    "src/agents/tier2_intake/collateral_agent.py": (2, _PENDING),
    "src/agents/tier2_intake/fact_gatherer.py": (6, _PENDING),
    "src/agents/tier2_intake/personal_circumstances.py": (5, _PENDING),
}

# Lower this as call sites migrate; it must never go up.
SHIM_CALLERS_MAX = 18


def _is_broad(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return True
    names = handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
    return any(isinstance(n, ast.Name) and n.id in ("Exception", "BaseException") for n in names)


def _broad_excepts() -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in sorted(AGENTS.rglob("*.py")):
        if "tests" in path.relative_to(AGENTS).parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        n = sum(
            1 for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler) and _is_broad(node)
        )
        if n:
            counts[str(path.relative_to(API_ROOT))] = n
    return counts


def _shim_calls() -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        n = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and (
                (isinstance(node.func, ast.Name) and node.func.id == "call_llm")
                or (isinstance(node.func, ast.Attribute) and node.func.attr == "call_llm")
            )
        )
        if n:
            counts[str(path.relative_to(API_ROOT))] = n
    return counts


def test_broad_except_count() -> None:
    found = _broad_excepts()
    unexpected = {
        path: n for path, n in found.items() if n > BROAD_EXCEPT_ALLOWLIST.get(path, (0, ""))[0]
    }
    assert not unexpected, (
        "except Exception in agent code converts failures into well-formed empty "
        f"results (§3). Narrow these, or allowlist them with a reason: {unexpected}"
    )
    stale = {
        path: (allowed, found.get(path, 0))
        for path, (allowed, _) in BROAD_EXCEPT_ALLOWLIST.items()
        if found.get(path, 0) < allowed
    }
    assert not stale, f"Allowlist is larger than needed; lower it: {stale}"


def test_shim_callers_decreasing() -> None:
    total = sum(_shim_calls().values())
    assert total <= SHIM_CALLERS_MAX, f"call_llm callers grew to {total}: {_shim_calls()}"
    assert (
        total == SHIM_CALLERS_MAX
    ), f"call_llm callers fell to {total}; lower SHIM_CALLERS_MAX to lock in the progress"
