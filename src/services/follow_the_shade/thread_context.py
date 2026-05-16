from contextvars import ContextVar

current_thread_id: ContextVar[str] = ContextVar("current_thread_id", default="1")
