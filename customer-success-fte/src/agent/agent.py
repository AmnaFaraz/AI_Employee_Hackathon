"""
Core AI Agent — Customer Success Digital FTE

Uses the OpenAI Agents SDK to orchestrate the full support loop:
  receive message → identify customer → retrieve history →
  search KB → generate answer → create ticket → respond / escalate
"""
from __future__ import annotations

import os
import time
import uuid
import logging
from pathlib import Path
from typing import Any, Optional

from openai import AsyncOpenAI
from agents import Agent, Runner, Tool, function_tool
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import (
    ChannelType, TicketPriority, IdentifierType,
    Conversation, Message, MessageRole, AgentMetric,
)
from src.agent.tools import (
    search_knowledge_base as _search_kb,
    get_customer_history as _get_history,
    create_ticket as _create_ticket,
    send_response as _send_response,
    escalate_to_human as _escalate,
    resolve_customer,
)
from src.agent.escalation import EscalationEngine, EscalationResult
from src.agent.formatters import get_channel_prompt_instructions

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = (Path(__file__).parent.parent.parent.parent / "context" / "system_prompt.txt").read_text()


# ---------------------------------------------------------------------------
# Incoming message event (normalised across channels)
# ---------------------------------------------------------------------------

class IncomingMessage:
    """Normalised message event produced by channel handlers."""

    def __init__(
        self,
        *,
        channel: ChannelType,
        content: str,
        sender_id: str,           # email, phone number, or user_id
        sender_name: str = "",
        channel_thread_id: str = "",
        channel_message_id: str = "",
        channel_context: dict[str, Any] | None = None,
    ):
        self.channel = channel
        self.content = content
        self.sender_id = sender_id
        self.sender_name = sender_name
        self.channel_thread_id = channel_thread_id
        self.channel_message_id = channel_message_id
        self.channel_context = channel_context or {}

    def identifier_type(self) -> IdentifierType:
        if self.channel == ChannelType.EMAIL:
            return IdentifierType.EMAIL
        elif self.channel == ChannelType.WHATSAPP:
            return IdentifierType.WHATSAPP_ID
        else:
            return IdentifierType.USER_ID


# ---------------------------------------------------------------------------
# Agent response
# ---------------------------------------------------------------------------

class AgentResponse:
    def __init__(
        self,
        *,
        content: str,
        ticket_id: uuid.UUID | None,
        ticket_number: int | None,
        was_escalated: bool,
        escalation_reason: str | None,
        processing_ms: int,
        kb_articles_used: int,
    ):
        self.content = content
        self.ticket_id = ticket_id
        self.ticket_number = ticket_number
        self.was_escalated = was_escalated
        self.escalation_reason = escalation_reason
        self.processing_ms = processing_ms
        self.kb_articles_used = kb_articles_used


# ---------------------------------------------------------------------------
# Customer Support Agent
# ---------------------------------------------------------------------------

