"""
Customers Router — Customer Success Digital FTE
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.connection import get_session
from src.database.models import Customer, Conversation, Message, Ticket

router = APIRouter()


class CustomerResponse(BaseModel):
    id: str
    display_name: Optional[str]
    primary_email: Optional[str]
    primary_phone: Optional[str]
    company: Optional[str]
    plan: str
    created_at: str


class ConversationSummary(BaseModel):
    id: str
    channel: str
    subject: Optional[str]
    status: str
    message_count: int
    started_at: str
    last_message_at: str


@router.get("/{customer_id}", response_model=CustomerResponse, summary="Get customer by ID")
async def get_customer(customer_id: str):
    async with get_session() as session:
        try:
            cid = uuid.UUID(customer_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid customer_id")

        c = await session.get(Customer, cid)
        if not c:
            raise HTTPException(status_code=404, detail="Customer not found")

        return CustomerResponse(
            id=str(c.id),
            display_name=c.display_name,
            primary_email=c.primary_email,
            primary_phone=c.primary_phone,
            company=c.company,
            plan=c.plan,
            created_at=c.created_at.isoformat(),
        )


@router.get(
    "/{customer_id}/conversations",
    response_model=list[ConversationSummary],
    summary="Get conversation history for a customer",
)
async def get_customer_conversations(
    customer_id: str,
    limit: int = Query(10, ge=1, le=50),
):
    async with get_session() as session:
        try:
            cid = uuid.UUID(customer_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid customer_id")

        result = await session.execute(
            select(Conversation)
            .where(Conversation.customer_id == cid)
            .order_by(desc(Conversation.last_message_at))
            .limit(limit)
        )
        conversations = result.scalars().all()

        summaries = []
        for conv in conversations:
            msg_count_result = await session.execute(
                select(Message).where(Message.conversation_id == conv.id)
            )
            msg_count = len(msg_count_result.scalars().all())

            summaries.append(
                ConversationSummary(
                    id=str(conv.id),
                    channel=conv.channel.value,
                    subject=conv.subject,
                    status=conv.status,
                    message_count=msg_count,
                    started_at=conv.started_at.isoformat(),
                    last_message_at=conv.last_message_at.isoformat(),
                )
            )

        return summaries
