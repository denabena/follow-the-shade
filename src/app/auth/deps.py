from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.clerk import user_id_from_token_async

_bearer = HTTPBearer(auto_error=False)


async def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    return await user_id_from_token_async(credentials.credentials)


def require_user_id(
    user_id: str | None = Depends(get_optional_user_id),
) -> str:
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user_id
