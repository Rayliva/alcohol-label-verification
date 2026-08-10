"""FastAPI entrypoint.

Startup runs the two warming calls described in docs/tech-spec.md. They are
separate because `max_tokens: 0` is rejected when a request also carries a
JSON schema, so one call warms the prompt cache and a second compiles the
schema.

Warming failures are loud but not fatal. A prototype that refuses to boot
because a cache did not engage is worse than one that serves a slightly
slower first request and says so on /health.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.config import settings
from app.extraction.client import SYSTEM_PROMPT, extract_from_text

log = structlog.get_logger()

# Populated at startup, reported by /health.
_readiness: dict[str, Any] = {
    "prompt_cache": "not_attempted",
    "schema": "not_attempted",
    "ocr": "not_attempted",
    "warm_ms": None,
}


def _warm_prompt_cache() -> str:
    """Prefill the cached system prompt. Returns a status string.

    `max_tokens=0` runs prefill and returns immediately with no output tokens
    billed. It cannot carry `output_config.format`, which is why schema
    warming is a separate call.
    """
    import anthropic

    client = anthropic.Anthropic(api_key=settings.require_anthropic_key())
    response = client.messages.create(
        model=settings.extraction_model,
        max_tokens=0,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral", "ttl": "1h"},
            }
        ],
        messages=[{"role": "user", "content": "warmup"}],
    )
    written = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
    read = getattr(response.usage, "cache_read_input_tokens", 0) or 0

    if written == 0 and read == 0:
        # Not fatal, but it means every request pays full input cost. The
        # minimum cacheable prefix differs by model and there is no error
        # when a prompt falls below it — this is the only way to notice.
        log.error(
            "prompt_cache_not_engaging",
            model=settings.extraction_model,
            hint="system prompt is likely below this model's minimum cacheable prefix",
        )
        return "not_engaging"
    return "warm"


def _warm_schema() -> str:
    """Compile the structured-output schema (cached ~24h) with one tiny call."""
    extract_from_text("warmup", model=settings.extraction_model)
    return "warm"


def _warm_ocr() -> str:
    """Prove the configured OCR engine actually works.

    Constructing the client only validates that the credentials JSON parses.
    Running one tiny extract additionally proves authentication, that the API
    is enabled, and that billing is attached — the failure that otherwise
    surfaces on a user's first upload rather than at boot.
    """
    import io

    from PIL import Image

    from app.ocr.factory import get_engine

    engine = get_engine()
    if engine.name == "fake":
        return "fake"

    buffer = io.BytesIO()
    Image.new("RGB", (32, 32), "white").save(buffer, format="PNG")
    engine.extract(buffer.getvalue())  # no text expected; the call succeeding is the point
    return "warm"


@asynccontextmanager
async def lifespan(_: FastAPI):
    started = time.perf_counter()
    stages: list[tuple[str, Any]] = [("ocr", _warm_ocr)]
    if settings.anthropic_api_key:
        stages += [("prompt_cache", _warm_prompt_cache), ("schema", _warm_schema)]
    else:
        _readiness["prompt_cache"] = _readiness["schema"] = "skipped_no_key"

    for name, fn in stages:
        try:
            _readiness[name] = fn()
        except Exception as exc:
            # The exception text goes to the log, which is authenticated. What
            # /health publishes is the failing stage and the exception type,
            # because a provider's message is third-party text and this endpoint
            # is open to anyone (.claude/rules/secrets.md).
            _readiness[name] = f"failed: {type(exc).__name__}"
            log.error("warmup_failed", stage=name, error=str(exc)[:500])

    _readiness["warm_ms"] = round((time.perf_counter() - started) * 1000)
    log.info("startup_complete", **_readiness, ocr_engine=settings.ocr_engine)
    yield


app = FastAPI(
    title="Alcohol Label Verification",
    description="Verifies label artwork against declared TTB COLA application data.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled(_request: Request, exc: Exception) -> JSONResponse:
    """The backstop. Nothing reaches an agent as a bare 500.

    An agent who reads "Internal Server Error" learns nothing, rejects the
    application, and concludes the tool wastes their time. Screen 7 of the UI
    spec has a line for this case; this handler is what populates it.
    """
    log.error("unhandled_error", error=f"{type(exc).__name__}: {str(exc)[:500]}")
    return JSONResponse(
        status_code=500,
        content={
            "code": "unexpected_error",
            "message": "Something went wrong while checking this label.",
            "what_to_do": "Try again. If it keeps happening, report it with the time.",
        },
    )


app.include_router(router)


@app.get("/health")
def health() -> dict[str, Any]:
    """Liveness plus warm state.

    Returns 200 even when warming did not fully succeed — the service is
    usable, just slower on first use. The body says which.
    """
    # "degraded" must mean actionable. A known and documented condition is
    # reported as a note instead, so the status field keeps its meaning.
    acceptable = ("warm", "fake", "not_engaging", "skipped_no_key")
    degraded = [k for k in ("prompt_cache", "schema", "ocr") if _readiness[k] not in acceptable]

    notes = []
    if _readiness["prompt_cache"] == "not_engaging":
        notes.append(
            f"Prompt caching is inactive: the system prompt is below "
            f"{settings.extraction_model}'s minimum cacheable prefix. Known and accepted "
            f"— see README > Performance. Costs a little per request, changes no behaviour."
        )
    if _readiness["ocr"] == "fake":
        notes.append("OCR is using deterministic fixtures. Set OCR_ENGINE=cloud for real OCR.")
    if _readiness["prompt_cache"] == "skipped_no_key":
        notes.append("ANTHROPIC_API_KEY is not set; extraction will fail.")

    return {
        "status": "ok" if not degraded else "degraded",
        "ocr_engine": settings.ocr_engine,
        "extraction_model": settings.extraction_model,
        "thinking": settings.extraction_thinking,
        "warmup": _readiness,
        "degraded": degraded,
        "notes": notes,
    }
