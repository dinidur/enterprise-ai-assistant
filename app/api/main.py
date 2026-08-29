"""FastAPI application entry point.

Step 1 deliverable: a running async API with structured logging, request
correlation and centralised error handling. Chat, retrieval and agent routes
are added in later steps.
"""

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.exceptions import AppError
from app.core.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
)

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Start-up and shut-down hooks.

    Long-lived clients (Pinecone, the LLM, the MCP session) will be created
    here in later steps, so they are opened once per process rather than once
    per request.
    """
    configure_logging()
    log.info("application_startup", env=settings.app_env, model=settings.llm_model)
    yield
    log.info("application_shutdown")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# The Streamlit UI runs as a separate process, so it needs CORS.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Attach a request id to every log line and response, and time the call."""
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    bind_request_context(request_id=request_id, path=request.url.path)
    started = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        log.info("request_completed", duration_ms=duration_ms)
        clear_request_context()
    response.headers["x-request-id"] = request_id
    return response


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Map domain errors to clean API responses instead of leaking stack traces."""
    log.warning("app_error", code=exc.code, message=exc.message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    """Liveness probe used by Docker Compose and the UI."""
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
async def ready() -> dict[str, object]:
    """Readiness probe.

    Extended in later steps to check Pinecone, the LLM and the MCP server.
    """
    return {
        "status": "ok",
        "dependencies": {
            "vector_db": "not_configured",
            "llm": "not_configured",
            "langsmith": settings.langsmith_tracing,
        },
    }
