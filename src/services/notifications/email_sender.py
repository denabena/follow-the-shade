from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

log = logging.getLogger(__name__)


class NotificationSendError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResendEmailSender:
    api_key: str | None
    from_email: str
    dry_run: bool = True

    async def send(
        self,
        *,
        to: str,
        subject: str,
        html: str,
        text: str,
    ) -> dict[str, Any]:
        if self.dry_run:
            log.info(
                "Notification dry run to=%s subject=%s text=%s",
                to,
                subject,
                text,
            )
            return {"id": "dry-run", "dry_run": True}

        if not self.api_key:
            raise NotificationSendError("RESEND_API_KEY is not configured.")

        payload = {
            "from": self.from_email,
            "to": [to],
            "subject": subject,
            "html": html,
            "text": text,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    "https://api.resend.com/emails",
                    json=payload,
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            raise NotificationSendError("Resend request failed.") from exc

        if response.status_code >= 400:
            raise NotificationSendError(
                f"Resend returned {response.status_code}: {response.text[:300]}"
            )

        return response.json()
