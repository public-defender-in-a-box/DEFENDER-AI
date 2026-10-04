#!/usr/bin/env python3
"""Generate docs/INVENTORY.md from the committed tree.

The project's self-description is derived from the code, never written by hand:
agents and their STATUS, Orchestrator registration, CaseState slots, which agents
the running app can reach, test counts and line totals.

    python scripts/inventory.py           # rewrite docs/INVENTORY.md
    python scripts/inventory.py --check   # exit 1 if docs/INVENTORY.md is stale (CI)

Standard library only. Reads tracked files (`git ls-files`), so untracked local
files never change the output.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
API = REPO / "packages" / "api"
OUTPUT = REPO / "docs" / "INVENTORY.md"

ORCHESTRATOR = API / "src" / "agents" / "tier0" / "orchestrator.py"
CASE_STATE = API / "src" / "models" / "case_state.py"
MAIN = API / "src" / "main.py"


@dataclass
class Agent:
    agent_id: str
    class_name: str
    path: Path
    status: str
    lines: int
    referenced_by: set[Path] = field(default_factory=set)
    tested_by: set[Path] = field(default_factory=set)


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO, check=True, capture_output=True, text=True
    ).stdout
    return sorted(REPO / name for name in out.split("\0") if name)


def rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def line_count(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines())


def parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def module_name(path: Path) -> str:
    """packages/api/src/agents/x.py -> src.agents.x"""
    parts = path.relative_to(API).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def is_test_file(path: Path) -> bool:
    return path.name.startswith("test_") or "tests" in path.relative_to(API).parts


def string_assign(body: list[ast.stmt], name: str) -> str | None:
    for node in body:
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in node.targets)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            return node.value.value
    return None


# --- import graph ------------------------------------------------------------


def resolve_import(node: ast.ImportFrom | ast.Import, path: Path, modules: dict[str, Path]):
    """Yield (module path, imported names) for imports that resolve inside packages/api."""
    if isinstance(node, ast.Import):
        for alias in node.names:
            if alias.name in modules:
                yield modules[alias.name], set()
        return
    base = node.module or ""
    if node.level:
        package = module_name(path).split(".")
        if path.name != "__init__.py":
            package = package[:-1]
        package = package[: len(package) - (node.level - 1)]
        base = ".".join(package + ([base] if base else []))
    names = {alias.name for alias in node.names}
    if base in modules:
        yield modules[base], names
    for name in names:
        if f"{base}.{name}" in modules:
            yield modules[f"{base}.{name}"], set()


def import_graph(py_files: list[Path]) -> tuple[dict[Path, set[Path]], dict[Path, set[str]]]:
    """Return (module -> imported modules, module -> names imported anywhere in it)."""
    modules = {module_name(p): p for p in py_files}
    edges: dict[Path, set[Path]] = defaultdict(set)
    names: dict[Path, set[str]] = defaultdict(set)
    for path in py_files:
        for node in ast.walk(parse(path)):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for target, imported in resolve_import(node, path, modules):
                    edges[path].add(target)
                    names[path] |= imported
    return edges, names


def reachable_from(start: Path, edges: dict[Path, set[Path]]) -> set[Path]:
    seen, stack = {start}, [start]
    while stack:
        for nxt in edges.get(stack.pop(), ()):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


# --- collectors --------------------------------------------------------------


def collect_agents(py_files: list[Path]) -> list[Agent]:
    agents = []
    for path in py_files:
        if is_test_file(path) or "agents" not in path.relative_to(API).parts:
            continue
        tree = parse(path)
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and any(
                isinstance(b, ast.Name) and b.id == "BaseAgent" for b in node.bases
            ):
                agents.append(
                    Agent(
                        agent_id=string_assign(node.body, "agent_id") or "?",
                        class_name=node.name,
                        path=path,
                        status=string_assign(tree.body, "STATUS") or "UNDECLARED",
                        lines=line_count(path),
                    )
                )
    return sorted(agents, key=lambda a: rel(a.path))


def collect_agent_config() -> dict[str, dict[str, str]]:
    for node in parse(ORCHESTRATOR).body:
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "_AGENT_CONFIG"
            and isinstance(node.value, ast.Dict)
        ):
            config = {}
            for key, value in zip(node.value.keys, node.value.values):
                entry = {}
                for k, v in zip(value.keys, value.values):
                    if isinstance(v, ast.Constant):
                        entry[k.value] = str(v.value)
                    elif isinstance(v, ast.Attribute):
                        entry[k.value] = v.attr
                config[key.value] = entry
            return config
    raise SystemExit("could not find _AGENT_CONFIG in orchestrator.py")


def collect_case_state_slots() -> list[str]:
    for node in parse(CASE_STATE).body:
        if isinstance(node, ast.ClassDef) and node.name == "CaseState":
            return [
                stmt.target.id
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign)
                and isinstance(stmt.target, ast.Name)
                and ast.unparse(stmt.annotation) == "dict[str, Any] | None"
            ]
    raise SystemExit("could not find CaseState in case_state.py")


def collect_routers() -> list[str]:
    routers = []
    for node in ast.walk(parse(MAIN)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "include_router"
            and node.args
        ):
            routers.append(ast.unparse(node.args[0]))
    return routers


def count_tests(path: Path) -> int:
    count = 0
    for node in parse(path).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            count += node.name.startswith("test_")
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            count += sum(
                isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                and n.name.startswith("test_")
                for n in node.body
            )
    return count


# --- rendering ---------------------------------------------------------------


def table(headers: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(row) + " |" for row in rows]
    return out


def render() -> str:
    files = tracked_files()
    api_py = [p for p in files if p.suffix == ".py" and p.is_relative_to(API)]
    src_py = [p for p in api_py if p.is_relative_to(API / "src")]
    test_files = [p for p in api_py if p.name.startswith("test_")]
    web_ts = [
        p
        for p in files
        if p.suffix in (".ts", ".tsx") and p.is_relative_to(REPO / "packages" / "web" / "src")
    ]

    edges, imported_names = import_graph(api_py)
    live = reachable_from(MAIN, edges)
    agents = collect_agents(api_py)
    config = collect_agent_config()
    slots = collect_case_state_slots()

    agents_per_dir = defaultdict(int)
    for agent in agents:
        agents_per_dir[agent.path.parent] += 1

    for agent in agents:
        # An agent that owns its package (e.g. sentencing_agent/) is tested through
        # any of the package's modules, not only through the class itself.
        own_package = agent.path.parent if agents_per_dir[agent.path.parent] == 1 else None
        for path in api_py:
            if path == agent.path:
                continue
            targets = edges.get(path, set())
            imports_agent = agent.class_name in imported_names.get(path, set()) or (
                own_package is not None and any(t.is_relative_to(own_package) for t in targets)
            )
            if not imports_agent:
                continue
            if is_test_file(path):
                agent.tested_by.add(path)
            elif path.name != "__init__.py" and not (
                own_package and path.is_relative_to(own_package)
            ):
                agent.referenced_by.add(path)

    def short(path: Path) -> str:
        return path.relative_to(API / "src").as_posix() if path.is_relative_to(API) else rel(path)

    by_id = {a.agent_id: a for a in agents}
    statuses = defaultdict(int)
    for agent in agents:
        statuses[agent.status] += 1
    test_counts = {p: count_tests(p) for p in test_files}

    out = [
        "# Project Inventory",
        "",
        "> Generated by `scripts/inventory.py` from the committed tree. Do not edit by hand.",
        "> CI fails when this file is stale: run `python scripts/inventory.py` and commit.",
        "> This is the only description of the codebase's state to trust (CLAUDE.md §8.1).",
        "",
        "## Totals",
        "",
        *table(
            ["What", "Files", "Lines"],
            [
                [
                    "Python, `packages/api/src` (non-test)",
                    str(sum(not is_test_file(p) for p in src_py)),
                    str(sum(line_count(p) for p in src_py if not is_test_file(p))),
                ],
                [
                    "Python tests, `packages/api` (incl. in-package tests)",
                    str(sum(is_test_file(p) for p in api_py)),
                    str(sum(line_count(p) for p in api_py if is_test_file(p))),
                ],
                [
                    "TypeScript, `packages/web/src`",
                    str(len(web_ts)),
                    str(sum(map(line_count, web_ts))),
                ],
            ],
        ),
        "",
        (
            f"Test functions: **{sum(test_counts.values())}** in {len(test_files)} files "
            "(parametrized tests count once)."
        ),
        "",
        "## Agents",
        "",
        f"{len(agents)} agent classes: "
        + ", ".join(
            f"{statuses[s]} {s}" for s in ("REAL", "PARTIAL", "STUB", "UNDECLARED") if statuses[s]
        )
        + f". {sum(a.agent_id in config for a in agents)} registered in `_AGENT_CONFIG`; "
        f"{sum(a.path in live for a in agents)} reachable from `main.py` (run in the app).",
        "",
        "- **STATUS**: declared by the module; see `AGENT_STATUSES` in `agents/base_agent.py`.",
        "- **Registered**: has an `_AGENT_CONFIG` entry, so the Orchestrator can merge its output.",
        "- **In app**: importable from `src/main.py`, i.e. some API route can run it.",
        "- **Used by**: non-test modules that import the class (package re-exports excluded).",
        "",
        *table(
            ["Agent ID", "Module", "STATUS", "Lines", "Registered", "In app", "Used by", "Tests"],
            [
                [
                    f"`{a.agent_id}`",
                    f"`{short(a.path)}`",
                    a.status,
                    str(a.lines),
                    "yes" if a.agent_id in config else "—",
                    "yes" if a.path in live else "—",
                    ", ".join(f"`{short(p)}`" for p in sorted(a.referenced_by)) or "—",
                    str(sum(test_counts.get(p, 0) for p in a.tested_by)) if a.tested_by else "—",
                ]
                for a in agents
            ],
        ),
        "",
        "Tests = test functions in files that import the class (or, for an agent that owns its",
        "package, any module of that package). Integration tests that reach an agent only",
        "through the Orchestrator or a route are not attributed to it. Parametrized tests count",
        "once.",
        "",
        "## Orchestrator registration (`_AGENT_CONFIG`)",
        "",
        *table(
            ["Key", "Agent STATUS", "CaseState slot", "Requires stage", "Client-facing"],
            [
                [
                    f"`{key}`",
                    by_id[key].status if key in by_id else "alias / no agent with this id",
                    f"`{entry.get('state_field', '?')}`",
                    entry.get("required_stage", "?"),
                    entry.get("is_client_facing", "?"),
                ]
                for key, entry in config.items()
            ],
        ),
        "",
        "## CaseState agent-output slots",
        "",
        *table(
            ["Slot", "Written by (`_AGENT_CONFIG` keys)"],
            [
                [
                    f"`{slot}`",
                    ", ".join(f"`{k}`" for k, e in config.items() if e.get("state_field") == slot)
                    or "— (nothing writes this slot)",
                ]
                for slot in slots
            ],
        ),
        "",
        "## API routers mounted in `main.py`",
        "",
        *[f"- `{router}`" for router in collect_routers()],
        "",
        "## Test files",
        "",
        *table(
            ["File", "Test functions"],
            [[f"`{rel(p)}`", str(test_counts[p])] for p in test_files],
        ),
        "",
        "## Legal corpus",
        "",
        "Files in `packages/api/src/corpus/data/` (excluding `.gitkeep`): "
        + str(
            sum(
                p.is_relative_to(API / "src" / "corpus" / "data") and p.name != ".gitkeep"
                for p in files
            )
        )
        + ".",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if the file is stale")
    args = parser.parse_args()

    content = render()
    if args.check:
        current = OUTPUT.read_text(encoding="utf-8") if OUTPUT.exists() else ""
        if current != content:
            sys.stdout.writelines(
                difflib.unified_diff(
                    current.splitlines(keepends=True),
                    content.splitlines(keepends=True),
                    fromfile=rel(OUTPUT),
                    tofile="regenerated",
                )
            )
            print(f"\n{rel(OUTPUT)} is stale. Run `python scripts/inventory.py` and commit.")
            return 1
        print(f"{rel(OUTPUT)} is up to date.")
        return 0
    OUTPUT.write_text(content, encoding="utf-8")
    print(f"wrote {rel(OUTPUT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
