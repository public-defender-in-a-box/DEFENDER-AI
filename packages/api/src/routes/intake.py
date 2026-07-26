"""Intake WebSocket endpoint for client chat."""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.agents.tier1.intake_conductor import (
    INTERVIEW_PHASES,
    IntakeConductorAgent,
    _DEFAULT_QUESTIONS,
    _generate_questions,
    _process_response,
)
from src.routes._store import case_store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["intake"])


@router.websocket("/ws/intake/{session_id}")
async def intake_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time client intake chat.

    Walks the client through each interview phase, sending one question at
    a time and processing each response through the Intake Conductor's
    response-processing pipeline.  When all phases are complete the
    session is finalized and the WebSocket is closed.
    """
    await websocket.accept()

    await websocket.send_json(
        {
            "sender": "SYSTEM",
            "content": (
                "Welcome. This conversation is protected by attorney-client privilege. "
                "This system helps gather information for your attorney. "
                "It does not provide legal advice."
            ),
        }
    )

    orchestrator = case_store.get(session_id)
    charge_data: dict = {}
    if orchestrator and orchestrator.case_state:
        raw = orchestrator.case_state.charge_processing or {}
        charge_data = raw.get("data", raw) if "data" in raw and "confidence" in raw else raw

    collected_responses: dict[str, list[dict]] = {}

    try:
        for phase in INTERVIEW_PHASES:
            try:
                questions_data = await _generate_questions(charge_data, phase)
            except Exception:
                logger.exception("Question generation failed for phase %s", phase)
                questions_data = {
                    "questions": _DEFAULT_QUESTIONS.get(phase, []),
                }

            questions = questions_data.get("questions", _DEFAULT_QUESTIONS.get(phase, []))
            if not questions:
                continue

            phase_responses: list[dict] = []

            for question in questions:
                q_id = question.get("question_id", "Q-UNKNOWN")
                q_text = question.get("question_text", "")

                await websocket.send_json(
                    {
                        "sender": "AGENT",
                        "phase": phase,
                        "question_id": q_id,
                        "content": q_text,
                    }
                )

                client_message = await websocket.receive_text()

                phase_responses.append(
                    {
                        "question_id": q_id,
                        "question_text": q_text,
                        "client_response": client_message,
                    }
                )

                try:
                    processed = await _process_response(
                        charge_data=charge_data,
                        phase=phase,
                        question_id=q_id,
                        question_text=q_text,
                        client_response=client_message,
                    )
                    for flag in processed.get("ethical_flags", []):
                        if flag.get("urgency") == "immediate":
                            await websocket.send_json(
                                {
                                    "sender": "SYSTEM",
                                    "content": (
                                        "Thank you for sharing that. I'm noting this for "
                                        "your attorney's immediate attention."
                                    ),
                                }
                            )
                except Exception:
                    logger.exception("Response processing failed for %s", q_id)

            collected_responses[phase] = phase_responses

        # Run the full agent with all collected responses to produce merged output
        agent = IntakeConductorAgent()
        result = await agent.run(
            {
                "charge_data": charge_data,
                "matter_id": session_id,
                "responses": collected_responses,
            }
        )

        if orchestrator:
            can_run, _ = orchestrator.can_run_agent("intake_conductor")
            if can_run:
                orchestrator.mark_agent_started("intake_conductor")
                await orchestrator.receive_agent_output("intake_conductor", result)
                logger.info("Intake complete for session %s", session_id)

        await websocket.send_json(
            {
                "sender": "SYSTEM",
                "content": (
                    "Thank you for answering all of our questions. "
                    "Your attorney will review this information. "
                    "This session is now complete."
                ),
            }
        )
        await websocket.close()

    except WebSocketDisconnect:
        logger.info("Client disconnected from intake session %s", session_id)
    except Exception:
        logger.exception("Unexpected error in intake session %s", session_id)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
