"""Test-wide guarantees.

The whole suite runs with no credentials and no network. A test that suddenly
needs either is a signal that something is reaching past a boundary it should be
mocked at (.claude/skills/run-tests.md).

This matters concretely: a developer with a populated .env would otherwise have
the FastAPI startup warmers fire real Anthropic requests on every TestClient
construction, which turned a 6-second suite into a 40-second one and billed for
the privilege.
"""

from __future__ import annotations

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "google_application_credentials_json", "")
    monkeypatch.setattr(settings, "ocr_engine", "fake")
