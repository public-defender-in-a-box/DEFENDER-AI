"""Prompt files are versioned and immutable (CLAUDE.md §6; PHASE_1_MODEL_GATEWAY.md §7)."""

from __future__ import annotations

import ast
from pathlib import Path

from src.prompts import discover, prompt_path, read_manifest

SRC = Path(__file__).resolve().parents[1] / "src"


def test_prompt_files_match_manifest() -> None:
    on_disk = discover()
    manifest = read_manifest()
    edited = {k for k in on_disk if k in manifest and manifest[k] != on_disk[k]}
    assert not edited, (
        f"Prompt files edited in place: {sorted(edited)}. A changed prompt is a new "
        "version: copy it to <name>.<next>.txt, point the call site at it, and run "
        "`python -m src.prompts`."
    )
    unregistered = set(on_disk) - set(manifest)
    assert not unregistered, f"Run `python -m src.prompts` to register: {sorted(unregistered)}"
    deleted = set(manifest) - set(on_disk)
    assert not deleted, f"Manifest lists prompt versions with no file: {sorted(deleted)}"


def test_every_load_prompt_call_resolves() -> None:
    missing: list[str] = []
    for path in SRC.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "load_prompt"
                and len(node.args) == 2
                and all(isinstance(a, ast.Constant) for a in node.args)
            ):
                prompt_id, version = (a.value for a in node.args)  # type: ignore[attr-defined]
                if not prompt_path(prompt_id, version).is_file():
                    missing.append(f"{path.name}: {prompt_id}@{version}")
    assert not missing, missing
