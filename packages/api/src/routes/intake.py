"""Intake WebSocket endpoint for interactive client interview."""

from __future__ import annotations

import asyncio
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.agents.tier1.case_prep import CasePrepAgent
from src.agents.tier1.intake_conductor import (
    INTERVIEW_PHASES,
    IntakeConductorAgent,
    _DEFAULT_QUESTIONS,
    _generate_questions,
    _process_response,
)
from src.models.case_state import PipelineStage
from src.routes._store import case_store
from src.services.llm_service import call_llm

logger = logging.getLogger(__name__)

router = APIRouter(tags=["intake"])

# Phase labels for display
_PHASE_LABELS: dict[str, str] = {
    "personal_information": "Personal Information",
    "incident_narrative": "What Happened",
    "arrest_and_custody": "Arrest & Custody",
    "prior_history": "Prior History",
    "priorities_and_concerns": "Your Priorities",
}

_TOTAL_PHASES = len(INTERVIEW_PHASES)


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

@dataclass
class IntakeSession:
    case_id: str
    charge_data: dict[str, Any]
    pre_interview_data: dict[str, Any] = field(default_factory=dict)
    phase_index: int = 0
    question_index: int = 0
    question_queue: list[dict[str, Any]] = field(default_factory=list)
    total_questions_all_phases: int = 0
    responses: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    all_facts: list[dict[str, Any]] = field(default_factory=list)
    completed: bool = False


_sessions: dict[str, IntakeSession] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _msg(
    msg_type: str,
    content: str,
    sender: str = "SYSTEM",
    **extra: Any,
) -> dict[str, Any]:
    """Build a server-to-client message envelope."""
    return {
        "type": msg_type,
        "content": content,
        "sender": sender,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "messageId": str(uuid.uuid4()),
        **extra,
    }


def _progress(session: IntakeSession) -> dict[str, Any]:
    """Build a progress update message."""
    phase = INTERVIEW_PHASES[session.phase_index] if session.phase_index < _TOTAL_PHASES else ""
    answered_total = sum(len(r) for r in session.responses.values())
    total_est = max(session.total_questions_all_phases, answered_total, 1)

    if session.completed or session.phase_index >= _TOTAL_PHASES:
        pct = 100
    else:
        pct = min(int((answered_total / total_est) * 100), 99)

    return _msg(
        "progress",
        "",
        phaseName=_PHASE_LABELS.get(phase, phase),
        phaseIndex=session.phase_index,
        totalPhases=_TOTAL_PHASES,
        questionsAnswered=session.phase_index,
        completionPercentage=pct,
    )


def _phase_for_targeted_question(tq: dict[str, Any]) -> str:
    """Return the interview phase a targeted question belongs to.

    Honors the `phase` field the Pre-Interview Research agent stamps on every
    targeted question. Falls back to `"incident_narrative"` only if the field
    is missing or invalid.
    """
    phase = tq.get("phase")
    if isinstance(phase, str) and phase in INTERVIEW_PHASES:
        return phase
    return "incident_narrative"


def _inject_targeted_questions(
    questions: list[dict[str, Any]],
    targeted: list[dict[str, Any]],
    phase: str,
) -> list[dict[str, Any]]:
    """Merge pre-interview targeted questions into the generated question list.

    MUST_ASK questions are prepended (asked first). SHOULD_ASK and IF_TIME
    questions are appended after the LLM-generated ones.
    """
    existing_texts = {q.get("question_text", "").lower() for q in questions}
    prepend: list[dict[str, Any]] = []
    append: list[dict[str, Any]] = []
    added = 0

    for tq in targeted:
        q_text = tq.get("question", "")
        if not q_text or q_text.lower() in existing_texts:
            continue

        # Only include questions classified for this phase
        if _phase_for_targeted_question(tq) != phase:
            continue

        priority = (tq.get("priority") or "SHOULD_ASK").upper()
        entry = {
            "question_id": f"Q-TQ-{added + 1:03d}",
            "question_text": q_text,
            "question_type": "open_ended",
            "priority": (
                "required" if priority == "MUST_ASK"
                else "recommended" if priority == "SHOULD_ASK"
                else "optional"
            ),
            "rationale": tq.get("rationale")
            or tq.get("relevant_element")
            or "From pre-interview research",
            "follow_up_triggers": [],
            "related_charges": [],
            "feeds_subagent": "fact_gatherer",
        }

        if priority == "MUST_ASK":
            prepend.append(entry)
        else:
            # SHOULD_ASK and IF_TIME both go after the LLM-generated questions
            append.append(entry)

        existing_texts.add(q_text.lower())
        added += 1

    # MUST_ASK first, then LLM-generated, then SHOULD_ASK + IF_TIME
    return prepend + questions + append


