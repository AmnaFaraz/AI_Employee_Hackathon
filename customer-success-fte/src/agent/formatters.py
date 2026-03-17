"""
Channel-specific response formatters — Customer Success Digital FTE

Enforces per-channel tone, length, and style rules.
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass

from src.database.models import ChannelType


# ---------------------------------------------------------------------------
# Channel constraints
# ---------------------------------------------------------------------------

EMAIL_MAX_WORDS = 500
WEB_FORM_MAX_WORDS = 300
WHATSAPP_MAX_CHARS = 300  # preferred; hard limit 1600 for WhatsApp

CHANNEL_RULES = {
    ChannelType.EMAIL: {
        "tone": "formal",
        "max_words": EMAIL_MAX_WORDS,
        "style": "structured paragraphs with greeting and sign-off",
    },
    ChannelType.WHATSAPP: {
        "tone": "short conversational",
        "max_chars": WHATSAPP_MAX_CHARS,
        "style": "brief, friendly, direct",
    },
    ChannelType.WEB_FORM: {
        "tone": "semi-formal",
        "max_words": WEB_FORM_MAX_WORDS,
        "style": "clear and scannable",
    },
}


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _count_words(text: str) -> int:
    return len(text.split())


def _truncate_to_words(text: str, max_words: int) -> str:
    """Truncate text to at most max_words, preserving sentences where possible."""
    words = text.split()
    if len(words) <= max_words:
        return text
    truncated = " ".join(words[:max_words])
    # Try to end at a sentence boundary
    for sep in (". ", "! ", "? "):
        last = truncated.rfind(sep)
        if last > len(truncated) // 2:
            return truncated[: last + 1]
    return truncated + "…"


def _truncate_to_chars(text: str, max_chars: int) -> str:
    """Truncate text to at most max_chars, respecting word boundaries."""
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        truncated = truncated[:last_space]
    return truncated.rstrip() + "…"


# ---------------------------------------------------------------------------
# Formatter functions
# ---------------------------------------------------------------------------

@dataclass
class FormattedResponse:
    content: str
    channel: ChannelType
    word_count: int | None
    char_count: int


def format_email_response(
    raw_content: str,
    customer_name: str = "Valued Customer",
    ticket_number: int | None = None,
) -> FormattedResponse:
    """Format a response for the Email channel."""
    content = _truncate_to_words(raw_content, EMAIL_MAX_WORDS - 50)  # Reserve words for header/footer

    ref = f"[Ticket #{ticket_number}] " if ticket_number else ""

    formatted = (
        f"Dear {customer_name},\n\n"
        f"{ref}"
        f"{content}\n\n"
        f"If you have any further questions, please don't hesitate to reach out.\n\n"
        f"Warm regards,\n"
        f"Aria | Customer Success Team\n"
        f"support@company.com"
    )

    # Final word-count enforcement
    word_count = _count_words(formatted)
    if word_count > EMAIL_MAX_WORDS:
        # Re-truncate the core content more aggressively
        allowed = EMAIL_MAX_WORDS - 60
        content = _truncate_to_words(raw_content, allowed)
        formatted = (
            f"Dear {customer_name},\n\n"
            f"{ref}"
            f"{content}\n\n"
            f"Warm regards,\n"
            f"Aria | Customer Success Team"
        )
        word_count = _count_words(formatted)

    return FormattedResponse(
        content=formatted,
        channel=ChannelType.EMAIL,
        word_count=word_count,
        char_count=len(formatted),
    )


def format_whatsapp_response(
    raw_content: str,
    ticket_number: int | None = None,
) -> FormattedResponse:
    """Format a response for the WhatsApp channel."""
    # WhatsApp: concise, friendly
    content = _truncate_to_chars(raw_content, WHATSAPP_MAX_CHARS - 20)

    if ticket_number:
        suffix = f" (Ref #{ticket_number})"
        if len(content) + len(suffix) <= WHATSAPP_MAX_CHARS:
            content += suffix

    return FormattedResponse(
        content=content,
        channel=ChannelType.WHATSAPP,
        word_count=None,
        char_count=len(content),
    )


def format_webform_response(
    raw_content: str,
    customer_name: str = "there",
    ticket_number: int | None = None,
) -> FormattedResponse:
    """Format a response for the Web Support Form channel."""
    content = _truncate_to_words(raw_content, WEB_FORM_MAX_WORDS - 30)

    ref_line = f"📌 **Reference:** Ticket #{ticket_number}\n\n" if ticket_number else ""

    formatted = (
        f"Hi {customer_name},\n\n"
        f"{ref_line}"
        f"{content}\n\n"
        f"Feel free to reply if you need further assistance!"
    )

    word_count = _count_words(formatted)
    if word_count > WEB_FORM_MAX_WORDS:
        allowed = WEB_FORM_MAX_WORDS - 30
        content = _truncate_to_words(raw_content, allowed)
        formatted = f"Hi {customer_name},\n\n{ref_line}{content}\n\nFeel free to reply if you need more help!"

    return FormattedResponse(
        content=formatted,
        channel=ChannelType.WEB_FORM,
        word_count=_count_words(formatted),
        char_count=len(formatted),
    )


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def format_response(
    raw_content: str,
    channel: ChannelType,
    customer_name: str = "there",
    ticket_number: int | None = None,
) -> FormattedResponse:
    """Route to the appropriate formatter based on channel."""
    if channel == ChannelType.EMAIL:
        return format_email_response(raw_content, customer_name, ticket_number)
    elif channel == ChannelType.WHATSAPP:
        return format_whatsapp_response(raw_content, ticket_number)
    elif channel == ChannelType.WEB_FORM:
        return format_webform_response(raw_content, customer_name, ticket_number)
    else:
        raise ValueError(f"Unknown channel: {channel}")


def get_channel_prompt_instructions(channel: ChannelType) -> str:
    """Return LLM-facing instructions for channel-specific generation."""
    rules = CHANNEL_RULES.get(channel, {})
    if channel == ChannelType.EMAIL:
        return (
            f"Write a {rules['tone']} email response. "
            f"Maximum {rules['max_words']} words. "
            f"Use {rules['style']}. "
            "Do NOT include greeting/signature — those are added automatically."
        )
    elif channel == ChannelType.WHATSAPP:
        return (
            f"Write a {rules['tone']} WhatsApp message. "
            f"Maximum {rules['max_chars']} characters. "
            f"Style: {rules['style']}. "
            "Be very concise — every word counts."
        )
    elif channel == ChannelType.WEB_FORM:
        return (
            f"Write a {rules['tone']} web support response. "
            f"Maximum {rules['max_words']} words. "
            f"Style: {rules['style']}. "
            "Do NOT include greeting — that is added automatically."
        )
    return "Write a helpful support response."
