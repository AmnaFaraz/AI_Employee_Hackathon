"""
Agent Tools — Customer Success Digital FTE

Five tools provided to the OpenAI Agents SDK agent:
  1. search_knowledge_base
  2. get_customer_history
  3. create_ticket
  4. send_response
  5. escalate_to_human
"""
from __future__ import annotations

import os
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Any

from openai import AsyncOpenAI
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    Customer,
    CustomerIdentifier,
    Conversation,
    Message,
    Ticket,
    KnowledgeBase,
    AgentMetric,
    ChannelType,
    TicketStatus,
    TicketPriority,
    MessageRole,
    IdentifierType,
)
from src.agent.formatters import format_response, FormattedResponse

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Tool: search_knowledge_base
# ---------------------------------------------------------------------------

async def search_knowledge_base(
    query: str,
    session: AsyncSession,
    openai_client: AsyncOpenAI,
    top_k: int = 3,
    similarity_threshold: float = 0.70,
) -> list[dict[str, Any]]:
    """
    Semantic search over the product knowledge base using pgvector cosine similarity.

    Args:
        query: The customer's question in natural language.
        session: Async DB session.
        openai_client: OpenAI client for embedding generation.
        top_k: Number of results to return.
        similarity_threshold: Minimum cosine similarity (0-1).

    Returns:
        List of KB articles with title, content, category, and similarity score.
    """
    try:
        # Generate query embedding
        embed_response = await openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=query,
        )
        query_vector = embed_response.data[0].embedding

        # pgvector cosine similarity search
        result = await session.execute(
            select(
                KnowledgeBase.id,
                KnowledgeBase.title,
                KnowledgeBase.content,
                KnowledgeBase.category,
                KnowledgeBase.source_url,
                (1 - KnowledgeBase.content_vector.cosine_distance(query_vector)).label("similarity"),
            )
            .where(KnowledgeBase.is_active == True)
            .order_by(
                KnowledgeBase.content_vector.cosine_distance(query_vector)
            )
            .limit(top_k)
        )
        rows = result.all()

        articles = []
        for row in rows:
            if row.similarity >= similarity_threshold:
                articles.append(
                    {
                        "id": str(row.id),
                        "title": row.title,
                        "content": row.content[:2000],  # truncate for context window
                        "category": row.category,
                        "source_url": row.source_url,
                        "similarity": round(row.similarity, 4),
                    }
                )

                # Increment view count
                kb = await session.get(KnowledgeBase, row.id)
                if kb:
                    kb.view_count += 1

        return articles

    except Exception as exc:
        logger.error("search_knowledge_base failed: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Tool: get_customer_history
# ---------------------------------------------------------------------------

async def get_customer_history(
    customer_id: uuid.UUID,
    session: AsyncSession,
    limit_messages: int = 10,
) -> dict[str, Any]:
    """
    Retrieve recent conversation history and open tickets for a customer.

    Args:
        customer_id: UUID of the customer.
        session: Async DB session.
        limit_messages: Number of recent messages to include.

    Returns:
        Dict with customer info, recent messages, and open tickets.
    """
    try:
        customer = await session.get(Customer, customer_id)
        if not customer:
            return {"error": "Customer not found"}

        # Recent messages
        msg_result = await session.execute(
            select(Message)
            .where(Message.customer_id == customer_id)
            .order_by(desc(Message.created_at))
            .limit(limit_messages)
        )
        messages = msg_result.scalars().all()

        # Open tickets
        ticket_result = await session.execute(
            select(Ticket)
            .where(
                Ticket.customer_id == customer_id,
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS, TicketStatus.ESCALATED]),
            )
            .order_by(desc(Ticket.created_at))
            .limit(5)
        )
        open_tickets = ticket_result.scalars().all()

        return {
            "customer": {
                "id": str(customer.id),
                "name": customer.display_name,
                "email": customer.primary_email,
                "company": customer.company,
                "plan": customer.plan,
            },
            "recent_messages": [
                {
                    "role": m.role.value,
                    "content": m.content[:500],
                    "channel": m.channel.value,
                    "created_at": m.created_at.isoformat(),
                }
                for m in reversed(messages)
            ],
            "open_tickets": [
                {
                    "id": str(t.id),
                    "ticket_number": t.ticket_number,
                    "subject": t.subject,
                    "status": t.status.value,
                    "priority": t.priority.value,
                    "created_at": t.created_at.isoformat(),
                }
                for t in open_tickets
            ],
            "open_ticket_count": len(open_tickets),
        }

    except Exception as exc:
        logger.error("get_customer_history failed: %s", exc)
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# Tool: create_ticket
# ---------------------------------------------------------------------------

