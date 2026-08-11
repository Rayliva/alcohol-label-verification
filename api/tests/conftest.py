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
from app.review.store import queue

TEST_USERNAME = "test-agent"
TEST_PASSWORD = "test-password"


@pytest.fixture(autouse=True)
def offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "anthropic_api_key", "")
    monkeypatch.setattr(settings, "google_application_credentials_json", "")
    monkeypatch.setattr(settings, "ocr_engine", "fake")
    # The app refuses to start without these, so that a public URL is never
    # served ungated. Tests supply their own rather than disabling the check.
    monkeypatch.setattr(settings, "agent_username", TEST_USERNAME)
    monkeypatch.setattr(settings, "agent_password", TEST_PASSWORD)
    monkeypatch.setattr(settings, "session_secret", "test-session-secret")


def sign_in(client) -> None:
    """Give a TestClient a session cookie. Every protected route needs one."""
    response = client.post(
        "/api/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
    )
    assert response.status_code == 200, response.text


@pytest.fixture(autouse=True)
def fresh_queue() -> None:
    """The queue is a process-wide singleton, so a decision made by one test
    would otherwise be visible to the next and the suite would depend on its
    own ordering."""
    queue._items.clear()
    queue._seeded = False
    yield
    queue._items.clear()
    queue._seeded = False