async def _generate_turn_message(
    client_response: str,
    question_text: str,
    next_question: str | None,
) -> str:
    """Use LLM to generate a warm acknowledgment that flows into the next question.

    Hard rule: the model may NOT add any additional questions, follow-ups, or
    clarifications. It returns ``<short ack>. <next_question verbatim>``.
    """
    if next_question is None:
        return "Thank you for sharing all of that. We're finished with the interview."

    prompt = f"""You are an intake assistant for a public defender's office.
The client just answered a question. Write ONE very short acknowledgment
(3-8 words, no advice, no repetition of their words), then ask ONE next
question — the one given below — EXACTLY as written.

HARD RULES:
- Output ONLY: <short ack>. <next question verbatim>
- Do NOT add any follow-up, clarification, or second question.
- Do NOT rephrase or shorten the next question.
- Do NOT combine questions with "and".
- Your whole response must contain exactly ONE question mark.

CLIENT SAID: "{client_response}"
NEXT QUESTION TO ASK (use verbatim): "{next_question}"

Return JSON: {{"combined_message": "short ack. {next_question}"}}"""

    try:
        result = await call_llm(prompt, max_tokens=256)
        combined = result.get("combined_message") or ""
        # Safety net: if the LLM added extra questions, fall back to a
        # minimal acknowledgment + the verbatim next question.
        if combined.count("?") > 1 or next_question not in combined:
            return f"Thank you. {next_question}"
        return combined
    except Exception:
        logger.exception("Turn message LLM failed, using raw question")
        return f"Thank you. {next_question}"


# ---------------------------------------------------------------------------
# REST validation endpoint (used by frontend landing page)
# ---------------------------------------------------------------------------

@router.get("/intake/{case_id}/validate")
async def validate_intake_session(case_id: str) -> dict[str, Any]:
    """Check if a case is ready for intake interview."""
    orch = case_store.get(case_id)
    if not orch:
        return {"valid": False, "error": "Case not found"}

    if orch.case_state is None:
        return {"valid": False, "error": "Case not initialized"}

    stage = orch.case_state.stage
    allowed = {PipelineStage.PRE_INTERVIEW_COMPLETE, PipelineStage.INTAKE_IN_PROGRESS}
    if stage not in allowed:
        return {
            "valid": False,
            "error": f"Case is at stage {stage.value}, not ready for intake",
        }

    return {"valid": True, "caseId": case_id, "stage": stage.value}


