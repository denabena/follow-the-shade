from contextvars import ContextVar

current_thread_id: ContextVar[str] = ContextVar("current_thread_id", default="1")
current_user_query: ContextVar[str | None] = ContextVar(
    "current_user_query",
    default=None,
)
current_user_id: ContextVar[str | None] = ContextVar(
    "current_user_id",
    default=None,
)