async def create_ticket(
    customer_id: uuid.UUID,
    subject: str,
    description: str,
    channel: ChannelType,
    session: AsyncSession,
    conversation_id: uuid.UUID | None = None,
    priority: TicketPriority = TicketPriority.MEDIUM,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Create a new support ticket in the CRM.

    Returns the created ticket's ID and ticket number.
    """
    try:
        ticket = Ticket(
            customer_id=customer_id,
            conversation_id=conversation_id,
            subject=subject[:500],
            description=description,
            status=TicketStatus.OPEN,
            priority=priority,
            channel=channel,
            tags=tags or [],
        )
        session.add(ticket)
        await session.flush()  # get ticket_number assigned

        logger.info("Ticket #%d created for customer %s", ticket.ticket_number, customer_id)

        return {
            "ticket_id": str(ticket.id),
            "ticket_number": ticket.ticket_number,
            "status": ticket.status.value,
            "priority": ticket.priority.value,
        }

    except Exception as exc:
        logger.error("create_ticket failed: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Tool: send_response
# ---------------------------------------------------------------------------

async def send_response(
    raw_content: str,
    channel: ChannelType,
    customer_name: str,
    ticket_number: int | None,
    channel_context: dict[str, Any],
) -> FormattedResponse:
    """
    Format and dispatch a response through the appropriate channel.

    `channel_context` varies by channel:
      EMAIL:    {"to_email": "...", "subject": "...", "thread_id": "..."}
      WHATSAPP: {"to_number": "+1...", "conversation_sid": "..."}
      WEB_FORM: {"session_id": "..."}

    Returns the formatted response object (actual sending is done by channel handlers).
    """
    formatted = format_response(
        raw_content=raw_content,
        channel=channel,
        customer_name=customer_name,
        ticket_number=ticket_number,
    )

    logger.info(
        "send_response | channel=%s | chars=%d | words=%s",
        channel.value,
        formatted.char_count,
        formatted.word_count,
    )

    return formatted


# ---------------------------------------------------------------------------
# Tool: escalate_to_human
# ---------------------------------------------------------------------------

async def escalate_to_human(
    ticket_id: uuid.UUID,
    reason: str,
    session: AsyncSession,
    assigned_to: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    """
    Mark a ticket as ESCALATED and assign it to a human agent queue.

    In production this should also:
    - Post to an on-call Slack channel
    - Send email to assigned_to
    - Create a PagerDuty incident for URGENT tickets
    """
    try:
        ticket = await session.get(Ticket, ticket_id)
        if not ticket:
            return {"error": "Ticket not found"}

        ticket.status = TicketStatus.ESCALATED
        ticket.escalation_reason = reason
        ticket.assigned_to = assigned_to or os.environ.get("DEFAULT_ESCALATION_EMAIL", "support-team@company.com")
        ticket.priority = TicketPriority.HIGH
        if notes:
            existing_desc = ticket.description or ""
            ticket.description = f"{existing_desc}\n\n[ESCALATION NOTE]: {notes}".strip()

        logger.warning(
            "Ticket #%d ESCALATED | reason=%s | assigned_to=%s",
            ticket.ticket_number,
            reason,
            ticket.assigned_to,
        )

        # TODO: Integrate Slack/PagerDuty notifications here
        # await notify_on_call_team(ticket)

        return {
            "ticket_id": str(ticket.id),
            "ticket_number": ticket.ticket_number,
            "status": "ESCALATED",
            "assigned_to": ticket.assigned_to,
            "reason": reason,
        }

    except Exception as exc:
        logger.error("escalate_to_human failed: %s", exc)
        raise


# ---------------------------------------------------------------------------
# Customer resolution (cross-channel identity)
# ---------------------------------------------------------------------------

async def resolve_customer(
    identifier_value: str,
    identifier_type: IdentifierType,
    session: AsyncSession,
) -> Customer | None:
    """
    Resolve a customer from any identifier (email, phone, WhatsApp ID, user_id).
    Creates a new customer record if none found.
    """
    # Look up existing identifier
    result = await session.execute(
        select(CustomerIdentifier).where(
            CustomerIdentifier.identifier_type == identifier_type,
            CustomerIdentifier.identifier_value == identifier_value,
        )
    )
    ident = result.scalar_one_or_none()

    if ident:
        return await session.get(Customer, ident.customer_id)

    # Create new customer + identifier
    customer = Customer(display_name=identifier_value)
    if identifier_type == IdentifierType.EMAIL:
        customer.primary_email = identifier_value
    elif identifier_type == IdentifierType.PHONE:
        customer.primary_phone = identifier_value

    session.add(customer)
    await session.flush()

    new_ident = CustomerIdentifier(
        customer_id=customer.id,
        identifier_type=identifier_type,
        identifier_value=identifier_value,
    )
    session.add(new_ident)

    logger.info("New customer created: %s", customer.id)
    return customer
