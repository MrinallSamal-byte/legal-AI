"""Lexa API entrypoint."""
from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import settings
from .db import init_db
from .logging_config import configure_logging, get_logger
from .ratelimit import rate_limit
from .routers import account, auth, billing, chat

configure_logging()
log = get_logger("lexa")

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.auto_create_tables:
        init_db()
    try:
        from .rag.retriever import get_retriever
        get_retriever().ensure_seeded()
    except Exception as e:  # noqa: BLE001
        log.warning("retriever warmup skipped", extra={"extra_fields": {"error": str(e)}})
    yield


app = FastAPI(
    title="Lexa - Legal AI Assistant",
    description="Grounded, cited legal research with tiered models and a verification "
                "agent. Informational only - not legal advice.",
    version="1.0.0",
    lifespan=lifespan,
)
if settings.auto_create_tables:
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,  # bearer-token auth; wildcard origins + credentials is invalid
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.error("unhandled error", extra={"extra_fields": {"path": str(request.url.path)}}, exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "provider": settings.llm_provider,
            "embeddings": settings.embeddings_backend}


_rl = [Depends(rate_limit)]
app.include_router(auth.router, dependencies=_rl)
app.include_router(chat.router, dependencies=_rl)
app.include_router(billing.router, dependencies=_rl)
app.include_router(account.router, dependencies=_rl)


if os.path.isdir(FRONTEND_DIR):
    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

    app.mount("/app", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
