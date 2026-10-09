"""Versioned prompt files (CLAUDE.md §6, §9; PHASE_1_MODEL_GATEWAY.md §7).

A prompt lives at ``src/prompts/<agent>/<name>.<version>.txt`` and is addressed as
``load_prompt("<agent>.<name>", "<version>")``. Files are used verbatim; a call site
that fills placeholders uses ``str.format``, so literal braces in such a file are
doubled, exactly as they were in the inline string the file replaced.

``MANIFEST.json`` pins the sha256 of every prompt file. A test fails when a file's
content no longer matches its entry, so a prompt cannot change without a new version
(regenerate entries for new files with ``python -m src.prompts``).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent
MANIFEST_PATH = PROMPTS_DIR / "MANIFEST.json"


@dataclass(frozen=True)
class Prompt:
    id: str
    version: str
    text: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def compose_version(*prompts: Prompt) -> str:
    """The version string a call records when it uses several prompt files.

    ``compose_version(system_v1, extract_v1) == "system.v1+extract.v1"``, so a change
    to any file the call uses shows up in the recorded version.
    """
    return "+".join(f"{p.id.split('.', 1)[1]}.{p.version}" for p in prompts)


def prompt_path(prompt_id: str, version: str) -> Path:
    agent, _, name = prompt_id.partition(".")
    if not agent or not name:
        raise ValueError(f"prompt_id must be '<agent>.<name>', got {prompt_id!r}")
    return PROMPTS_DIR / agent / f"{name}.{version}.txt"


@lru_cache(maxsize=None)
def load_prompt(prompt_id: str, version: str) -> Prompt:
    path = prompt_path(prompt_id, version)
    return Prompt(id=prompt_id, version=version, text=path.read_text(encoding="utf-8"))


def discover() -> dict[str, str]:
    """``{"<agent>.<name>@<version>": sha256}`` for every prompt file on disk."""
    found: dict[str, str] = {}
    for path in sorted(PROMPTS_DIR.glob("*/*.txt")):
        name, _, version = path.stem.rpartition(".")
        prompt = load_prompt(f"{path.parent.name}.{name}", version)
        found[f"{prompt.id}@{prompt.version}"] = prompt.sha256
    return found


def read_manifest() -> dict[str, str]:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}


def main() -> int:
    """Add manifest entries for new prompt files. Never rewrites an existing entry."""
    manifest = read_manifest()
    changed = [k for k, sha in discover().items() if k in manifest and manifest[k] != sha]
    if changed:
        print(f"Edited without a version bump (copy to a new version instead): {changed}")
        return 1
    manifest.update({k: v for k, v in discover().items() if k not in manifest})
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(f"{len(manifest)} prompt versions in {MANIFEST_PATH.name}")
    return 0
