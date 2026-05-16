from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.api.notifications.schemas import (
    NotificationSchedule,
    NotificationScheduleUpsert,
    NotificationTestSendResponse,
)
from app.auth.deps import require_user_id
from app.state import AppState, get_state
from services.notifications.clerk_users import resolve_clerk_primary_email

router = APIRouter(prefix="/me/notifications", tags=["notifications"])


@router.get("", response_model=NotificationSchedule)
async def get_notification_schedule(
    user_id: str = Depends(require_user_id),
    state: AppState = Depends(get_state),
) -> NotificationSchedule:
    data = state.notification_store.get(user_id)
    return NotificationSchedule.model_validate(data)


@router.put("", response_model=NotificationSchedule)
async def put_notification_schedule(
    schedule: NotificationScheduleUpsert,
    user_id: str = Depends(require_user_id),
    state: AppState = Depends(get_state),
) -> NotificationSchedule:
    updates = schedule.model_dump(exclude_none=True)
    if updates.get("enabled") is True and "email" not in updates:
        stored = state.notification_store.get(user_id)
        if not stored.get("email"):
            email = await resolve_clerk_primary_email(
                user_id=user_id,
                secret_key=state.settings.CLERK_SECRET_KEY,
            )
            if email:
                updates["email"] = email
    data = state.notification_store.upsert(user_id, updates)
    return NotificationSchedule.model_validate(data)


@router.post("/test", response_model=NotificationTestSendResponse)
async def send_test_notification(
    user_id: str = Depends(require_user_id),
    state: AppState = Depends(get_state),
) -> NotificationTestSendResponse:
    if state.notification_dispatcher is None:
        raise HTTPException(
            status_code=503,
            detail="Notifications are disabled on this backend.",
        )

    schedule = state.notification_store.get(user_id)
    if not schedule.get("email"):
        email = await resolve_clerk_primary_email(
            user_id=user_id,
            secret_key=state.settings.CLERK_SECRET_KEY,
        )
        if email:
            schedule = state.notification_store.upsert(user_id, {"email": email})

    result = await state.notification_dispatcher.dispatch_user(
        user_id,
        schedule=schedule,
        force=True,
    )
    if result is None:
        return NotificationTestSendResponse(
            sent=False,
            detail=(
                "No notification was sent. Clerk did not return an email for "
                "this user, so save the notification schedule once or check "
                "CLERK_SECRET_KEY."
            ),
        )
    return NotificationTestSendResponse(
        sent=True,
        analysis_id=result.get("analysis_id"),
        subject=result.get("subject"),
    )
