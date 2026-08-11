"""Findings from a security review, pinned so they cannot come back.

None of this makes the prototype an identity system — the brief rules that out.
It is the short list of things that are simply wrong: a session cookie that
travels in the clear, a login that 500s on a non-ASCII byte, a spreadsheet
export that executes when opened, and a form field that can stop a batch dead.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import TEST_PASSWORD, TEST_USERNAME, sign_in


@pytest.fixture
def client() -> TestClient:
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


class TestTheSessionCookieIsNotSentInTheClear:
    def test_the_cookie_is_marked_secure(self, client: TestClient) -> None:
        # It was derived from the CORS origin string, which on the deployed
        # instance still began with http://localhost — so the flag was off in
        # production, on HTTPS, where it matters. A cookie flag must not depend
        # on an unrelated setting.
        response = client.post(
            "/api/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        cookie = response.headers["set-cookie"].lower()
        assert "secure" in cookie
        assert "httponly" in cookie
        assert "samesite=lax" in cookie


class TestSigningInSurvivesOddInput:
    @pytest.mark.parametrize("username", ["é", "日本語", "\x00", "user​"])
    def test_a_non_ascii_username_is_refused_not_a_crash(
        self, client: TestClient, username: str
    ) -> None:
        # compare_digest raises TypeError on non-ASCII str. That turned any
        # such attempt into a 500 — and would have locked everyone out
        # permanently if the deployed password contained one such character.
        response = client.post("/api/login", json={"username": username, "password": TEST_PASSWORD})
        assert response.status_code == 401

    def test_a_non_ascii_password_is_refused_not_a_crash(self, client: TestClient) -> None:
        response = client.post(
            "/api/login", json={"username": TEST_USERNAME, "password": "pässwörd"}
        )
        assert response.status_code == 401


class TestTheExportDoesNotExecuteWhenOpened:
    @pytest.mark.parametrize("payload", ["=cmd|'/c calc'!A1", "+1+1", "-1+1", "@SUM(1)"])
    def test_a_formula_in_a_cell_is_neutralised(self, payload: str) -> None:
        # An importer supplies the manifest and a label carries printed text, so
        # both reach this file. An agent then opens it in Excel.
        from app.api.batch_routes import _csv_safe

        assert _csv_safe(payload).startswith("'")

    def test_ordinary_values_are_left_alone(self) -> None:
        from app.api.batch_routes import _csv_safe

        assert _csv_safe("OLD TOM DISTILLERY") == "OLD TOM DISTILLERY"
        assert _csv_safe("750 mL") == "750 mL"
        assert _csv_safe("") == ""


class TestConcurrencyCannotStallABatch:
    @pytest.mark.parametrize("concurrency", ["0", "-5", "999"])
    def test_an_out_of_range_worker_count_is_refused(
        self, client: TestClient, concurrency: str
    ) -> None:
        # Zero or negative killed the worker pool after the request had already
        # returned 200, leaving the job stuck at 0 with nothing on screen to
        # explain it. Large values remove the deliberate cap on provider calls.
        sign_in(client)
        response = client.post(
            "/api/batch",
            data={"concurrency": concurrency},
            files=[("images", ("a.png", b"not-an-image", "image/png"))],
        )
        assert response.status_code == 422
