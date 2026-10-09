"""Intake Conductor — Tier 1, Client-Facing.

Manages the structured client interview across five phases. Adapts to charge
type, client demographics, and accessibility needs. Trauma-informed, plain
language, multilingual capable.

Migrated from standalone intake-conductor-agent. Core logic preserved:
- Five-phase interview structure (personal, incident, arrest, history, priorities)
- LLM-driven question generation and response processing
- Inconsistency analysis between client account and charges
- Subagent trigger dispatch for Tier 2 specialists
- Confidence scoring and ethical flag detection
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from src.agents.base_agent import BaseAgent
from src.models.responses.intake import InconsistencyAnalysis, PhaseQuestions, ProcessedResponse
from src.prompts import compose_version, load_prompt
from src.services.model_gateway import ModelCallRequest, call_model

STATUS = "REAL"

logger = logging.getLogger(__name__)

_REVIEW_THRESHOLD = 0.5

INTERVIEW_PHASES = [
    "personal_information",
    "incident_narrative",
    "arrest_and_custody",
    "prior_history",
    "priorities_and_concerns",
]


# ---------------------------------------------------------------------------
# Prompts — preserved from standalone intake-conductor-agent
# ---------------------------------------------------------------------------

# Prompts: src/prompts/intake_conductor/
_SYSTEM = load_prompt("intake_conductor.system", "v1")
_QUESTION_GENERATION = load_prompt("intake_conductor.question_generation", "v1")
_RESPONSE_PROCESSING = load_prompt("intake_conductor.response_processing", "v1")
_INCONSISTENCY_ANALYSIS = load_prompt("intake_conductor.inconsistency_analysis", "v1")

# Thinking tokens count toward max_tokens on current models (Phase 1 §2).
_QUESTIONS_MAX_TOKENS = 12000
_RESPONSE_MAX_TOKENS = 16000
_INCONSISTENCY_MAX_TOKENS = 16000

_PHASE_DESCRIPTIONS = {
    "personal_information": (
        "Gather demographics, employment, housing, family, immigration status, "
        "mental health, substance use, and special needs. This establishes the "
        "client's personal context and identifies collateral consequence risks."
    ),
    "incident_narrative": (
        "Get the client's account of what happened in their own words. Start "
        "open-ended, then targeted follow-ups based on charging documents. "
        "Do not lead the client."
    ),
    "arrest_and_custody": (
        "Document how the client was contacted/arrested, Miranda rights, statements "
        "made, consent to search, injuries, treatment in custody, and arrest witnesses. "
        "Critical for rights violation analysis."
    ),
    "prior_history": (
        "Criminal history, pending cases, probation/parole, prior LE interactions, "
        "relationship with complainant, compliance history."
    ),
    "priorities_and_concerns": (
        "What matters most to the client? Immigration, employment, housing, family, "
        "incarceration avoidance? What are they most worried about?"
    ),
}

_PHASE_ABBREVIATIONS = {
    "personal_information": "PI",
    "incident_narrative": "IN",
    "arrest_and_custody": "AC",
    "prior_history": "PH",
    "priorities_and_concerns": "PC",
}

# ---------------------------------------------------------------------------
# Default question bank. The intake route asks these when generation returns no
# questions for a phase. A *failed* generation raises (PHASE_1_MODEL_GATEWAY.md §3).
# ---------------------------------------------------------------------------

_DEFAULT_QUESTIONS: dict[str, list[dict[str, Any]]] = {
    "personal_information": [
        {
            "question_id": "Q-PI-001",
            "question_text": "What is your full legal name?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Verify identity",
            "follow_up_triggers": [],
            "related_charges": [],
            "feeds_subagent": "none",
        },
        {
            "question_id": "Q-PI-002",
            "question_text": "What is your date of birth?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Verify identity and determine if minor",
            "follow_up_triggers": ["under 18"],
            "related_charges": [],
            "feeds_subagent": "collateral_consequences",
        },
        {
            "question_id": "Q-PI-003",
            "question_text": "What is your current address?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Housing status",
            "follow_up_triggers": [],
            "related_charges": [],
            "feeds_subagent": "collateral_consequences",
        },
        {
            "question_id": "Q-PI-004",
            "question_text": "Are you currently employed? If so, where do you work?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Employment impact assessment",
            "follow_up_triggers": [],
            "related_charges": [],
            "feeds_subagent": "collateral_consequences",
        },
        {
            "question_id": "Q-PI-005",
            "question_text": "What is your immigration status?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Immigration consequences",
            "follow_up_triggers": ["not US citizen"],
            "related_charges": [],
            "feeds_subagent": "collateral_consequences",
        },
        {
            "question_id": "Q-PI-006",
            "question_text": "Do you have any children or dependents?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Family circumstances",
            "follow_up_triggers": [],
            "related_charges": [],
            "feeds_subagent": "collateral_consequences",
        },
        {
            "question_id": "Q-PI-007",
            "question_text": "Do you have any mental health conditions or are you currently taking any medications?",
            "question_type": "open_ended",
            "priority": "recommended",
            "rationale": "Competency and mitigation",
            "follow_up_triggers": ["mental health condition"],
            "related_charges": [],
            "feeds_subagent": "collateral_consequences",
        },
        {
            "question_id": "Q-PI-008",
            "question_text": "Do you have any history of substance use?",
            "question_type": "open_ended",
            "priority": "recommended",
            "rationale": "Drug court eligibility, mitigation",
            "follow_up_triggers": ["substance use"],
            "related_charges": [],
            "feeds_subagent": "collateral_consequences",
        },
    ],
    "incident_narrative": [
        {
            "question_id": "Q-IN-001",
            "question_text": "In your own words, can you tell me what happened?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Client's unguided account",
            "follow_up_triggers": [],
            "related_charges": [],
            "feeds_subagent": "fact_gatherer",
        },
        {
            "question_id": "Q-IN-002",
            "question_text": "Where exactly did this happen?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Location details",
            "follow_up_triggers": [],
            "related_charges": [],
            "feeds_subagent": "fact_gatherer",
        },
        {
            "question_id": "Q-IN-003",
            "question_text": "When did this happen? What time of day?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Timeline",
            "follow_up_triggers": [],
            "related_charges": [],
            "feeds_subagent": "fact_gatherer",
        },
        {
            "question_id": "Q-IN-004",
            "question_text": "Was anyone else there? Who?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Potential witnesses",
            "follow_up_triggers": [],
            "related_charges": [],
            "feeds_subagent": "fact_gatherer",
        },
        {
            "question_id": "Q-IN-005",
            "question_text": "Is there anything the police or the charges got wrong about what happened?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Identify discrepancies",
            "follow_up_triggers": [],
            "related_charges": [],
            "feeds_subagent": "fact_gatherer",
        },
    ],
    "arrest_and_custody": [
        {
            "question_id": "Q-AC-001",
            "question_text": "How did the police first contact you? Were you at home, in a car, on the street?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Arrest circumstances for 4th Amendment analysis",
            "follow_up_triggers": [],
            "related_charges": [],
            "feeds_subagent": "rights_violation_scanner",
        },
        {
            "question_id": "Q-AC-002",
            "question_text": "Did the police tell you that you had the right to remain silent and the right to an attorney?",
            "question_type": "yes_no",
            "priority": "required",
            "rationale": "Miranda compliance",
            "follow_up_triggers": ["no Miranda"],
            "related_charges": [],
            "feeds_subagent": "rights_violation_scanner",
        },
        {
            "question_id": "Q-AC-003",
            "question_text": "Did you say anything to the police? If so, what did you say?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Statements made \u2014 5th Amendment",
            "follow_up_triggers": ["made statements"],
            "related_charges": [],
            "feeds_subagent": "rights_violation_scanner",
        },
        {
            "question_id": "Q-AC-004",
            "question_text": "Did the police search you, your car, or your home? Did they ask for your permission to search?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Search and seizure \u2014 4th Amendment",
            "follow_up_triggers": ["search conducted"],
            "related_charges": [],
            "feeds_subagent": "rights_violation_scanner",
        },
        {
            "question_id": "Q-AC-005",
            "question_text": "Were you physically hurt during the arrest? Were the police rough with you?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Excessive force",
            "follow_up_triggers": ["injury"],
            "related_charges": [],
            "feeds_subagent": "rights_violation_scanner",
        },
        {
            "question_id": "Q-AC-006",
            "question_text": "Did you ask for a lawyer at any point? What happened when you did?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "6th Amendment \u2014 right to counsel",
            "follow_up_triggers": ["requested lawyer"],
            "related_charges": [],
            "feeds_subagent": "rights_violation_scanner",
        },
    ],
    "prior_history": [
        {
            "question_id": "Q-PH-001",
            "question_text": "Have you ever been arrested or charged with a crime before?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Criminal history for sentencing",
            "follow_up_triggers": ["prior arrests"],
            "related_charges": [],
            "feeds_subagent": "none",
        },
        {
            "question_id": "Q-PH-002",
            "question_text": "Have you ever been convicted of a crime?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Prior convictions \u2014 enhancement risk",
            "follow_up_triggers": ["prior convictions"],
            "related_charges": [],
            "feeds_subagent": "none",
        },
        {
            "question_id": "Q-PH-003",
            "question_text": "Are you currently on probation, parole, or any form of supervised release?",
            "question_type": "yes_no",
            "priority": "required",
            "rationale": "Supervision status",
            "follow_up_triggers": ["on supervision"],
            "related_charges": [],
            "feeds_subagent": "none",
        },
        {
            "question_id": "Q-PH-004",
            "question_text": "Do you have any other pending criminal cases?",
            "question_type": "yes_no",
            "priority": "required",
            "rationale": "Pending cases",
            "follow_up_triggers": ["pending cases"],
            "related_charges": [],
            "feeds_subagent": "none",
        },
    ],
    "priorities_and_concerns": [
        {
            "question_id": "Q-PC-001",
            "question_text": "What are you most worried about with this case?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Client priorities",
            "follow_up_triggers": [],
            "related_charges": [],
            "feeds_subagent": "none",
        },
        {
            "question_id": "Q-PC-002",
            "question_text": "Is there anything specific you want to make sure your attorney knows about?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Catch-all",
            "follow_up_triggers": [],
            "related_charges": [],
            "feeds_subagent": "none",
        },
        {
            "question_id": "Q-PC-003",
            "question_text": "Are you worried about losing your job, your housing, or your immigration status because of this case?",
            "question_type": "open_ended",
            "priority": "required",
            "rationale": "Collateral consequences priorities",
            "follow_up_triggers": ["immigration concern", "job concern", "housing concern"],
            "related_charges": [],
            "feeds_subagent": "collateral_consequences",
        },
    ],
}


# ---------------------------------------------------------------------------
# Interview helpers
# ---------------------------------------------------------------------------


def _summarize_charge_data(charge_data: dict[str, Any]) -> str:
    """Create a focused summary of charge data for question generation."""
    summary: dict[str, Any] = {
        "defendant": charge_data.get("defendant", {}),
        "charges": [],
        "key_allegations": [],
        "misconduct_flags": [],
    }
    for charge in charge_data.get("charges", []):
        summary["charges"].append(
            {
                "count": charge.get("count_number"),
                "description": charge.get("charge_description"),
                "statute": charge.get("statute", {}).get("code"),
                "degree": charge.get("degree"),
                "date": charge.get("date_of_alleged_offense"),
                "location": charge.get("location_of_alleged_offense"),
            }
        )
    for allegation in charge_data.get("factual_allegations", [])[:10]:
        summary["key_allegations"].append(
            {
                "summary": allegation.get("summary"),
                "category": allegation.get("category"),
            }
        )
    for flag in charge_data.get("misconduct_flags", []):
        summary["misconduct_flags"].append(
            {
                "category": flag.get("category"),
                "description": flag.get("description"),
            }
        )
    return json.dumps(summary, indent=2, default=str)


def _create_charge_summary_for_processing(charge_data: dict[str, Any]) -> str:
    """Create a focused text summary for response processing context."""
    parts: list[str] = []

    defendant = charge_data.get("defendant", {})
    if defendant.get("name") and defendant["name"] != "UNKNOWN":
        parts.append(f"Defendant: {defendant['name']}")

    charges = charge_data.get("charges", [])
    if charges:
        lines = []
        for c in charges:
            line = f"Count {c.get('count_number', '?')}: {c.get('charge_description', 'Unknown charge')}"
            if c.get("statute", {}).get("code"):
                line += f" ({c['statute']['code']})"
            lines.append(line)
        parts.append("Charges:\n" + "\n".join(lines))

    allegations = charge_data.get("factual_allegations", [])
    if allegations:
        alleg_lines = [a.get("summary", "") for a in allegations[:8]]
        parts.append("Key Allegations:\n" + "\n".join(f"- {a}" for a in alleg_lines if a))

    misconduct = charge_data.get("misconduct_flags", [])
    if misconduct:
        lines = [f"- {m.get('description', '')}" for m in misconduct[:5]]
        parts.append("Misconduct Flags:\n" + "\n".join(lines))

    return "\n\n".join(parts)


def _summarize_pre_interview_for_phase(
    pre_interview_research: dict[str, Any] | None,
    phase: str,
) -> str:
    """Create a focused summary of pre-interview research for a given phase."""
    if not pre_interview_research:
        return "None \u2014 no pre-interview research available."

    pi = pre_interview_research
    # Unwrap ConfidenceRated wrapper if needed
    if "data" in pi and "confidence" in pi:
        pi = pi["data"]

    targeted = [
        tq
        for tq in pi.get("targeted_questions", [])
        if (tq.get("phase") or "incident_narrative") == phase
    ]
    rights_flags = pi.get("preliminary_rights_flags", [])
    collateral = pi.get("collateral_consequence_alerts", [])
    known_facts = pi.get("known_facts_from_documents", [])
    legal_brief = pi.get("legal_brief", {}) or {}

    payload = {
        "targeted_questions_for_this_phase": [
            {
                "question": tq.get("question"),
                "priority": tq.get("priority"),
                "relevant_element": tq.get("relevant_element"),
                "rationale": tq.get("rationale"),
            }
            for tq in targeted
        ],
        "preliminary_rights_flags": [
            {
                "flag_id": f.get("flag_id"),
                "type": f.get("type"),
                "description": f.get("description"),
                "investigation_needed": f.get("investigation_needed"),
                "severity": f.get("severity"),
            }
            for f in rights_flags
        ],
        "collateral_consequence_alerts": [
            {
                "alert_id": c.get("alert_id"),
                "category": c.get("category"),
                "description": c.get("description"),
                "severity": c.get("severity"),
            }
            for c in collateral
        ],
        "known_facts_from_documents": [
            {
                "fact": kf.get("fact"),
                "category": kf.get("category"),
                "verify_with_client": kf.get("verify_with_client"),
            }
            for kf in known_facts[:15]
        ],
        "key_legal_issues": legal_brief.get("key_legal_issues", []),
        "potential_defenses": legal_brief.get("potential_defenses", []),
    }
    text = json.dumps(payload, indent=2, default=str)
    if len(text) > 15_000:
        text = text[:15_000] + "\n... [TRUNCATED]"
    return text


def _summarize_known_client_facts(
    previous_responses: list[dict[str, Any]] | None,
) -> str:
    """Extract a plain-English bullet list of facts the client has already shared.

    Used in the question-generation prompt to prevent duplicate questions
    (e.g. not asking "what is your job" after the client said they're a teacher).
    """
    if not previous_responses:
        return (
            "None \u2014 this is the first phase and the client has not " "answered anything yet."
        )

    lines: list[str] = []
    for r in previous_responses:
        q = (r.get("question_text") or "").strip()
        a = (r.get("client_response") or r.get("response") or "").strip()
        if not a:
            continue
        if len(q) > 140:
            q = q[:140] + "..."
        if len(a) > 280:
            a = a[:280] + "..."
        if q:
            lines.append(f"- Q: {q}\n  Client said: {a}")
        else:
            lines.append(f"- Client said: {a}")

    if not lines:
        return "None \u2014 no substantive client answers yet."
    return "\n".join(lines)


def _normalize_question_text(text: str) -> str:
    """Normalize question text for dedup comparison."""
    import re

    t = (text or "").lower().strip()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Drop very common stopwords that don't affect meaning
    stops = {
        "the",
        "a",
        "an",
        "do",
        "did",
        "you",
        "your",
        "can",
        "could",
        "please",
        "tell",
        "me",
        "about",
        "what",
        "is",
        "was",
        "were",
        "have",
        "had",
        "has",
        "any",
        "are",
        "to",
    }
    tokens = [w for w in t.split() if w not in stops]
    return " ".join(tokens)


def _dedupe_and_cap_questions(
    llm_questions: list[dict[str, Any]],
    injected_must_ask: list[dict[str, Any]] | None = None,
    max_total: int = 8,
    max_llm: int = 6,
) -> list[dict[str, Any]]:
    """Cap and dedupe LLM-generated questions against already-injected MUST_ASK.

    Rules:
    - Keep at most ``max_llm`` LLM questions
    - Drop any LLM question that normalizes to the same text as a MUST_ASK
    - Drop any LLM question that combines two questions with " and "
      (multi-part questions are banned)
    - Global cap ``max_total`` across LLM + must_ask
    """
    must_ask = injected_must_ask or []
    must_ask_norms = {_normalize_question_text(q.get("question_text", "")) for q in must_ask}

    kept: list[dict[str, Any]] = []
    seen_norms: set[str] = set(must_ask_norms)

    for q in llm_questions:
        if len(kept) >= max_llm:
            break
        text = (q.get("question_text") or "").strip()
        if not text:
            continue
        # Ban multi-part questions: any " and " inside a single question_text
        lowered = text.lower()
        if " and " in lowered and "?" in text:
            # If the " and " is part of a noun phrase it can stay; but if the
            # text contains two sentences or two clauses ending in a question
            # mark, drop it.
            if (
                text.count("?") > 1
                or " and what " in lowered
                or " and where " in lowered
                or " and when " in lowered
                or " and how " in lowered
                or " and why " in lowered
                or " and who " in lowered
                or " and did " in lowered
            ):
                continue
        norm = _normalize_question_text(text)
        if not norm or norm in seen_norms:
            continue
        seen_norms.add(norm)
        kept.append(q)

    # Combined cap — MUST_ASK wins if there's a conflict
    remaining_slots = max(0, max_total - len(must_ask))
    return kept[:remaining_slots]


async def _generate_questions(
    charge_data: dict[str, Any],
    phase: str,
    previous_responses: list[dict[str, Any]] | None = None,
    pre_interview_research: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate interview questions for a given phase. Raises on a failed call."""
    phase_description = _PHASE_DESCRIPTIONS.get(phase, "")
    phase_abbrev = _PHASE_ABBREVIATIONS.get(phase, "XX")
    charge_summary = _summarize_charge_data(charge_data)

    prev_text = "None \u2014 this is the first phase."
    if previous_responses:
        prev_text = json.dumps(previous_responses, indent=2, default=str)
        if len(prev_text) > 20_000:
            prev_text = prev_text[:20_000] + "\n... [TRUNCATED]"

    known_client_facts = _summarize_known_client_facts(previous_responses)

    pre_interview_context = _summarize_pre_interview_for_phase(pre_interview_research, phase)

    prompt = _QUESTION_GENERATION.text.format(
        charge_data=charge_summary,
        phase=phase,
        phase_description=phase_description,
        previous_responses=prev_text,
        phase_abbrev=phase_abbrev,
        pre_interview_context=pre_interview_context,
        known_client_facts=known_client_facts,
    )

    call = await call_model(
        ModelCallRequest(
            prompt=prompt,
            system=_SYSTEM.text,
            max_tokens=_QUESTIONS_MAX_TOKENS,
            response_model=PhaseQuestions,
            prompt_id="intake_conductor.question_generation",
            prompt_version=compose_version(_SYSTEM, _QUESTION_GENERATION),
            agent_id="intake_conductor",
        )
    )
    result = call.data.model_dump()

    # Enforce the 4-6 question cap and ban multi-part questions even if the
    # LLM didn't comply with the prompt hard rules.
    questions = result.get("questions") or []
    result["questions"] = _dedupe_and_cap_questions(
        questions, injected_must_ask=None, max_total=6, max_llm=6
    )
    return result


async def _process_response(
    charge_data: dict[str, Any],
    phase: str,
    question_id: str,
    question_text: str,
    client_response: str,
    pre_interview_research: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Process a single client response and extract structured data. Raises on failure."""
    phase_abbrev = _PHASE_ABBREVIATIONS.get(phase, "XX")
    charge_summary = _create_charge_summary_for_processing(charge_data)
    pre_interview_context = _summarize_pre_interview_for_phase(pre_interview_research, phase)

    prompt = _RESPONSE_PROCESSING.text.format(
        charge_data_summary=charge_summary,
        pre_interview_context=pre_interview_context,
        phase=phase,
        question_text=question_text,
        question_id=question_id,
        client_response=client_response,
        phase_abbrev=phase_abbrev,
    )

    call = await call_model(
        ModelCallRequest(
            prompt=prompt,
            system=_SYSTEM.text,
            max_tokens=_RESPONSE_MAX_TOKENS,
            response_model=ProcessedResponse,
            prompt_id="intake_conductor.response_processing",
            prompt_version=compose_version(_SYSTEM, _RESPONSE_PROCESSING),
            agent_id="intake_conductor",
        )
    )
    return call.data.model_dump()


async def _analyze_inconsistencies(
    charge_data: dict[str, Any],
    interview_facts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Cross-reference client statements with charge data. Raises on failure."""
    charge_str = json.dumps(charge_data, indent=2, default=str)
    facts_str = json.dumps(interview_facts, indent=2, default=str)

    if len(charge_str) > 50_000:
        charge_str = charge_str[:50_000] + "\n... [TRUNCATED]"
    if len(facts_str) > 50_000:
        facts_str = facts_str[:50_000] + "\n... [TRUNCATED]"

    prompt = _INCONSISTENCY_ANALYSIS.text.format(
        charge_data=charge_str,
        interview_facts=facts_str,
    )

    call = await call_model(
        ModelCallRequest(
            prompt=prompt,
            system=_SYSTEM.text,
            max_tokens=_INCONSISTENCY_MAX_TOKENS,
            response_model=InconsistencyAnalysis,
            prompt_id="intake_conductor.inconsistency_analysis",
            prompt_version=compose_version(_SYSTEM, _INCONSISTENCY_ANALYSIS),
            agent_id="intake_conductor",
        )
    )
    return call.data.model_dump()


def _deduplicate_triggers(triggers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove duplicate sub-agent triggers, keeping highest priority."""
    seen: dict[tuple[str, str], dict[str, Any]] = {}
    priority_order = {"high": 0, "medium": 1, "low": 2}

    for trigger in triggers:
        key = (trigger.get("target_agent", ""), trigger.get("trigger_reason", "")[:50])
        current = priority_order.get(trigger.get("priority", "low"), 2)
        existing = seen.get(key)
        if existing is None or current < priority_order.get(existing.get("priority", "low"), 2):
            seen[key] = trigger

    return list(seen.values())


def _build_subagent_packages(
    triggers: list[dict[str, Any]],
    intake_facts: list[dict[str, Any]],
    charge_data: dict[str, Any],
    inconsistencies: list[dict[str, Any]],
    pre_interview_research: dict[str, Any] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build context packages for each triggered sub-agent."""
    pi = pre_interview_research or {}
    if "data" in pi and "confidence" in pi:
        pi = pi["data"]

    agent_triggers: dict[str, list[dict[str, Any]]] = {}
    for trigger in triggers:
        agent = trigger.get("target_agent", "unknown")
        agent_triggers.setdefault(agent, []).append(trigger)

    packages: dict[str, dict[str, Any]] = {}

    for agent_name, agent_trigger_list in agent_triggers.items():
        base: dict[str, Any] = {
            "target_agent": agent_name,
            "trigger_count": len(agent_trigger_list),
            "triggers": agent_trigger_list,
        }

        if agent_name == "fact_gatherer":
            relevant_facts = [
                f
                for f in intake_facts
                if f.get("category") in ("incident", "personal", "prior_history")
                or f.get("feeds_subagent") == "fact_gatherer"
            ]
            base["context"] = {
                "client_facts": relevant_facts,
                "charge_allegations": charge_data.get("factual_allegations", []),
                "persons_of_interest": charge_data.get("persons_of_interest", []),
                "known_facts_from_documents": pi.get("known_facts_from_documents", []),
                "inconsistencies": [
                    i for i in inconsistencies if i.get("severity") in ("high", "medium")
                ],
                "task": (
                    "Structure the client's account into a chronological timeline. "
                    "Cross-reference with charging document allegations. "
                    "Identify corroborations, contradictions, and gaps."
                ),
            }
        elif agent_name == "rights_violation_scanner":
            relevant_facts = [
                f
                for f in intake_facts
                if f.get("category") in ("arrest", "custody")
                or f.get("feeds_subagent") == "rights_violation_scanner"
            ]
            base["context"] = {
                "client_arrest_custody_facts": relevant_facts,
                "charge_misconduct_flags": charge_data.get("misconduct_flags", []),
                "charge_procedural_flags": charge_data.get("procedural_flags", []),
                "preliminary_rights_flags": pi.get("preliminary_rights_flags", []),
                "arrest_allegations": [
                    a
                    for a in charge_data.get("factual_allegations", [])
                    if a.get("category")
                    in ("arrest_circumstances", "search_and_seizure", "statement_by_defendant")
                ],
                "task": (
                    "Analyze for Fourth Amendment (search/seizure), Fifth Amendment "
                    "(Miranda, coerced statements), and Sixth Amendment (right to counsel) "
                    "violations based on both the client's account and the charging documents. "
                    "Confirm or refute each preliminary rights flag from pre-interview."
                ),
            }
        elif agent_name == "collateral_consequences":
            relevant_facts = [
                f
                for f in intake_facts
                if f.get("category") in ("personal", "priority", "concern")
                or f.get("feeds_subagent") == "collateral_consequences"
            ]
            base["context"] = {
                "client_personal_facts": relevant_facts,
                "charges": [
                    {
                        "count": c.get("count_number"),
                        "description": c.get("charge_description"),
                        "statute": c.get("statute", {}).get("code"),
                        "degree": c.get("degree"),
                    }
                    for c in charge_data.get("charges", [])
                ],
                "defendant_info": charge_data.get("defendant", {}),
                "diversion_eligibility": charge_data.get("diversion_eligibility", {}),
                "collateral_alerts": pi.get("collateral_consequence_alerts", []),
                "task": (
                    "Analyze collateral consequences: immigration, employment, housing, "
                    "family, financial. Build on the collateral alerts already surfaced "
                    "by pre-interview research."
                ),
            }
        else:
            base["context"] = {
                "relevant_facts": intake_facts,
                "task": f"Process trigger for agent: {agent_name}",
            }

        packages[agent_name] = base

    return packages


def _confidence_summary(facts: list[dict[str, Any]]) -> dict[str, int]:
    """Calculate confidence distribution across extracted facts."""
    summary = {"very_high": 0, "high": 0, "medium": 0, "low": 0, "very_low": 0}
    for fact in facts:
        conf = fact.get("confidence", 0.0)
        if isinstance(conf, str):
            try:
                conf = float(conf)
            except (ValueError, TypeError):
                conf = 0.5
        if conf >= 0.9:
            summary["very_high"] += 1
        elif conf >= 0.7:
            summary["high"] += 1
        elif conf >= 0.5:
            summary["medium"] += 1
        elif conf >= 0.3:
            summary["low"] += 1
        else:
            summary["very_low"] += 1
    return summary


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class IntakeConductorAgent(BaseAgent):
    agent_id = "intake_conductor"
    agent_name = "Intake Conductor"

    async def run(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Conduct a full client intake interview.

        Input keys:
            charge_data: dict — output from Charge Processing Agent
            matter_id: str — case/matter identifier
            responses: dict[str, list[dict]] — pre-recorded responses per phase
                Each response: {question_id, question_text, client_response}

        For interactive/WebSocket mode, the agent can be called iteratively
        with partial input. For batch/test mode, all responses are provided
        at once.

        Output: ConfidenceRated dict with intake summary, facts,
            inconsistencies, ethical flags, and sub-agent triggers.
        """
        self.log_action(
            "intake_started",
            {
                "input_keys": list(input_data.keys()),
            },
        )

        charge_data = input_data.get("charge_data", {})
        # Unwrap if the charge data is ConfidenceRated wrapped
        if "data" in charge_data and "confidence" in charge_data:
            charge_data = charge_data["data"]

        pre_interview_research = input_data.get("pre_interview_research", {}) or {}
        # Unwrap ConfidenceRated wrapper if present
        if (
            isinstance(pre_interview_research, dict)
            and "data" in pre_interview_research
            and "confidence" in pre_interview_research
        ):
            pre_interview_research = pre_interview_research["data"]

        matter_id = input_data.get("matter_id", "unknown")
        pre_recorded = input_data.get("responses", {})
        intake_id = f"INTAKE-{uuid.uuid4().hex[:8]}"
        start_time = datetime.now(timezone.utc)

        # Accumulated data
        all_facts: list[dict[str, Any]] = []
        all_inconsistencies: list[dict[str, Any]] = []
        all_ethical_flags: list[dict[str, Any]] = []
        all_subagent_triggers: list[dict[str, Any]] = []
        all_follow_ups: list[dict[str, Any]] = []
        phase_results: dict[str, dict[str, Any]] = {}
        completed_phases: list[str] = []

        for phase in INTERVIEW_PHASES:
            self.log_action("phase_started", {"phase": phase})

            # Generate questions
            previous = [phase_results[p] for p in completed_phases if p in phase_results]
            questions_data = await _generate_questions(
                charge_data=charge_data,
                phase=phase,
                previous_responses=previous if previous else None,
                pre_interview_research=pre_interview_research,
            )

            # Get responses (pre-recorded for batch, or default placeholders)
            responses = pre_recorded.get(phase, [])
            if not responses:
                # Use generated questions as placeholders (interactive mode
                # would collect actual responses via WebSocket)
                self.log_action("phase_skipped_no_responses", {"phase": phase})
                phase_results[phase] = {
                    "phase": phase,
                    "questions_generated": len(questions_data.get("questions", [])),
                    "responses_processed": 0,
                    "facts_extracted": 0,
                }
                completed_phases.append(phase)
                continue

            # Process each response
            phase_facts: list[dict[str, Any]] = []
            phase_inconsistencies: list[dict[str, Any]] = []
            phase_ethical_flags: list[dict[str, Any]] = []
            phase_triggers: list[dict[str, Any]] = []
            phase_follow_ups: list[dict[str, Any]] = []

            for resp in responses:
                processed = await _process_response(
                    charge_data=charge_data,
                    phase=phase,
                    question_id=resp["question_id"],
                    question_text=resp["question_text"],
                    client_response=resp["client_response"],
                    pre_interview_research=pre_interview_research,
                )
                phase_facts.extend(processed.get("extracted_facts", []))
                phase_inconsistencies.extend(processed.get("inconsistencies_with_charges", []))
                phase_ethical_flags.extend(processed.get("ethical_flags", []))
                phase_triggers.extend(processed.get("subagent_triggers", []))
                phase_follow_ups.extend(processed.get("follow_up_questions", []))

            all_facts.extend(phase_facts)
            all_inconsistencies.extend(phase_inconsistencies)
            all_ethical_flags.extend(phase_ethical_flags)
            all_subagent_triggers.extend(phase_triggers)
            all_follow_ups.extend(phase_follow_ups)

            phase_results[phase] = {
                "phase": phase,
                "responses_processed": len(responses),
                "facts_extracted": len(phase_facts),
                "inconsistencies_found": len(phase_inconsistencies),
                "ethical_flags_raised": len(phase_ethical_flags),
                "subagent_triggers": len(phase_triggers),
                "facts": phase_facts,
                "inconsistencies": phase_inconsistencies,
                "ethical_flags": phase_ethical_flags,
                "triggers": phase_triggers,
                "follow_ups": phase_follow_ups,
            }
            completed_phases.append(phase)

            # Log urgent ethical flags
            for flag in phase_ethical_flags:
                if flag.get("urgency") == "immediate":
                    logger.warning(
                        "IMMEDIATE ETHICAL FLAG in phase '%s': %s \u2014 %s",
                        phase,
                        flag.get("flag_type"),
                        flag.get("description"),
                    )

        # Post-interview inconsistency analysis
        inconsistency_analysis: dict[str, Any] = {}
        if all_facts:
            inconsistency_analysis = await _analyze_inconsistencies(charge_data, all_facts)

        # Deduplicate triggers and build sub-agent packages
        deduped_triggers = _deduplicate_triggers(all_subagent_triggers)
        subagent_packages = _build_subagent_packages(
            deduped_triggers,
            all_facts,
            charge_data,
            inconsistency_analysis.get("inconsistencies", []),
            pre_interview_research=pre_interview_research,
        )

        # Tag low-confidence facts
        review_required: list[dict[str, Any]] = []
        for fact in all_facts:
            conf = fact.get("confidence", 1.0)
            if isinstance(conf, str):
                try:
                    conf = float(conf)
                except (ValueError, TypeError):
                    conf = 0.5
            if conf < _REVIEW_THRESHOLD:
                fact["review_required"] = True
                review_required.append(fact)

        elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()

        intake_output = {
            "_disclaimer": (
                "This information is not legal advice and was collected for "
                "informational purposes only. Please consult your attorney "
                "before relying on any of it."
            ),
            "intake_id": intake_id,
            "matter_id": matter_id,
            "processing_timestamp": datetime.now(timezone.utc).isoformat(),
            "defendant": charge_data.get("defendant", {}),
            "charges_context": [
                {
                    "count_number": c.get("count_number"),
                    "charge_description": c.get("charge_description"),
                    "statute_code": c.get("statute", {}).get("code"),
                    "degree": c.get("degree"),
                }
                for c in charge_data.get("charges", [])
            ],
            "interview_phases": phase_results,
            "extracted_facts": all_facts,
            "inconsistencies_with_charges": all_inconsistencies,
            "inconsistency_analysis": inconsistency_analysis,
            "ethical_flags": all_ethical_flags,
            "subagent_triggers": deduped_triggers,
            "subagent_packages": subagent_packages,
            "pending_follow_ups": all_follow_ups,
            "new_defense_angles": inconsistency_analysis.get("new_defense_angles", []),
            "pre_interview_context": {
                "integrated": bool(pre_interview_research),
                "targeted_questions_count": (
                    len(pre_interview_research.get("targeted_questions", []))
                    if pre_interview_research
                    else 0
                ),
                "preliminary_rights_flags_count": (
                    len(pre_interview_research.get("preliminary_rights_flags", []))
                    if pre_interview_research
                    else 0
                ),
                "collateral_alerts_count": (
                    len(pre_interview_research.get("collateral_consequence_alerts", []))
                    if pre_interview_research
                    else 0
                ),
                "known_facts_count": (
                    len(pre_interview_research.get("known_facts_from_documents", []))
                    if pre_interview_research
                    else 0
                ),
            },
            "processing_metadata": {
                "agent_version": "1.0.0",
                "total_processing_time_seconds": round(elapsed, 2),
                "phases_completed": completed_phases,
                "total_facts_extracted": len(all_facts),
                "total_inconsistencies": len(all_inconsistencies),
                "total_ethical_flags": len(all_ethical_flags),
                "total_subagent_triggers": len(deduped_triggers),
                "review_required_count": len(review_required),
                "confidence_summary": _confidence_summary(all_facts),
            },
        }

        # Compute overall confidence from fact distribution
        conf_summary = intake_output["processing_metadata"]["confidence_summary"]
        total = sum(conf_summary.values())
        if total > 0:
            weights = {"very_high": 0.95, "high": 0.8, "medium": 0.6, "low": 0.4, "very_low": 0.15}
            weighted = sum(conf_summary.get(k, 0) * v for k, v in weights.items())
            overall_confidence = round(weighted / total, 3)
        else:
            overall_confidence = 0.7

        self.log_action(
            "intake_completed",
            {
                "phases_completed": len(completed_phases),
                "facts_extracted": len(all_facts),
                "ethical_flags": len(all_ethical_flags),
                "overall_confidence": overall_confidence,
            },
        )

        return self.wrap_output(intake_output, confidence=overall_confidence)
