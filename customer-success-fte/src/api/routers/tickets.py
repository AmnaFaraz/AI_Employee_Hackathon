"""
Tickets Router — Customer Success Digital FTE

CRUD endpoints for support ticket management.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_session
from src.database.models import Ticket, TicketStatus, TicketPriority, ChannelType

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TicketResponse(BaseModel):
    id: str
    ticket_number: int
    customer_id: str
    subject: str
    description: Optional[str]
    status: str
    priority: str
    channel: str
    assigned_to: Optional[str]
    escalation_reason: Optional[str]
    tags: list[str]
    created_at: str
    updated_at: str
    resolved_at: Optional[str]

    class Config:
        from_attributes = True


class TicketUpdateRequest(BaseModel):
    status: Optional[TicketStatus] = None
    priority: Optional[TicketPriority] = None
    assigned_to: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[list[str]] = None


class TicketReplyRequest(BaseModel):
    message: str


class TicketListResponse(BaseModel):
    tickets: list[TicketResponse]
    total: int
    page: int
    page_size: int


def _ticket_to_response(t: Ticket) -> TicketResponse:
    return TicketResponse(
        id=str(t.id),
        ticket_number=t.ticket_number,
        customer_id=str(t.customer_id),
        subject=t.subject,
        description=t.description,
        status=t.status.value,
        priority=t.priority.value,
        channel=t.channel.value,
        assigned_to=t.assigned_to,
        escalation_reason=t.escalation_reason,
        tags=t.tags or [],
        created_at=t.created_at.isoformat(),
        updated_at=t.updated_at.isoformat(),
        resolved_at=t.resolved_at.isoformat() if t.resolved_at else None,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "",
    response_model=TicketListResponse,
    summary="List all tickets with optional filters",
)
async def list_tickets(
    status: Optional[TicketStatus] = Query(None),
    priority: Optional[TicketPriority] = Query(None),
    channel: Optional[ChannelType] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    async with get_session() as session:
        query = select(Ticket)

        if status:
            query = query.where(Ticket.status == status)
        if priority:
            query = query.where(Ticket.priority == priority)
        if channel:
            query = query.where(Ticket.channel == channel)

        # Count total
        count_result = await session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        # Paginate
        query = query.order_by(desc(Ticket.created_at)).offset((page - 1) * page_size).limit(page_size)
        result = await session.execute(query)
        tickets = result.scalars().all()

        return TicketListResponse(
            tickets=[_ticket_to_response(t) for t in tickets],
            total=total,
            page=page,
            page_size=page_size,
        )


@router.get(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Get a specific ticket by ID",
)
async def get_ticket(ticket_id: str):
    async with get_session() as session:
        try:
            tid = uuid.UUID(ticket_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid ticket_id format")

        ticket = await session.get(Ticket, tid)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        return _ticket_to_response(ticket)


@router.patch(
    "/{ticket_id}",
    response_model=TicketResponse,
    summary="Update ticket status, priority, or assignment",
)
async def update_ticket(ticket_id: str, update: TicketUpdateRequest):
    async with get_session() as session:
        try:
            tid = uuid.UUID(ticket_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid ticket_id format")

        ticket = await session.get(Ticket, tid)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        if update.status is not None:
            ticket.status = update.status
            if update.status in (TicketStatus.RESOLVED, TicketStatus.CLOSED):
                ticket.resolved_at = datetime.now(timezone.utc)

        if update.priority is not None:
            ticket.priority = update.priority

        if update.assigned_to is not None:
            ticket.assigned_to = update.assigned_to

        if update.description is not None:
            ticket.description = update.description

        if update.tags is not None:
            ticket.tags = update.tags

        return _ticket_to_response(ticket)


@router.post(
    "/{ticket_id}/reply",
    response_model=TicketResponse,
    summary="Admin reply to a ticket thread",
)
async def reply_ticket(ticket_id: str, reply: TicketReplyRequest):
    from src.database.models import Message, MessageRole
    async with get_session() as session:
        try:
            tid = uuid.UUID(ticket_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid ticket_id format")

        ticket = await session.get(Ticket, tid)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found")

        # Create msg
        msg = Message(
            customer_id=ticket.customer_id,
            conversation_id=ticket.conversation_id,
            channel=ticket.channel,
            role=MessageRole.AGENT,
            content=reply.message,
            is_human=True,
        )
        session.add(msg)
        
        if ticket.status == TicketStatus.ESCALATED:
            ticket.status = TicketStatus.IN_PROGRESS

        await session.commit()
        await session.refresh(ticket)
        return _ticket_to_response(ticket)

