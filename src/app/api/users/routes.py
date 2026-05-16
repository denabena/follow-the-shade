from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.users.schemas import UserPreferences, UserPreferencesPatch
from app.auth.deps import require_user_id
from app.state import AppState, get_state

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/preferences", response_model=UserPreferences)
async def get_preferences(
    user_id: str = Depends(require_user_id),
    state: AppState = Depends(get_state),
) -> UserPreferences:
    data = state.preferences_store.get(user_id)
    return UserPreferences.model_validate(data)


@router.patch("/preferences", response_model=UserPreferences)
async def patch_preferences(
    patch: UserPreferencesPatch,
    user_id: str = Depends(require_user_id),
    state: AppState = Depends(get_state),
) -> UserPreferences:
    updates = patch.model_dump(exclude_none=True)
    data = state.preferences_store.update(user_id, updates)
    return UserPreferences.model_validate(data)
