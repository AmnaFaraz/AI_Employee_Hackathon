"""
Channel Intake Router — Customer Success Digital FTE

Endpoints for receiving incoming messages from all three channels:
  POST /api/v1/channels/email/webhook     — Gmail push notification
  POST /api/v1/channels/whatsapp/webhook  — Twilio WhatsApp webhook
  POST /api/v1/channels/webform/submit    — Web support form submission
  WS   /api/v1/channels/webform/chat      — WebSocket live chat
"""
from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel

from src.channels.gmail_handler import get_gmail_handler
from src.channels.whatsapp_handler import get_whatsapp_handler
from src.channels.webform_handler import (
    WebFormSubmission, WebFormChatMessage, WebFormResponse,
    WebFormHandler, connection_manager,
)
from src.agent.agent import CustomerSuccessAgent, IncomingMessage
from src.database.connection import get_session
from src.database.models import ChannelType
# from src.workers.producer import get_producer

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def _get_webform_handler() -> WebFormHandler:
    # producer = await get_producer()
    return WebFormHandler()


# ---------------------------------------------------------------------------
# Gmail Email Webhook
# ---------------------------------------------------------------------------

@router.post(
    "/email/webhook",
    status_code=status.HTTP_200_OK,
    summary="Gmail Pub/Sub push notification receiver",
)
async def gmail_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
) -> dict[str, str]:
    """
    Receives Gmail push notifications from Google Pub/Sub.
    Parses new emails and publishes them to Kafka for agent processing.
    """
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    gmail = get_gmail_handler()
    parsed = gmail.parse_webhook_payload(payload)

    if not parsed:
        # Ack to Pub/Sub to avoid repeated delivery of bad messages
        return {"status": "ignored"}

    async def _process_new_emails():
        try:
            # producer = await get_producer()
            agent = CustomerSuccessAgent()
            messages = gmail.get_new_messages(parsed["history_id"])

            for msg in messages:
                incoming = IncomingMessage(
                    channel=ChannelType.EMAIL,
                    sender_id=msg["sender_email"],
                    content=f"Subject: {msg['subject']}\n\n{msg['body']}",
                    sender_name=msg["sender_name"],
                    channel_thread_id=msg["thread_id"],
                    channel_message_id=msg["message_id"],
                    channel_context={
                        "to_email": msg["sender_email"],
                        "subject": msg["subject"],
                        "thread_id": msg["thread_id"],
                    },
                )
                async with get_session() as session:
                    await agent.process(incoming, session)
                logger.info("Email processed directly: %s", msg["message_id"])
        except Exception as exc:
            logger.error("Background email processing failed: %s", exc)

    background_tasks.add_task(_process_new_emails)
    return {"status": "accepted"}


# ---------------------------------------------------------------------------
# WhatsApp Webhook
# ---------------------------------------------------------------------------

@router.post(
    "/whatsapp/webhook",
    status_code=status.HTTP_200_OK,
    summary="Twilio WhatsApp webhook receiver",
)
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_twilio_signature: str = Header(default="", alias="X-Twilio-Signature"),
) -> Any:
    """
    Receives Twilio WhatsApp webhook events.
    Returns TwiML-compatible response (<Response/>) immediately;
    actual AI processing happens asynchronously.
    """
    form_data = await request.form()
    form_dict = dict(form_data)

    # Validate Twilio signature in production
    if os.environ.get("ENV", "production") == "production":
        handler = get_whatsapp_handler()
        url = str(request.url)
        if not handler.validate_signature(url, form_dict, x_twilio_signature):
            raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    handler = get_whatsapp_handler()
    parsed = handler.parse_webhook(form_dict)

    if not parsed:
        return {"status": "ignored"}

    async def _process_whatsapp():
        try:
            # producer = await get_producer()
            agent = CustomerSuccessAgent()
            incoming = IncomingMessage(
                channel=ChannelType.WHATSAPP,
                sender_id=parsed["sender_phone"],
                content=parsed["body"],
                sender_name=parsed["sender_name"],
                channel_thread_id=parsed.get("conversation_sid", ""),
                channel_message_id=parsed.get("message_sid", ""),
                channel_context={
                    "to_number": parsed["sender_phone"],
                    "conversation_sid": parsed.get("conversation_sid", ""),
                },
            )
            async with get_session() as session:
                await agent.process(incoming, session)
            logger.info("WhatsApp message processed directly: %s", parsed.get("message_sid", ""))
        except Exception as exc:
            logger.error("WhatsApp background processing failed: %s", exc)

    background_tasks.add_task(_process_whatsapp)

    # Twilio expects an XML response
    from fastapi.responses import Response
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response/>',
        media_type="application/xml",
    )


# ---------------------------------------------------------------------------
# Web Support Form Submit
# ---------------------------------------------------------------------------

@router.post(
    "/webform/submit",
    response_model=WebFormResponse,
    summary="Submit a web support form",
)
async def webform_submit(
    submission: WebFormSubmission,
    handler: WebFormHandler = Depends(_get_webform_handler),
) -> WebFormResponse:
    """
    Accepts support form submissions from the embedded web widget.
    Publishes to Kafka and returns an immediate acknowledgement.
    """
    return await handler.handle_submission(submission)


# ---------------------------------------------------------------------------
# WebSocket Live Chat
# ---------------------------------------------------------------------------

@router.websocket("/webform/chat")
async def webform_chat(websocket: WebSocket):
    """
    WebSocket endpoint for real-time chat support widget.
    Query param: ?session_id=<uuid>
    """
    session_id = websocket.query_params.get("session_id", "")
    if not session_id:
        await websocket.close(code=4000, reason="session_id required")
        return

    await connection_manager.connect(websocket, session_id)

    try:
            # producer = await get_producer()
            # handler = WebFormHandler(producer)
            handler = WebFormHandler()

            # Send connection ack
            await websocket.send_json({
                "type": "connected",
                "session_id": session_id,
                "message": "Connected to Customer Success AI. How can I help you today?",
            })

            while True:
                data = await websocket.receive_json()
                content = data.get("content", "").strip()
                if not content:
                    continue

                chat_msg = WebFormChatMessage(session_id=session_id, content=content)
                await handler.handle_chat_message(chat_msg)

    except WebSocketDisconnect:
        connection_manager.disconnect(websocket, session_id)
        logger.info("WebSocket disconnected: session=%s", session_id)
    except Exception as exc:
        logger.error("WebSocket error: %s", exc)
        connection_manager.disconnect(websocket, session_id)
