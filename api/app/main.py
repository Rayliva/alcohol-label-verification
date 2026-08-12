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
from pathlib import Path
from typing import Any

import structlog
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from app.api.batch_routes import router as batch_router
from app.api.review_routes import router as review_router
from app.api.routes import router
from app.auth import credentials_are_configured, require_agent
from app.config import settings
from app.errors import StartupError
from app.extraction.client import SYSTEM_PROMPT, extract_from_text
from app.review.store import queue

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
    if not credentials_are_configured():
        # Silent misconfiguration here means a public URL with no gate at all,
        # which is the kind of failure that has to be loud (rules/error-handling.md 3).
        raise StartupError(
            "AGENT_USERNAME and AGENT_PASSWORD must both be set. Without them "
            "the review queue would be served to anyone who finds the URL."
        )

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

    # Recorded results, read from disk. No OCR, no model call, no per-boot
    # cost — see app/review/store.py for why that is deliberate.
    _readiness["queue"] = f"seeded:{queue.seed()}"

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


# Everything that checks a label needs a session. Applied here rather than per
# route so a new endpoint is guarded by default — forgetting the decorator on
# one route is exactly how a gate develops a hole. /health stays open: it is
# how the platform decides whether this instance is alive.
_signed_in = [Depends(require_agent)]
app.include_router(router, dependencies=_signed_in)
app.include_router(batch_router, dependencies=_signed_in)
# Its own login and logout must stay reachable without a session.
app.include_router(review_router)


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
            f"See README > Measured results. Costs a little per request, changes no behaviour."
        )
    if _readiness["ocr"] == "fake":
        notes.append(
            "OCR is faked: one built-in sample label is returned for every image, "
            "so checks do not read the artwork supplied. "
            "Set OCR_ENGINE=cloud for real OCR."
        )
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


# The built frontend, served from the same origin as the API.
#
# **Registered last, deliberately.** A mount at "/" swallows every path beneath
# it, including routes declared after it — mounting this above /health took the
# health check off the air in production for the length of one deploy. Anything
# that must answer on its own path goes above this line.
#
# The tech spec puts the frontend on Vercel and that is still the production
# shape. Serving the bundle here as well makes the one deployed URL a working
# application rather than a JSON endpoint, which is what the brief asks for as a
# deliverable, and it removes CORS from the demo path entirely.
#
# app/static is built by `npm run build` in web/ and copied here; see the README.
_STATIC = Path(__file__).resolve().parent / "static"


@app.middleware("http")
async def html_is_never_cached(request, call_next):  # type: ignore[no-untyped-def]
    """The HTML entry must always be revalidated.

    The bundle's assets are content-hashed and each deploy deletes the old
    pair, so a browser that cached index.html keeps asking for assets that no
    longer exist — or, served from its own cache, keeps showing last week's
    UI while the changelog says otherwise. The assets themselves stay
    cacheable; only the document that names them must not be.
    """
    response = await call_next(request)
    if response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache"
    return response


if _STATIC.is_dir():
    app.mount("/", StaticFiles(directory=_STATIC, html=True), name="frontend")
else:
    log.warning(
        "frontend_not_built",
        hint="run npm run build in web/ and copy dist to app/static",
    )
