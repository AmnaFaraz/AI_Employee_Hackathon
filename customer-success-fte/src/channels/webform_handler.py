"""
Web Form Channel Handler — Customer Success Digital FTE

Processes support form submissions from the Next.js embeddable widget.
Handles real-time WebSocket connections for live chat.
"""
from __future__ import annotations

import asyncio
import logging
import uuid
from collections import defaultdict
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field, EmailStr, field_validator

from src.agent.agent import IncomingMessage, CustomerSuccessAgent
from src.database.connection import get_session
from src.database.models import ChannelType

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pydantic request/response schemas
# ---------------------------------------------------------------------------

class WebFormSubmission(BaseModel):
    """Inbound support form submission payload."""
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    subject: str = Field(..., min_length=1, max_length=500)
    message: str = Field(..., min_length=1, max_length=5000)
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("message")
    @classmethod
    def message_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Message cannot be empty")
        return v.strip()


class WebFormChatMessage(BaseModel):
    """Real-time chat message over WebSocket."""
    session_id: str
    content: str = Field(..., min_length=1, max_length=5000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class WebFormResponse(BaseModel):
    """API response for form submissions."""
    success: bool
    session_id: str
    message: str
    ticket_number: int | None = None
    estimated_response_time: str = "under 30 seconds"


# ---------------------------------------------------------------------------
# WebSocket connection manager (for real-time chat)
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Manages active WebSocket connections for the live chat widget."""

    def __init__(self):
        # session_id → list of WebSocket connections (multi-tab support)
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, session_id: str) -> None:
        await websocket.accept()
        self._connections[session_id].append(websocket)
        logger.info("WebSocket connected | session=%s | total=%d", session_id, len(self._connections[session_id]))

    def disconnect(self, websocket: WebSocket, session_id: str) -> None:
        connections = self._connections.get(session_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self._connections.pop(session_id, None)
        logger.info("WebSocket disconnected | session=%s", session_id)

    async def send_to_session(self, session_id: str, message: dict) -> None:
        """Send a message to all connections for a session."""
        connections = self._connections.get(session_id, [])
        dead = []
        for ws in connections:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws, session_id)

    async def broadcast(self, message: dict) -> None:
        """Broadcast to all active sessions (e.g., system announcements)."""
        tasks = [
            self.send_to_session(sid, message)
            for sid in list(self._connections.keys())
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

    @property
    def active_sessions(self) -> int:
        return len(self._connections)


# Module-level singleton
connection_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# WebForm handler
# ---------------------------------------------------------------------------

class WebFormHandler:
    """Processes web form submissions and manages live chat sessions."""

    def __init__(self, agent: CustomerSuccessAgent | None = None):
        """
        Args:
            agent: CustomerSuccessAgent instance for direct processing.
        """
        self._agent = agent or CustomerSuccessAgent()

    async def handle_submission(self, submission: WebFormSubmission) -> WebFormResponse:
        """Process a standard (non-real-time) form submission."""
        try:
            incoming = IncomingMessage(
                channel=ChannelType.WEB_FORM,
                sender_id=submission.email,
                content=f"Subject: {submission.subject}\n\n{submission.message}",
                sender_name=submission.name,
                channel_thread_id=submission.session_id,
                channel_context={
                    "session_id": submission.session_id,
                    "email": submission.email,
                    "name": submission.name,
                    "subject": submission.subject,
                    "metadata": submission.metadata,
                },
            )

            async with get_session() as session:
                response = await self._agent.process(incoming, session)

            logger.info(
                "Web form submission processed directly | email=%s | ticket_id=%s",
                submission.email,
                response.ticket_id,
            )

            return WebFormResponse(
                success=True,
                session_id=submission.session_id,
                message=(
                    "Thank you! We've received your message and our AI assistant "
                    "is working on your response right now."
                ),
            )

        except Exception as exc:
            logger.error("Web form submission failed: %s", exc)
            return WebFormResponse(
                success=False,
                session_id=submission.session_id,
                message="We encountered an issue. Please try again or email us directly.",
            )

    async def handle_chat_message(
        self,
        chat_msg: WebFormChatMessage,
    ) -> str:
        """Process a real-time chat message from a WebSocket connection."""
        incoming = IncomingMessage(
            channel=ChannelType.WEB_FORM,
            sender_id=chat_msg.session_id,
            content=chat_msg.content,
            channel_thread_id=chat_msg.session_id,
            channel_context={
                "session_id": chat_msg.session_id,
                "real_time": True,
            },
        )

        async with get_session() as session:
            response = await self._agent.process(incoming, session)

        # Acknowledge receipt and send response back if WebSocket is used for real-time interaction
        # However, the worker usually handles the response sending.
        # Here we send the agent's response back directly since we're bypassing the queue.
        await self.send_agent_response_to_websocket(
            session_id=chat_msg.session_id,
            response_content=response.content,
            ticket_number=response.ticket_number,
            was_escalated=response.was_escalated,
        )

        return str(response.ticket_id or uuid.uuid4())

    async def send_agent_response_to_websocket(
        self,
        session_id: str,
        response_content: str,
        ticket_number: int | None = None,
        was_escalated: bool = False,
    ) -> None:
        """Push agent response back to the customer's WebSocket session."""
        payload = {
            "type": "agent_response",
            "content": response_content,
            "ticket_number": ticket_number,
            "was_escalated": was_escalated,
        }
        await connection_manager.send_to_session(session_id, payload)
