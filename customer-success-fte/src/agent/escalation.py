"""
Escalation rules engine — Customer Success Digital FTE

Determines whether an incoming message requires human escalation
based on content analysis and OpenAI sentiment detection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from openai import AsyncOpenAI


# ---------------------------------------------------------------------------
# Escalation Reasons
# ---------------------------------------------------------------------------

class EscalationReason(str, Enum):
    REFUND_REQUEST       = "REFUND_REQUEST"
    PRICING_NEGOTIATION  = "PRICING_NEGOTIATION"
    LEGAL_QUESTION       = "LEGAL_QUESTION"
    ANGRY_SENTIMENT      = "ANGRY_SENTIMENT"
    HUMAN_REQUEST        = "HUMAN_REQUEST"
    HIGH_VALUE_CUSTOMER  = "HIGH_VALUE_CUSTOMER"
    REPEATED_ISSUE       = "REPEATED_ISSUE"


# ---------------------------------------------------------------------------
# Keyword patterns
# ---------------------------------------------------------------------------

REFUND_PATTERNS = re.compile(
    r"\b(refund|chargeback|money.?back|reimburs|cancel.{0,20}subscription|"
    r"get.{0,15}money|dispute|reverse.{0,15}charge)\b",
    re.IGNORECASE,
)

PRICING_PATTERNS = re.compile(
    r"\b(discount|negotiate|better.{0,15}price|lower.{0,15}price|"
    r"competitor.{0,15}offer|match.{0,15}price|enterprise.{0,15}deal|"
    r"custom.{0,15}pricing|annual.{0,15}plan.{0,15}discount)\b",
    re.IGNORECASE,
)

LEGAL_PATTERNS = re.compile(
    r"\b(lawyer|attorney|lawsuit|sue|legal.{0,15}action|court|GDPR|"
    r"data.{0,15}breach|regulatory|compliance|violation|contract.{0,15}breach|"
    r"arbitration|class.{0,15}action)\b",
    re.IGNORECASE,
)

HUMAN_REQUEST_PATTERNS = re.compile(
    r"\b(speak.{0,15}human|talk.{0,15}person|real.{0,15}agent|"
    r"human.{0,15}agent|manager|supervisor|escalat|not.{0,15}bot|"
    r"transfer.{0,15}me)\b",
    re.IGNORECASE,
)

ANGER_PATTERNS = re.compile(
    r"\b(unacceptable|outrage|furious|disgusting|horrible|terrible|"
    r"worst.{0,15}ever|never.{0,15}again|scam|fraud|useless|incompetent|"
    r"waste.{0,15}of.{0,15}time|absolutely.{0,15}ridiculous|disappoint|"
    r"fed.{0,15}up|had.{0,15}enough)\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Escalation result
# ---------------------------------------------------------------------------

@dataclass
class EscalationResult:
    should_escalate: bool
    reason: Optional[EscalationReason] = None
    confidence: float = 0.0
    triggered_patterns: list[str] = field(default_factory=list)
    notes: str = ""


# ---------------------------------------------------------------------------
# Rules engine
# ---------------------------------------------------------------------------

class EscalationEngine:
    """
    Two-stage escalation detection:
    1. Fast regex keyword matching (< 1 ms)
    2. Optional LLM sentiment analysis for edge cases
    """

    def __init__(self, openai_client: AsyncOpenAI | None = None):
        self._client = openai_client

    def check_keywords(self, text: str) -> EscalationResult:
        """Synchronous keyword-based check. Always runs first."""
        triggered = []

        if REFUND_PATTERNS.search(text):
            triggered.append(EscalationReason.REFUND_REQUEST)

        if PRICING_PATTERNS.search(text):
            triggered.append(EscalationReason.PRICING_NEGOTIATION)

        if LEGAL_PATTERNS.search(text):
            triggered.append(EscalationReason.LEGAL_QUESTION)

        if HUMAN_REQUEST_PATTERNS.search(text):
            triggered.append(EscalationReason.HUMAN_REQUEST)

        if ANGER_PATTERNS.search(text):
            triggered.append(EscalationReason.ANGRY_SENTIMENT)

        if triggered:
            primary_reason = triggered[0]
            return EscalationResult(
                should_escalate=True,
                reason=primary_reason,
                confidence=0.95,
                triggered_patterns=[r.value for r in triggered],
                notes=f"Keyword match: {', '.join(r.value for r in triggered)}",
            )

        return EscalationResult(should_escalate=False, confidence=0.8)

    async def check_sentiment(self, text: str) -> EscalationResult:
        """
        Use GPT to detect nuanced anger/frustration not caught by keywords.
        Only called when keyword check returns False.
        """
        if not self._client:
            return EscalationResult(should_escalate=False)

        try:
            response = await self._client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a sentiment classifier for customer support. "
                            "Classify the customer message sentiment. "
                            "Reply ONLY with JSON: "
                            '{"escalate": true/false, "reason": "ANGRY_SENTIMENT|null", "score": 0.0-1.0}'
                        ),
                    },
                    {"role": "user", "content": text[:1000]},  # Cap for cost control
                ],
                temperature=0,
                max_tokens=60,
                response_format={"type": "json_object"},
            )
            import json
            result = json.loads(response.choices[0].message.content or "{}")
            if result.get("escalate") and result.get("score", 0) > 0.75:
                return EscalationResult(
                    should_escalate=True,
                    reason=EscalationReason.ANGRY_SENTIMENT,
                    confidence=result.get("score", 0.8),
                    notes="LLM sentiment analysis triggered escalation",
                )
        except Exception:
            pass  # Fail open — don't escalate on analysis error

        return EscalationResult(should_escalate=False, confidence=0.7)

    async def evaluate(self, text: str, open_ticket_count: int = 0) -> EscalationResult:
        """
        Full escalation evaluation:
        1. Keyword match
        2. Repeated issue check
        3. LLM sentiment (async)
        """
        # Stage 1: keyword check
        result = self.check_keywords(text)
        if result.should_escalate:
            return result

        # Stage 2: repeated issue
        if open_ticket_count >= 3:
            return EscalationResult(
                should_escalate=True,
                reason=EscalationReason.REPEATED_ISSUE,
                confidence=0.85,
                notes=f"Customer has {open_ticket_count} open tickets — repeated issue flag",
            )

        # Stage 3: LLM sentiment
        return await self.check_sentiment(text)


# Module-level singleton (can be overridden in tests)
_engine: EscalationEngine | None = None


def get_escalation_engine(openai_client: AsyncOpenAI | None = None) -> EscalationEngine:
    global _engine
    if _engine is None:
        _engine = EscalationEngine(openai_client)
    return _engine
