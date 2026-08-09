# Multi-stage: dependencies resolved in the builder, only the runtime ships.
# Build context is api/ (Render root directory = api).

FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Dependency layer first so it caches independently of source changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --extra server --extra cloud-ocr

COPY app ./app
RUN uv sync --frozen --extra server --extra cloud-ocr


FROM python:3.12-slim AS runtime

# System libraries OpenCV links against. Installed now rather than at the
# point image preprocessing lands (PRD P1-11) so the dependency surface is
# proven by every deploy instead of discovered during one.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Never run as root.
RUN useradd --create-home --uid 10001 appuser

WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder --chown=appuser:appuser /app/.venv ./.venv
COPY --chown=appuser:appuser app ./app

USER appuser

# Render supplies $PORT. Default matches local dev.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