class CustomerSuccessAgent:
    """
    Wraps the OpenAI Agents SDK Agent with domain logic.
    One instance can process many requests concurrently.
    """

    def __init__(self):
        # Remove langsmith wrapper for cleaner debugging of tool calls
        self._client = AsyncOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=os.environ["GROQ_API_KEY"]
        )
        self._escalation_engine = EscalationEngine(self._client)

    def _build_agent(self, session: AsyncSession, channel: ChannelType) -> Agent:
        """
        Build an OpenAI Agents SDK Agent with session-bound tools.
        Tools close over `session` via Python closures.
        """

        @function_tool
        async def kb(query: str) -> str:
            """Search the product knowledge base for relevant articles."""
            articles = await _search_kb(query, session, self._client)
            if not articles:
                return "No relevant knowledge base articles found."
            parts = []
            for i, a in enumerate(articles, 1):
                parts.append(
                    f"[Article {i}] {a['title']} (similarity={a['similarity']})\n{a['content']}"
                )
            return "\n\n---\n\n".join(parts)

        @function_tool
        async def history(customer_id: str) -> str:
            """Retrieve recent messages and open tickets for a customer."""
            import json
            try:
                cid = uuid.UUID(customer_id)
            except ValueError:
                return "Invalid customer_id format."
            data = await _get_history(cid, session)
            return json.dumps(data, indent=2, default=str)

        @function_tool
        async def ticket(
            customer_id: str,
            subject: str,
            description: str,
            priority: str = "MEDIUM",
        ) -> str:
            """Create a new support ticket for the customer."""
            import json
            try:
                cid = uuid.UUID(customer_id)
            except ValueError:
                return "Invalid customer_id format."
            prio_map = {
                "LOW": TicketPriority.LOW,
                "MEDIUM": TicketPriority.MEDIUM,
                "HIGH": TicketPriority.HIGH,
                "URGENT": TicketPriority.URGENT,
            }
            result = await _create_ticket(
                customer_id=cid,
                subject=subject,
                description=description,
                channel=channel,
                session=session,
                priority=prio_map.get(priority.upper(), TicketPriority.MEDIUM),
            )
            return json.dumps(result)

        @function_tool
        async def respond(
            content: str,
            customer_name: str,
            ticket_number: int,
        ) -> str:
            """Format and prepare the final response for the customer."""
            formatted = await _send_response(
                raw_content=content,
                channel=channel,
                customer_name=customer_name,
                ticket_number=ticket_number,
                channel_context={},
            )
            return formatted.content

        @function_tool
        async def escalate(
            ticket_id: str,
            reason: str,
            notes: str = "",
        ) -> str:
            """Escalate a ticket to a human agent."""
            import json
            try:
                tid = uuid.UUID(ticket_id)
            except ValueError:
                return "Invalid ticket_id format."
            result = await _escalate(tid, reason, session, notes=notes)
            return json.dumps(result)

        channel_instructions = get_channel_prompt_instructions(channel)

        return Agent(
            name="Aria",
            instructions=f"{_SYSTEM_PROMPT}\n\nCHANNEL INSTRUCTIONS: {channel_instructions}",
            tools=[
                kb,
                history,
                ticket,
                respond,
                escalate,
            ],
            model="mixtral-8x7b-32768",
        )

    async def process(
        self,
        incoming: IncomingMessage,
        session: AsyncSession,
    ) -> AgentResponse:
        """
        Full processing pipeline:
        1. Identify/create customer
        2. Get/create conversation
        3. Save incoming message
        4. Run escalation check
        5. Run agent
        6. Save agent reply message
        7. Record metrics
        """
        start_time = time.monotonic()
        ticket_id: uuid.UUID | None = None
        ticket_number: int | None = None
        was_escalated = False
        escalation_reason: str | None = None
        kb_articles_used = 0

        try:
            # --- 1. Resolve customer ---
            customer = await resolve_customer(
                identifier_value=incoming.sender_id,
                identifier_type=incoming.identifier_type(),
                session=session,
            )
            if not customer:
                raise RuntimeError("Customer resolution failed")

            if incoming.sender_name and not customer.display_name:
                customer.display_name = incoming.sender_name

            # --- 2. Resolve or create conversation ---
            conv = None
            if incoming.channel_thread_id:
                from sqlalchemy import select
                result = await session.execute(
                    select(Conversation).where(
                        Conversation.channel_thread_id == incoming.channel_thread_id
                    )
                )
                conv = result.scalar_one_or_none()

            if not conv:
                conv = Conversation(
                    customer_id=customer.id,
                    channel=incoming.channel,
                    channel_thread_id=incoming.channel_thread_id or None,
                )
                session.add(conv)
                await session.flush()

            # --- 3. Save inbound message ---
            inbound_msg = Message(
                conversation_id=conv.id,
                customer_id=customer.id,
                role=MessageRole.CUSTOMER,
                content=incoming.content,
                channel=incoming.channel,
                channel_message_id=incoming.channel_message_id or None,
            )
            session.add(inbound_msg)
            await session.flush()

            # --- 4. Escalation pre-check ---
            from sqlalchemy import select as sa_select
            from src.database.models import Ticket, TicketStatus
            open_ticket_result = await session.execute(
                sa_select(Ticket).where(
                    Ticket.customer_id == customer.id,
                    Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS]),
                )
            )
            open_tickets = open_ticket_result.scalars().all()

            escalation_result: EscalationResult = await self._escalation_engine.evaluate(
                incoming.content,
                open_ticket_count=len(open_tickets),
            )
            was_escalated = escalation_result.should_escalate
            escalation_reason = escalation_result.reason.value if escalation_result.reason else None

            # Compose user message for agent
            context_message = (
                f"Customer ID: {customer.id}\n"
                f"Customer Name: {customer.display_name or 'Unknown'}\n"
                f"Channel: {incoming.channel.value}\n"
                f"Escalation Required: {was_escalated}\n"
                f"Escalation Reason: {escalation_reason or 'None'}\n\n"
                f"Customer Message:\n{incoming.content}"
            )

            # --- 5. Run agent with manual tool loop (more robust for Groq) ---
            # Ultra-high-reliability tool prompt for Groq/Llama
            agent_system_prompt = (
                f"{_SYSTEM_PROMPT}\n\n"
                f"CHANNEL INSTRUCTIONS: {get_channel_prompt_instructions(incoming.channel)}\n\n"
                "## MANDATORY TOOL FORMAT:\n"
                "Your tool calls MUST follow this syntax EXACTLY. Failure will cause an error.\n"
                "SYNTAX: `tool_name(param1=\"value1\", param2=\"value2\")`\n\n"
                "EXAMPLES:\n"
                "- kb(query=\"pricing info\")\n"
                "- history(customer_id=\"e0c02232...\")\n"
                "- ticket(customer_id=\"...\", subject=\"...\", description=\"...\")\n\n"
                "DO NOT USE CURLY BRACES `{}` AFTER THE TOOL NAME. Use parentheses `()`.\n"
                "DO NOT ADD ANY PREAMBLE. JUST THE TOOL CALL."
            )

            messages = [
                {"role": "system", "content": agent_system_prompt},
                {"role": "user", "content": context_message}
            ]

            # Simplified tool definitions for the API
            tools_spec = [
                {
                    "type": "function",
                    "function": {
                        "name": "kb",
                        "description": "Search knowledge base",
                        "parameters": {
                            "type": "object",
                            "properties": {"query": {"type": "string"}},
                            "required": ["query"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "history",
                        "description": "Get customer history",
                        "parameters": {
                            "type": "object",
                            "properties": {"customer_id": {"type": "string"}},
                            "required": ["customer_id"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "ticket",
                        "description": "Create support ticket",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "customer_id": {"type": "string"},
                                "subject": {"type": "string"},
                                "description": {"type": "string"},
                                "priority": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "URGENT"]}
                            },
                            "required": ["customer_id", "subject", "description"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "respond",
                        "description": "Send response to customer",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "content": {"type": "string"},
                                "customer_name": {"type": "string"},
                                "ticket_number": {"type": "integer"}
                            },
                            "required": ["content", "customer_name", "ticket_number"]
                        }
                    }
                },
                {
                    "type": "function",
                    "function": {
                        "name": "escalate",
                        "description": "Escalate to human",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "ticket_id": {"type": "string"},
                                "reason": {"type": "string"},
                                "notes": {"type": "string"}
                            },
                            "required": ["ticket_id", "reason"]
                        }
                    }
                }
            ]

            max_turns = 5
            agent_reply = ""
            
            # Local tool mapping (calling existing tool functions)
            tool_funcs = {
                "kb": lambda query: _search_kb(query, session, self._client),
                "history": lambda customer_id: _get_history(uuid.UUID(customer_id), session),
                "ticket": lambda customer_id, subject, description, priority="MEDIUM": _create_ticket(
                    uuid.UUID(customer_id), subject, description, incoming.channel, session, priority=TicketPriority[priority.upper()]
                ),
                "respond": lambda content, customer_name, ticket_number: _send_response(content, incoming.channel, customer_name, ticket_number, {}),
                "escalate": lambda ticket_id, reason, notes="": _escalate(uuid.UUID(ticket_id), reason, session, notes=notes)
            }

            import json
            for _ in range(max_turns):
                response = await self._client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    # We'll try to parse tools manually if the model is being helpful but malforming calls
                    # Or keep tool calling enabled but be more descriptive.
                    # Let's try ONE MORE prompt fix focusing on the ABSENCE of parentheses vs braces.
                    tools=tools_spec,
                    tool_choice="auto",
                    temperature=0
                )
                
                resp_msg = response.choices[0].message
                messages.append(resp_msg)
                
                if not resp_msg.tool_calls:
                    agent_reply = resp_msg.content or ""
                    # Check for "manual" tool calls in content if no formal tool_calls exist
                    # (Llama sometimes just writes "ticket(..." in content)
                    break
                
                for tool_call in resp_msg.tool_calls:
                    name = tool_call.function.name
                    # LAX PARSING: Handle Groq's tendency to merge name and arguments or use wrong delimiters
                    raw_args = tool_call.function.arguments
                    try:
                        args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        # Attempt to fix common malformations
                        import re
                        # If it starts with some variant of tool name, strip it
                        # Groq sometimes returns "ticket{\"customer_id\": ...}" as arguments
                        match = re.search(r'\{.*\}', raw_args)
                        if match:
                            try:
                                args = json.loads(match.group(0))
                            except:
                                args = {}
                        else:
                            args = {}
                    
                    logger.info(f"Agent calling tool: {name}({args})")
                    
                    if name in tool_funcs:
                        try:
                            # Map descriptive names to function calls
                            raw_result = await tool_funcs[name](**args)
                            
                            # Handle FormattedResponse from respond tool
                            if name == "respond":
                                result_str = raw_result.content
                            elif name == "kb":
                                parts = []
                                for i, a in enumerate(raw_result, 1):
                                    parts.append(f"[Article {i}] {a['title']} (similarity={a['similarity']})\n{a['content']}")
                                result_str = "\n\n---\n\n".join(parts) or "No relevant articles found."
                            else:
                                result_str = json.dumps(raw_result, default=str)
                                
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": name,
                                "content": result_str
                            })
                        except Exception as e:
                            logger.error(f"Tool execution error ({name}): {e}")
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call.id,
                                "name": name,
                                "content": f"Error: {str(e)}"
                            })
                    else:
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": name,
                            "content": "Error: Tool not found"
                        })
            
            if not agent_reply:
                agent_reply = "I've processed your request. Please let me know if you need anything else."

            # --- 6. Save agent reply ---
            reply_msg = Message(
                conversation_id=conv.id,
                customer_id=customer.id,
                role=MessageRole.AGENT,
                content=agent_reply,
                channel=incoming.channel,
                processing_ms=int((time.monotonic() - start_time) * 1000),
            )
            session.add(reply_msg)

            # Update conversation last_message_at
            from datetime import datetime, timezone
            conv.last_message_at = datetime.now(timezone.utc)

            # --- 7. Record metrics ---
            processing_ms = int((time.monotonic() - start_time) * 1000)
            metric = AgentMetric(
                message_id=inbound_msg.id,
                channel=incoming.channel,
                processing_ms=processing_ms,
                kb_hits=kb_articles_used,
                was_escalated=was_escalated,
                escalation_reason=escalation_reason,
                model_used="llama-3.3-70b-versatile",
            )
            session.add(metric)

            logger.info(
                "Agent processed | customer=%s | channel=%s | ms=%d | escalated=%s",
                customer.id,
                incoming.channel.value,
                processing_ms,
                was_escalated,
            )

            return AgentResponse(
                content=agent_reply,
                ticket_id=ticket_id,
                ticket_number=ticket_number,
                was_escalated=was_escalated,
                escalation_reason=escalation_reason,
                processing_ms=processing_ms,
                kb_articles_used=kb_articles_used,
            )

        except Exception as exc:
            processing_ms = int((time.monotonic() - start_time) * 1000)
            logger.error("Agent processing error: %s", exc, exc_info=True)
            metric = AgentMetric(
                channel=incoming.channel,
                processing_ms=processing_ms,
                error_occurred=True,
                error_message=str(exc)[:500],
                model_used="llama-3.3-70b-versatile",
            )
            session.add(metric)
            raise
