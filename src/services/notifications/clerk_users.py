from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)


async def resolve_clerk_primary_email(
    *,
    user_id: str,
    secret_key: str | None,
) -> str | None:
    if not secret_key:
        return None

    headers = {"Authorization": f"Bearer {secret_key}"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"https://api.clerk.com/v1/users/{user_id}",
                headers=headers,
            )
    except httpx.HTTPError as exc:
        log.warning("Could not fetch Clerk user %s: %s", user_id, exc)
        return None

    if response.status_code >= 400:
        log.warning("Clerk user lookup failed with status %s", response.status_code)
        return None

    data = response.json()
    primary_id = data.get("primary_email_address_id")
    emails = data.get("email_addresses")
    if not primary_id or not isinstance(emails, list):
        return None

    for email in emails:
        address = _email_from_entry(email)
        if email.get("id") == primary_id and address:
            return address
    return None


def _email_from_entry(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return None
    address = entry.get("email_address")
    return str(address) if address else None
