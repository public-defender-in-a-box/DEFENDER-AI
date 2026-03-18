"""Intake WebSocket endpoint for client chat."""

from fastapi import APIRouter, WebSocket

router = APIRouter(tags=["intake"])


@router.websocket("/ws/intake/{session_id}")
async def intake_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time client intake chat.

    The Intake Conductor agent processes each message and generates
    the next question dynamically.
    """
    await websocket.accept()

    # Send initial disclaimer
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

    try:
        while True:
            _client_message = await websocket.receive_text()
            # TODO: Route _client_message to Intake Conductor agent
            await websocket.send_json(
                {
                    "sender": "SYSTEM",
                    "content": "Thank you. Processing your response...",
                }
            )
    except Exception:
        pass
