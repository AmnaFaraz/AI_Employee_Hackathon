"""
Kafka Event Schemas — Customer Success Digital FTE

Pydantic models for messages flowing through Kafka topics.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class KafkaIncomingMessage(BaseModel):
    """Published to topic: customer-messages"""
    event_id: str = Field(..., description="Unique event ID for deduplication")
    channel: str                        # EMAIL | WHATSAPP | WEB_FORM
    sender_id: str                      # email, phone, or session_id
    sender_name: str = ""
    content: str
    channel_thread_id: str = ""
    channel_message_id: str = ""
    channel_context: dict[str, Any] = Field(default_factory=dict)
    received_at: datetime = Field(default_factory=datetime.utcnow)


class KafkaAgentResponse(BaseModel):
    """Published to topic: agent-responses"""
    event_id: str
    original_event_id: str
    channel: str
    sender_id: str
    response_content: str
    ticket_id: Optional[str] = None
    ticket_number: Optional[int] = None
    was_escalated: bool = False
    escalation_reason: Optional[str] = None
    processing_ms: int
    responded_at: datetime = Field(default_factory=datetime.utcnow)


class KafkaErrorEvent(BaseModel):
    """Published to topic: agent-errors"""
    event_id: str
    original_event_id: str
    channel: str
    error_type: str
    error_message: str
    failed_at: datetime = Field(default_factory=datetime.utcnow)
