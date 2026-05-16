import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat.routes import router as chat_router
from app.lifespan import lifespan

log = logging.getLogger(__name__)

app = FastAPI(
    title="Follow the Shade Agent",
    description="Split cafe sun and shade chatbot backend.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "follow-the-shade-agent"}


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": "Follow the Shade Agent",
        "chat_endpoint": "/chat/final_answer",
        "health": "/health",
    }


if __name__ == "__main__":
    log.info("Starting Follow the Shade FastAPI server...")

    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
