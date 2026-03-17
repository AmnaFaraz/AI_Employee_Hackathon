"""
Twilio WhatsApp Channel Handler — Customer Success Digital FTE

Handles incoming WhatsApp webhook events from Twilio
and sends replies via Twilio Messaging API.
"""
from __future__ import annotations

import logging
import os
from typing import Optional
from urllib.parse import parse_qs

from twilio.request_validator import RequestValidator
from twilio.rest import Client as TwilioClient

logger = logging.getLogger(__name__)


class WhatsAppHandler:
    """Handles Twilio WhatsApp webhook events and message sending."""

    def __init__(self):
        self._account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self._auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self._whatsapp_number = os.environ.get("TWILIO_WHATSAPP_NUMBER", "")
        self._client: TwilioClient | None = None
        self._validator: RequestValidator | None = None

    def _get_client(self) -> TwilioClient:
        if not self._client:
            if not self._account_sid or not self._auth_token:
                raise RuntimeError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set")
            self._client = TwilioClient(self._account_sid, self._auth_token)
        return self._client

    def _get_validator(self) -> RequestValidator:
        if not self._validator:
            self._validator = RequestValidator(self._auth_token)
        return self._validator

    def validate_signature(
        self,
        url: str,
        params: dict,
        twilio_signature: str,
    ) -> bool:
        """
        Validate that the webhook request came from Twilio.
        Should be called before processing any webhook.
        """
        validator = self._get_validator()
        return validator.validate(url, params, twilio_signature)

    def parse_webhook(self, form_data: dict | str) -> Optional[dict]:
        """
        Parse a Twilio WhatsApp webhook POST body.

        Args:
            form_data: URL-encoded form body as dict or string.

        Returns:
            Normalised message dict or None if not a valid message.
        """
        if isinstance(form_data, str):
            parsed = parse_qs(form_data)
            # parse_qs returns lists; flatten
            form_data = {k: v[0] for k, v in parsed.items()}

        # Check it's an inbound message
        if not form_data.get("Body"):
            return None

        from_number = form_data.get("From", "")
        if from_number.startswith("whatsapp:"):
            from_number = from_number[len("whatsapp:"):]

        profile_name = form_data.get("ProfileName", "")
        body = form_data.get("Body", "")
        message_sid = form_data.get("MessageSid", "")
        conversation_sid = form_data.get("ConversationSid", "")

        return {
            "sender_phone": from_number,
            "sender_name": profile_name,
            "body": body,
            "message_sid": message_sid,
            "conversation_sid": conversation_sid,
            "num_media": int(form_data.get("NumMedia", "0")),
            "raw": form_data,
        }

    def send_message(
        self,
        to_number: str,
        body: str,
        conversation_sid: str = "",
    ) -> bool:
        """
        Send a WhatsApp message via Twilio.

        Args:
            to_number: Recipient's phone number (with country code, no 'whatsapp:' prefix).
            body: Message text (≤1600 chars; preferred ≤300).
            conversation_sid: Optional Twilio Conversations SID for threading.
        """
        client = self._get_client()
        from_wa = f"whatsapp:{self._whatsapp_number}"
        to_wa = f"whatsapp:{to_number}"

        try:
            if conversation_sid:
                # Send within a Twilio Conversation thread
                client.conversations.v1.conversations(conversation_sid).messages.create(
                    author=from_wa,
                    body=body,
                )
            else:
                # Standalone message
                client.messages.create(
                    from_=from_wa,
                    to=to_wa,
                    body=body,
                )

            logger.info("WhatsApp message sent to %s", to_number)
            return True

        except Exception as exc:
            logger.error("Failed to send WhatsApp message to %s: %s", to_number, exc)
            return False

    def send_template_message(
        self,
        to_number: str,
        template_sid: str,
        template_variables: dict | None = None,
    ) -> bool:
        """
        Send a WhatsApp approved template message (required for first-touch outbound).
        """
        client = self._get_client()
        try:
            import json
            client.messages.create(
                from_=f"whatsapp:{self._whatsapp_number}",
                to=f"whatsapp:{to_number}",
                content_sid=template_sid,
                content_variables=json.dumps(template_variables or {}),
            )
            logger.info("WhatsApp template sent to %s | template=%s", to_number, template_sid)
            return True
        except Exception as exc:
            logger.error("Failed to send WhatsApp template: %s", exc)
            return False


# Module-level singleton
_handler: WhatsAppHandler | None = None


def get_whatsapp_handler() -> WhatsAppHandler:
    global _handler
    if _handler is None:
        _handler = WhatsAppHandler()
    return _handler
