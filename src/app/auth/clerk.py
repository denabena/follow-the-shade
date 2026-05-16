from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import jwt
from jwt import PyJWKClient

from core.config import settings

log = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _jwks_client() -> PyJWKClient | None:
    jwks_url = settings.clerk_jwks_url
    if not jwks_url:
        return None
    return PyJWKClient(jwks_url)


def verify_clerk_token(token: str) -> dict[str, Any] | None:
    if not token:
        return None

    decode_options: dict[str, Any] = {"verify_aud": False}
    decode_kwargs: dict[str, Any] = {
        "algorithms": ["RS256"],
        "options": decode_options,
    }
    if settings.CLERK_ISSUER:
        decode_kwargs["issuer"] = settings.CLERK_ISSUER

    try:
        if settings.CLERK_JWT_PUBLIC_KEY:
            return jwt.decode(
                token,
                settings.CLERK_JWT_PUBLIC_KEY,
                **decode_kwargs,
            )

        client = _jwks_client()
        if client is None:
            log.warning("Clerk JWT verification is not configured.")
            return None

        signing_key = client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            **decode_kwargs,
        )
    except jwt.PyJWTError as exc:
        log.info("Clerk token verification failed: %s", exc)
        return None


def user_id_from_token(token: str) -> str | None:
    payload = verify_clerk_token(token)
    if not payload:
        return None
    sub = payload.get("sub")
    return str(sub) if sub else None
