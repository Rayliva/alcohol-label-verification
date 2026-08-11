"""Application settings, read from the process environment.

The app never reads a .env file directly — it reads environment variables.
Locally, pydantic-settings loads .env into that environment; in production
Render injects the same names. One code path, three sources.

See .claude/rules/secrets.md
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Credentials ---
    anthropic_api_key: str = ""
    google_application_credentials_json: str = ""

    # --- OCR ---
    ocr_engine: Literal["cloud", "paddle", "fake"] = "fake"

    # --- Models ---
    # Phase 0 benchmark winner (2026-08-09). See README -> Performance.
    extraction_model: str = "claude-haiku-4-5"
    vision_fallback_model: str = "claude-opus-5"

    # Thinking is never omitted. On Opus 5 the default is ON; on the previous
    # generation it was OFF. Inheriting a default that has already changed once
    # is how a latency budget gets spent silently.
    extraction_thinking: Literal["disabled", "adaptive"] = "disabled"

    # Must be "high" or lower when extraction_thinking == "disabled";
    # pairing "disabled" with xhigh/max returns a 400.
    extraction_effort: Literal["low", "medium", "high"] = "low"

    # --- Access ---
    # One shared agent credential, injected at runtime. There is no user table
    # and nothing is stored, so there is no password hash to keep — the value
    # is compared, in constant time, against what the environment supplies.
    # This is a gate on a public demo URL, not an identity system, and the
    # README says so.
    agent_username: str = ""
    agent_password: str = ""
    # Signs the session cookie. Unset means a fresh key per boot, which simply
    # means everyone signs in again after a restart.
    session_secret: str = ""

    # --- Server ---
    cors_origins: str = "http://localhost:5173"
    log_level: str = "INFO"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    def require_anthropic_key(self) -> str:
        """Return the Anthropic key, or fail loudly.

        Never log or echo the value — see .claude/rules/secrets.md.
        """
        if not self.anthropic_api_key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and fill it in."
            )
        return self.anthropic_api_key


settings = Settings()
