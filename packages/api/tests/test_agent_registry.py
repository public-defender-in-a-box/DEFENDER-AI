"""Status and wiring invariants for every agent module (SPEC v2.0, Phase 0).

Every agent module declares STATUS. Stubs may stay registered with the Orchestrator,
but their output must say so. Which agents are wired into the Orchestrator, and which
are not, is asserted explicitly, so the agents directory can never again be mistaken
for a working system.
"""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

import pytest

from src.agents.base_agent import AGENT_STATUSES, BaseAgent
from src.agents.tier0.orchestrator import _AGENT_CONFIG
from src.models.case_state import CaseState

API_ROOT = Path(__file__).resolve().parents[1]
AGENTS_DIR = API_ROOT / "src" / "agents"

# _AGENT_CONFIG keys that are second names for an agent_id (see orchestrator.py).
CONFIG_ALIASES = {"case_prep": "case_prep_conductor"}

# Agents that run the pipeline rather than write a CaseState slot.
INFRASTRUCTURE = {"orchestrator", "ethics_monitor"}

# Agents with no _AGENT_CONFIG entry, and so no path into CaseState through the
# Orchestrator. Wiring one in means removing it from this set.
UNWIRED = {
    "brady_agent",
    "case_law_agent",
    "citation_verifier",
    "collateral_agent",
    "fact_gatherer",
    "motion_drafter",
    "personal_circumstances",
    "plea_trial_analyst",
    "recency_monitor",
    "rights_scanner",
    "sentencing_agent",
    "statute_agent",
}

# Stubs that are registered anyway; they run and their output is labeled STUB.
REGISTERED_STUBS = {"case_prep_conductor"}


def _discover_agent_classes() -> list[type[BaseAgent]]:
    """Import every module under src/agents that defines a BaseAgent subclass."""
    classes: list[type[BaseAgent]] = []
    for path in sorted(AGENTS_DIR.rglob("*.py")):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text())
        defines_agent = any(
            isinstance(node, ast.ClassDef)
            and any(isinstance(base, ast.Name) and base.id == "BaseAgent" for base in node.bases)
            for node in tree.body
        )
        if not defines_agent:
            continue
        module = importlib.import_module(".".join(path.relative_to(API_ROOT).with_suffix("").parts))
        classes.extend(
            obj
            for obj in vars(module).values()
            if isinstance(obj, type)
            and issubclass(obj, BaseAgent)
            and obj is not BaseAgent
            and obj.__module__ == module.__name__
        )
    return classes


def _module_status(cls: type[BaseAgent]) -> str | None:
    return getattr(sys.modules[cls.__module__], "STATUS", None)


AGENT_CLASSES = _discover_agent_classes()
AGENT_IDS = {cls.agent_id for cls in AGENT_CLASSES}
STUB_CLASSES = [cls for cls in AGENT_CLASSES if _module_status(cls) == "STUB"]


def test_discovery_finds_the_agents():
    # Guards the parametrized tests below against passing on an empty list.
    assert len(AGENT_CLASSES) >= 20
    assert len(STUB_CLASSES) >= 1


def test_agent_ids_are_unique():
    ids = [cls.agent_id for cls in AGENT_CLASSES]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("cls", AGENT_CLASSES, ids=lambda cls: cls.__name__)
def test_agent_module_declares_status(cls):
    assert _module_status(cls) in AGENT_STATUSES


@pytest.mark.parametrize("cls", STUB_CLASSES, ids=lambda cls: cls.__name__)
def test_stub_output_is_labeled(cls):
    assert cls.wrap_output is BaseAgent.wrap_output
    envelope = cls().wrap_output({}, confidence=0.5)
    assert envelope["agent_status"] == "STUB"


def test_registered_stubs_are_explicit():
    registered = {cls.agent_id for cls in STUB_CLASSES if cls.agent_id in _AGENT_CONFIG}
    assert registered == REGISTERED_STUBS


def test_agent_config_keys_resolve_to_agents():
    for key in _AGENT_CONFIG:
        assert CONFIG_ALIASES.get(key, key) in AGENT_IDS, key


def test_agent_config_state_fields_exist_on_case_state():
    for key, config in _AGENT_CONFIG.items():
        assert config["state_field"] in CaseState.model_fields, key


def test_unwired_agents_are_explicit():
    assert AGENT_IDS - set(_AGENT_CONFIG) - INFRASTRUCTURE == UNWIRED
