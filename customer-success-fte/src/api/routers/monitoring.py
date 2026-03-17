"""
Monitoring Router — Customer Success Digital FTE

Health check and metrics endpoints.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import select, func, text

from src.database.connection import get_session, get_engine
from src.database.models import AgentMetric, Ticket, TicketStatus

router = APIRouter()


@router.get("/health", summary="System health check")
async def health_check():
    """Returns health status of all system components."""
    checks = {}

    # Database check
    try:
        async with get_session() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as exc:
        checks["database"] = f"unhealthy: {exc}"

    # Kafka check (simple connectivity)
    kafka_servers = os.environ.get("KAFKA_BOOTSTRAP_SERVERS")
    if not kafka_servers or kafka_servers == "INSERT_KAFKA_SERVERS_HERE":
        checks["kafka"] = "healthy (skipped: Kafka disabled)"
    else:
        try:
            from aiokafka.admin import AIOKafkaAdminClient
            client = AIOKafkaAdminClient(bootstrap_servers=kafka_servers)
            await client.start()
            await client.close()
            checks["kafka"] = "healthy"
        except Exception as exc:
            checks["kafka"] = f"unhealthy: {exc}"

    overall = "healthy" if all(v == "healthy" for v in checks.values()) else "degraded"

    return {
        "status": overall,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0",
        "checks": checks,
    }


@router.get("/metrics", summary="Agent performance metrics")
async def get_metrics():
    """Returns aggregated agent performance statistics."""
    async with get_session() as session:
        # Last 24h metrics
        result = await session.execute(
            select(
                func.count(AgentMetric.id).label("total_requests"),
                func.avg(AgentMetric.processing_ms).label("avg_processing_ms"),
                func.max(AgentMetric.processing_ms).label("max_processing_ms"),
                func.sum(
                    func.cast(AgentMetric.was_escalated, func.Integer())
                ).label("total_escalations"),
                func.sum(
                    func.cast(AgentMetric.error_occurred, func.Integer())
                ).label("total_errors"),
                func.avg(AgentMetric.confidence_score).label("avg_confidence"),
            ).where(
                AgentMetric.created_at >= text("NOW() - INTERVAL '24 hours'")
            )
        )
        row = result.one()

        total = row.total_requests or 0
        escalations = int(row.total_escalations or 0)
        errors = int(row.total_errors or 0)

        # Open tickets
        ticket_result = await session.execute(
            select(func.count(Ticket.id)).where(
                Ticket.status.in_([TicketStatus.OPEN, TicketStatus.IN_PROGRESS])
            )
        )
        open_tickets = ticket_result.scalar_one()

        # Escalated tickets
        escalated_result = await session.execute(
            select(func.count(Ticket.id)).where(Ticket.status == TicketStatus.ESCALATED)
        )
        escalated_tickets = escalated_result.scalar_one()

        return {
            "period": "last_24_hours",
            "total_requests": total,
            "avg_processing_ms": round(row.avg_processing_ms or 0, 2),
            "max_processing_ms": row.max_processing_ms or 0,
            "escalation_count": escalations,
            "escalation_rate_pct": round(escalations / max(total, 1) * 100, 2),
            "error_count": errors,
            "error_rate_pct": round(errors / max(total, 1) * 100, 2),
            "avg_confidence_score": round(row.avg_confidence or 0, 4),
            "open_tickets": open_tickets,
            "escalated_tickets": escalated_tickets,
            "targets": {
                "response_processing_under_3s": "< 3000 ms",
                "accuracy_above_85pct": "> 85%",
                "escalation_rate_below_20pct": "< 20%",
            },
        }


@router.get("/api/v1/admin/metrics", summary="Detailed admin metrics")
async def admin_metrics():
    """Per-channel breakdown of agent metrics."""
    async with get_session() as session:
        result = await session.execute(
            select(
                AgentMetric.channel,
                func.count(AgentMetric.id).label("count"),
                func.avg(AgentMetric.processing_ms).label("avg_ms"),
                func.sum(
                    func.cast(AgentMetric.was_escalated, func.Integer())
                ).label("escalations"),
                func.avg(AgentMetric.confidence_score).label("confidence"),
            )
            .where(AgentMetric.created_at >= text("NOW() - INTERVAL '7 days'"))
            .group_by(AgentMetric.channel)
        )
        rows = result.all()

        return {
            "period": "last_7_days",
            "channels": [
                {
                    "channel": row.channel.value,
                    "total_requests": row.count,
                    "avg_processing_ms": round(row.avg_ms or 0, 2),
                    "escalations": int(row.escalations or 0),
                    "escalation_rate_pct": round(int(row.escalations or 0) / max(row.count, 1) * 100, 2),
                    "avg_confidence": round(row.confidence or 0, 4),
                }
                for row in rows
            ],
        }
