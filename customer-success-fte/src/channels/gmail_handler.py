"""
Gmail Channel Handler — Customer Success Digital FTE

Handles Gmail API OAuth2, webhook push notifications,
and sending email replies via the Gmail API.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/gmail.send",
]


# ---------------------------------------------------------------------------
# Gmail client
# ---------------------------------------------------------------------------

class GmailHandler:
    """Handles Gmail API operations for incoming and outgoing emails."""

    def __init__(self):
        self._service = None
        self._credentials_path = os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials/gmail_credentials.json")
        self._token_path = os.environ.get("GMAIL_TOKEN_PATH", "credentials/gmail_token.json")

    def _authenticate(self) -> None:
        """Authenticate with Gmail API using OAuth2."""
        creds = None

        if os.path.exists(self._token_path):
            creds = Credentials.from_authorized_user_file(self._token_path, GMAIL_SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # In production: use service account or pre-authorised token
                flow = InstalledAppFlow.from_client_secrets_file(
                    self._credentials_path, GMAIL_SCOPES
                )
                creds = flow.run_local_server(port=0)

            with open(self._token_path, "w") as token_file:
                token_file.write(creds.to_json())

        self._service = build("gmail", "v1", credentials=creds)
        logger.info("Gmail API authenticated")

    def get_service(self):
        if not self._service:
            self._authenticate()
        return self._service

    def parse_webhook_payload(self, payload: dict) -> Optional[dict]:
        """
        Parse Gmail Pub/Sub push notification payload.
        Returns normalised message data or None if not processable.
        """
        try:
            # Gmail sends base64-encoded Pub/Sub data
            data = payload.get("message", {}).get("data", "")
            if not data:
                return None

            decoded = json.loads(base64.b64decode(data).decode("utf-8"))
            history_id = decoded.get("historyId")
            email_address = decoded.get("emailAddress")

            return {
                "history_id": history_id,
                "email_address": email_address,
            }
        except Exception as exc:
            logger.error("Failed to parse Gmail webhook payload: %s", exc)
            return None

    def get_new_messages(self, history_id: str, user_id: str = "me") -> list[dict]:
        """
        Fetch new messages since a given history_id using Gmail API.
        Returns list of parsed email messages.
        """
        service = self.get_service()
        messages = []

        try:
            history_response = service.users().history().list(
                userId=user_id,
                startHistoryId=history_id,
                historyTypes=["messageAdded"],
                labelId="INBOX",
            ).execute()

            histories = history_response.get("history", [])
            for history in histories:
                for added_msg in history.get("messagesAdded", []):
                    msg_id = added_msg["message"]["id"]
                    full_msg = service.users().messages().get(
                        userId=user_id,
                        id=msg_id,
                        format="full",
                    ).execute()

                    parsed = self._parse_message(full_msg)
                    if parsed:
                        messages.append(parsed)

        except HttpError as exc:
            logger.error("Gmail API error fetching history: %s", exc)

        return messages

    def _parse_message(self, msg: dict) -> Optional[dict]:
        """Parse a Gmail message object into a normalised format."""
        headers = {
            h["name"].lower(): h["value"]
            for h in msg.get("payload", {}).get("headers", [])
        }

        sender_email = _extract_email(headers.get("from", ""))
        sender_name = _extract_name(headers.get("from", ""))
        subject = headers.get("subject", "(No Subject)")
        thread_id = msg.get("threadId", "")
        message_id = msg.get("id", "")

        body = _extract_body(msg.get("payload", {}))

        if not sender_email or not body:
            return None

        # Skip automated emails
        if any(
            keyword in sender_email.lower()
            for keyword in ["noreply", "no-reply", "mailer-daemon", "postmaster"]
        ):
            return None

        return {
            "sender_email": sender_email,
            "sender_name": sender_name,
            "subject": subject,
            "body": body,
            "thread_id": thread_id,
            "message_id": message_id,
        }

    def send_reply(
        self,
        to_email: str,
        subject: str,
        body: str,
        thread_id: str,
        user_id: str = "me",
    ) -> bool:
        """Send an email reply via Gmail API."""
        service = self.get_service()

        try:
            message = MIMEMultipart("alternative")
            message["To"] = to_email
            message["Subject"] = f"Re: {subject}" if not subject.startswith("Re:") else subject

            # Plain text part
            text_part = MIMEText(body, "plain")
            message.attach(text_part)

            # HTML part (basic formatting)
            html_body = body.replace("\n", "<br>")
            html_part = MIMEText(f"<html><body><p>{html_body}</p></body></html>", "html")
            message.attach(html_part)

            raw = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

            service.users().messages().send(
                userId=user_id,
                body={
                    "raw": raw,
                    "threadId": thread_id,
                },
            ).execute()

            logger.info("Email reply sent to %s | thread=%s", to_email, thread_id)
            return True

        except HttpError as exc:
            logger.error("Failed to send email reply: %s", exc)
            return False

    def setup_watch(self, topic_name: str, user_id: str = "me") -> dict:
        """
        Set up Gmail push notifications via Google Pub/Sub.
        Call this once to start receiving webhook notifications.
        """
        service = self.get_service()
        try:
            response = service.users().watch(
                userId=user_id,
                body={
                    "topicName": topic_name,
                    "labelIds": ["INBOX"],
                    "labelFilterAction": "include",
                },
            ).execute()
            logger.info("Gmail watch setup: %s", response)
            return response
        except HttpError as exc:
            logger.error("Failed to set up Gmail watch: %s", exc)
            raise


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _extract_email(from_header: str) -> str:
    """Extract email address from 'Name <email>' format."""
    import re
    match = re.search(r"<([^>]+)>", from_header)
    if match:
        return match.group(1).strip().lower()
    return from_header.strip().lower()


def _extract_name(from_header: str) -> str:
    """Extract display name from 'Name <email>' format."""
    import re
    match = re.match(r'^"?([^"<]+)"?\s*<', from_header)
    if match:
        return match.group(1).strip()
    return ""


def _extract_body(payload: dict) -> str:
    """Recursively extract text body from Gmail message payload."""
    mime_type = payload.get("mimeType", "")
    data = payload.get("body", {}).get("data", "")

    if mime_type in ("text/plain", "text/html") and data:
        text = base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
        if mime_type == "text/html":
            # Strip HTML tags for plain text extraction
            import re
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text).strip()
        return text

    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result

    return ""


# Module-level singleton
_handler: GmailHandler | None = None


def get_gmail_handler() -> GmailHandler:
    global _handler
    if _handler is None:
        _handler = GmailHandler()
    return _handler
