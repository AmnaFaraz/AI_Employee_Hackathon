"""
SQLAlchemy ORM Models — Customer Success Digital FTE CRM
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float,
    ForeignKey, DateTime, Enum as SAEnum, ARRAY,
    UniqueConstraint, Index, func,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from pgvector.sqlalchemy import Vector
import enum


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ChannelType(str, enum.Enum):
    EMAIL = "EMAIL"
    WHATSAPP = "WHATSAPP"
    WEB_FORM = "WEB_FORM"


class TicketStatus(str, enum.Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class TicketPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class MessageRole(str, enum.Enum):
    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


class IdentifierType(str, enum.Enum):
    EMAIL = "EMAIL"
    PHONE = "PHONE"
    USER_ID = "USER_ID"
    WHATSAPP_ID = "WHATSAPP_ID"


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    display_name: Mapped[Optional[str]] = mapped_column(String(255))
    primary_email: Mapped[Optional[str]] = mapped_column(String(320), unique=True, index=True)
    primary_phone: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    company: Mapped[Optional[str]] = mapped_column(String(255), index=True)
    plan: Mapped[str] = mapped_column(String(100), default="free")
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    identifiers: Mapped[List["CustomerIdentifier"]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    conversations: Mapped[List["Conversation"]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    tickets: Mapped[List["Ticket"]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    messages: Mapped[List["Message"]] = relationship(back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer id={self.id} email={self.primary_email}>"


# ---------------------------------------------------------------------------
# CustomerIdentifier
# ---------------------------------------------------------------------------

class CustomerIdentifier(Base):
    __tablename__ = "customer_identifiers"
    __table_args__ = (
        UniqueConstraint("identifier_type", "identifier_value"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    identifier_type: Mapped[IdentifierType] = mapped_column(SAEnum(IdentifierType, name="identifier_type"))
    identifier_value: Mapped[str] = mapped_column(String(500), index=True)
    channel: Mapped[Optional[ChannelType]] = mapped_column(SAEnum(ChannelType, name="channel_type"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer: Mapped["Customer"] = relationship(back_populates="identifiers")


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------

class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    channel: Mapped[ChannelType] = mapped_column(SAEnum(ChannelType, name="channel_type"))
    channel_thread_id: Mapped[Optional[str]] = mapped_column(String(500), index=True)
    subject: Mapped[Optional[str]] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(50), default="ACTIVE", index=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_message_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    customer: Mapped["Customer"] = relationship(back_populates="conversations")
    messages: Mapped[List["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan")
    tickets: Mapped[List["Ticket"]] = relationship(back_populates="conversation")


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[MessageRole] = mapped_column(SAEnum(MessageRole, name="message_role"))
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_vector: Mapped[Optional[List[float]]] = mapped_column(Vector(1536))
    channel: Mapped[ChannelType] = mapped_column(SAEnum(ChannelType, name="channel_type"))
    channel_message_id: Mapped[Optional[str]] = mapped_column(String(500), index=True)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    processing_ms: Mapped[Optional[int]] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    customer: Mapped["Customer"] = relationship(back_populates="messages")


# ---------------------------------------------------------------------------
# Ticket
# ---------------------------------------------------------------------------

class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_number: Mapped[int] = mapped_column(Integer, unique=True, server_default=func.nextval('tickets_ticket_number_seq'))
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), index=True
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), index=True
    )
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    status: Mapped[TicketStatus] = mapped_column(
        SAEnum(TicketStatus, name="ticket_status"), default=TicketStatus.OPEN, index=True
    )
    priority: Mapped[TicketPriority] = mapped_column(
        SAEnum(TicketPriority, name="ticket_priority"), default=TicketPriority.MEDIUM, index=True
    )
    channel: Mapped[ChannelType] = mapped_column(SAEnum(ChannelType, name="channel_type"))
    assigned_to: Mapped[Optional[str]] = mapped_column(String(255))
    escalation_reason: Mapped[Optional[str]] = mapped_column(Text)
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    customer: Mapped["Customer"] = relationship(back_populates="tickets")
    conversation: Mapped[Optional["Conversation"]] = relationship(back_populates="tickets")


# ---------------------------------------------------------------------------
# KnowledgeBase
# ---------------------------------------------------------------------------

class KnowledgeBase(Base):
    __tablename__ = "knowledge_base"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_vector: Mapped[List[float]] = mapped_column(Vector(1536), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(100), index=True)
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), default=list)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    view_count: Mapped[int] = mapped_column(Integer, default=0)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ---------------------------------------------------------------------------
# AgentMetrics
# ---------------------------------------------------------------------------

class AgentMetric(Base):
    __tablename__ = "agent_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id", ondelete="SET NULL")
    )
    ticket_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tickets.id", ondelete="SET NULL")
    )
    channel: Mapped[ChannelType] = mapped_column(SAEnum(ChannelType, name="channel_type"), index=True)
    processing_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    kb_hits: Mapped[int] = mapped_column(Integer, default=0)
    was_escalated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    escalation_reason: Mapped[Optional[str]] = mapped_column(String(255))
    confidence_score: Mapped[Optional[float]] = mapped_column(Float)
    customer_satisfied: Mapped[Optional[bool]] = mapped_column(Boolean)
    tokens_used: Mapped[Optional[int]] = mapped_column(Integer)
    model_used: Mapped[Optional[str]] = mapped_column(String(100))
    error_occurred: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