@router.post("/intake/{case_id}/finalize")
async def finalize_stuck_interview(case_id: str) -> dict[str, Any]:
    """Manually finalize an intake interview stuck at INTAKE_IN_PROGRESS."""
    orch = case_store.get(case_id)
    if not orch or orch.case_state is None:
        return {"error": "Case not found"}

    if orch.case_state.stage != PipelineStage.INTAKE_IN_PROGRESS:
        return {"error": f"Case is at {orch.case_state.stage.value}, not INTAKE_IN_PROGRESS"}

    session = _sessions.get(case_id)
    if not session:
        # No session data — create minimal responses to advance pipeline
        logger.warning("No session data for %s, using empty responses", case_id)
        charge_output = orch.case_state.charge_processing or {}
        charge_data = charge_output.get("data", charge_output)
        pi_output = orch.case_state.pre_interview_research or {}
        pre_interview_data = pi_output.get("data", pi_output) if isinstance(pi_output, dict) else {}
        responses: dict[str, list[dict[str, Any]]] = {p: [] for p in INTERVIEW_PHASES}
    else:
        charge_data = session.charge_data
        pre_interview_data = session.pre_interview_data
        responses = session.responses

    conductor = IntakeConductorAgent()
    result = await conductor.run({
        "charge_data": charge_data,
        "matter_id": case_id,
        "responses": responses,
        "pre_interview_research": pre_interview_data or {},
    })

    merge_result = await orch.receive_agent_output("intake_conductor", result)

    # Run Case Prep best-effort; don't fail the endpoint if it errors.
    case_prep_decision: str | None = None
    try:
        case_prep_result = await CasePrepAgent().run(
            {"case_state": orch.get_case_state_snapshot()}
        )
        case_prep_merge = await orch.receive_agent_output(
            "case_prep_conductor", case_prep_result
        )
        case_prep_decision = case_prep_merge.get("decision")
    except Exception:
        logger.exception("CasePrepAgent failed during manual finalize for %s", case_id)

    return {
        "status": "finalized",
        "case_id": case_id,
        "stage": orch.case_state.stage.value,
        "decision": merge_result.get("decision"),
        "case_prep_decision": case_prep_decision,
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/intake/{session_id}")
async def intake_websocket(websocket: WebSocket, session_id: str) -> None:
    """WebSocket endpoint for real-time client intake interview.

    Protocol:
        Server -> Client: {type, content, sender, timestamp, messageId, ...}
        Client -> Server: plain text
    """
    await websocket.accept()

    # --- 1. Validate case ---
    orch = case_store.get(session_id)
    if not orch or orch.case_state is None:
        await websocket.send_json(_msg("error", "Case not found. Please check your session code."))
        await websocket.close(code=4004)
        return

    allowed_stages = {PipelineStage.PRE_INTERVIEW_COMPLETE, PipelineStage.INTAKE_IN_PROGRESS}
    if orch.case_state.stage not in allowed_stages:
        await websocket.send_json(
            _msg("error", f"This case is not ready for intake (stage: {orch.case_state.stage.value}).")
        )
        await websocket.close(code=4003)
        return

    # --- 2. Extract charge data and pre-interview research ---
    charge_output = orch.case_state.charge_processing or {}
    charge_data: dict[str, Any] = charge_output.get("data", charge_output)

    pi_output = orch.case_state.pre_interview_research or {}
    pre_interview_data: dict[str, Any] = pi_output.get("data", pi_output)

    # Check for existing session (reconnection)
    existing = _sessions.get(session_id)
    if existing and not existing.completed:
        session = existing
        await websocket.send_json(
            _msg("system", "Welcome back. Let's continue where we left off.")
        )
        await websocket.send_json(_progress(session))

        # Re-send the current question
        if session.phase_index < _TOTAL_PHASES and session.question_queue:
            if session.question_index < len(session.question_queue):
                current_q = session.question_queue[session.question_index]["question_text"]
                phase_label = _PHASE_LABELS.get(INTERVIEW_PHASES[session.phase_index], "")
                await websocket.send_json(
                    _msg("message", f"{phase_label}: {current_q}", sender="SYSTEM")
                )
    else:
        # Fresh session
        if orch.case_state.stage == PipelineStage.PRE_INTERVIEW_COMPLETE:
            orch.mark_agent_started("intake_conductor")

        session = IntakeSession(
            case_id=session_id,
            charge_data=charge_data,
            pre_interview_data=pre_interview_data,
        )
        for phase in INTERVIEW_PHASES:
            session.responses[phase] = []
        _sessions[session_id] = session

        # --- 3. Send disclaimer ---
        await websocket.send_json(
            _msg(
                "system",
                "Welcome. This conversation is protected by attorney-client privilege. "
                "This system helps gather information for your attorney. "
                "It does not provide legal advice.\n\n"
                "We'll go through a few topics to understand your situation. "
                "Take your time — there are no wrong answers.",
            )
        )

        # --- 4. Generate first phase questions and send first question ---
        try:
            await _start_phase(websocket, session)
        except Exception:
            logger.exception("Failed to start first phase")
            await websocket.send_json(_msg("error", "Failed to initialize interview. Please try again."))
            await websocket.close(code=1011)
            return

    # --- 5. Message loop ---
    try:
        while True:
            client_text = await websocket.receive_text()

            if session.completed:
                await websocket.send_json(
                    _msg("system", "The interview is already complete. Thank you for your time.")
                )
                continue

            await _handle_client_message(websocket, session, client_text, orch)

    except WebSocketDisconnect:
        logger.info("Client disconnected from intake session %s", session_id)
    except Exception:
        logger.exception("Unexpected error in intake session %s", session_id)
        try:
            await websocket.send_json(_msg("error", "An unexpected error occurred."))
        except Exception:
            pass


async def _start_phase(websocket: WebSocket, session: IntakeSession) -> None:
    """Generate questions for the current phase and send the first one."""
    phase = INTERVIEW_PHASES[session.phase_index]
    previous: list[dict[str, Any]] = []
    for prev_phase in INTERVIEW_PHASES[: session.phase_index]:
        previous.extend(session.responses.get(prev_phase, []))

    questions_data = await _generate_questions(
        charge_data=session.charge_data,
        phase=phase,
        previous_responses=previous if previous else None,
        pre_interview_research=session.pre_interview_data or None,
    )

    questions = questions_data.get("questions", [])

    # Inject relevant targeted questions from pre-interview research
    targeted = session.pre_interview_data.get("targeted_questions", [])
    if targeted:
        questions = _inject_targeted_questions(questions, targeted, phase)

    # If we still have nothing, fall back to defaults + injected targeted
    # questions instead of silently skipping the phase.
    if not questions:
        logger.warning(
            "No questions generated for phase %s; falling back to defaults", phase
        )
        defaults = list(_DEFAULT_QUESTIONS.get(phase, []))
        if targeted:
            defaults = _inject_targeted_questions(defaults, targeted, phase)
        questions = defaults

    # Global cap: hard-limit a phase to 8 questions total. Preserve order so
    # MUST_ASK (prepended) always wins. This is a safety net in case the LLM
    # generated more than 6 or the targeted-question injection pushed us over.
    _MAX_QUESTIONS_PER_PHASE = 8
    if len(questions) > _MAX_QUESTIONS_PER_PHASE:
        logger.info(
            "Capping phase %s from %d to %d questions",
            phase,
            len(questions),
            _MAX_QUESTIONS_PER_PHASE,
        )
        questions = questions[:_MAX_QUESTIONS_PER_PHASE]

    session.question_queue = questions
    session.question_index = 0
    session.total_questions_all_phases += len(questions)

    if not session.question_queue:
        # Truly nothing to ask (no defaults either) — advance to next phase.
        logger.warning(
            "No questions and no defaults for phase %s, skipping", phase
        )
        session.phase_index += 1
        if session.phase_index < _TOTAL_PHASES:
            await _start_phase(websocket, session)
        return

    # Send phase intro + first question
    phase_label = _PHASE_LABELS.get(phase, phase)
    first_q = session.question_queue[0]["question_text"]
    intro = f"Let's talk about: {phase_label}\n\n{first_q}"

    await websocket.send_json(_msg("message", intro, sender="SYSTEM"))
    await websocket.send_json(_progress(session))


async def _handle_client_message(
    websocket: WebSocket,
    session: IntakeSession,
    client_text: str,
    orch: Any,
) -> None:
    """Process a single client response and advance the interview."""
    phase = INTERVIEW_PHASES[session.phase_index]
    current_q = session.question_queue[session.question_index]
    question_id = current_q.get("question_id", f"Q-{session.question_index}")
    question_text = current_q["question_text"]

    # Record the response
    session.responses[phase].append({
        "question_id": question_id,
        "question_text": question_text,
        "client_response": client_text,
    })

    # Process response in background (extract facts, flags)
    asyncio.create_task(
        _background_process_response(session, phase, question_id, question_text, client_text)
    )

    # Advance question index
    session.question_index += 1

    if session.question_index < len(session.question_queue):
        # More questions in this phase
        next_q = session.question_queue[session.question_index]["question_text"]
        turn_msg = await _generate_turn_message(client_text, question_text, next_q)
        await websocket.send_json(_msg("message", turn_msg, sender="SYSTEM"))
        await websocket.send_json(_progress(session))

    else:
        # Phase complete — advance to next phase
        session.phase_index += 1

        if session.phase_index < _TOTAL_PHASES:
            next_phase_label = _PHASE_LABELS.get(INTERVIEW_PHASES[session.phase_index], "")
            await websocket.send_json(
                _msg(
                    "message",
                    f"Thank you — that section is complete. Next, we'll cover: {next_phase_label}",
                    sender="SYSTEM",
                )
            )
            await websocket.send_json(_progress(session))
            await _start_phase(websocket, session)

        else:
            # All phases done — run final processing
            await websocket.send_json(
                _msg(
                    "system",
                    "Thank you for completing the interview. "
                    "We're now preparing your information for your attorney. "
                    "This may take a moment...",
                )
            )
            await websocket.send_json(_progress(session))

            try:
                await _finalize_interview(websocket, session, orch)
            except Exception:
                logger.exception("Failed to finalize interview for %s", session.case_id)
                await websocket.send_json(
                    _msg("error", "There was an issue finalizing the interview, but your responses have been saved.")
                )


async def _background_process_response(
    session: IntakeSession,
    phase: str,
    question_id: str,
    question_text: str,
    client_response: str,
) -> None:
    """Process a response in background to extract facts (non-blocking)."""
    try:
        result = await _process_response(
            charge_data=session.charge_data,
            phase=phase,
            question_id=question_id,
            question_text=question_text,
            client_response=client_response,
            pre_interview_research=session.pre_interview_data or None,
        )
        session.all_facts.extend(result.get("extracted_facts", []))
    except Exception:
        logger.exception("Background response processing failed for %s", question_id)


async def _finalize_interview(
    websocket: WebSocket,
    session: IntakeSession,
    orch: Any,
) -> None:
    """Run the full IntakeConductorAgent batch processing and advance the pipeline."""
    session.completed = True
    logger.info("Starting finalization for case %s with %d phases of responses",
                session.case_id, len(session.responses))

    conductor = IntakeConductorAgent()
    try:
        result = await conductor.run({
            "charge_data": session.charge_data,
            "matter_id": session.case_id,
            "responses": session.responses,
            "pre_interview_research": session.pre_interview_data or {},
        })
        logger.info("IntakeConductorAgent.run() completed for %s — keys: %s",
                     session.case_id, list(result.keys()) if isinstance(result, dict) else type(result))
    except Exception:
        logger.exception("IntakeConductorAgent.run() FAILED for %s", session.case_id)
        raise

    # Feed output to orchestrator to advance pipeline -> INTAKE_COMPLETE
    try:
        merge_result = await orch.receive_agent_output("intake_conductor", result)
        logger.info(
            "Intake finalized for %s — merge decision: %s",
            session.case_id,
            merge_result.get("decision"),
        )
    except Exception:
        logger.exception("receive_agent_output FAILED for %s", session.case_id)
        raise

    await websocket.send_json(
        _msg(
            "system",
            "Thank you. We're preparing your information for your attorney now...",
        )
    )

    # Kick off Case Prep Conductor automatically. If it fails, intake still
    # counts as successful — we just log and tell the client their info is
    # saved.
    try:
        case_prep_result = await CasePrepAgent().run(
            {"case_state": orch.get_case_state_snapshot()}
        )
        await orch.receive_agent_output("case_prep_conductor", case_prep_result)
        logger.info("CasePrepAgent completed for %s", session.case_id)
        await websocket.send_json(
            _msg(
                "complete",
                "Your interview is complete and your case prep has been drafted. "
                "Your attorney will review this information and reach out with next "
                "steps. Thank you for your time.",
            )
        )
    except Exception:
        logger.exception("CasePrepAgent failed for %s", session.case_id)
        await websocket.send_json(
            _msg(
                "system",
                "Your information has been saved. Your attorney will be notified. "
                "Thank you for your time.",
            )
        )
        await websocket.send_json(
            _msg(
                "complete",
                "Your interview is complete. Thank you.",
            )
        )
