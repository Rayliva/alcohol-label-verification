"""Nothing that reads a label is reachable without signing in.

The deployed URL is public. The gate is not an identity system — one shared
credential, no accounts, nothing stored — but it has to actually hold, and it
has to hold on every route rather than the ones someone remembered to decorate.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from tests.conftest import TEST_PASSWORD, TEST_USERNAME, sign_in


def a_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (900, 1200), "white").save(buffer, "PNG")
    return buffer.getvalue()


@pytest.fixture
def client() -> TestClient:
    with TestClient(app, base_url="https://testserver") as test_client:
        yield test_client


class TestTheGateHolds:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("get", "/api/queue"),
            ("get", "/api/queue/001_bourbon_clean"),
            ("get", "/api/queue/001_bourbon_clean/image"),
            ("post", "/api/queue/001_bourbon_clean/decision"),
            ("post", "/api/verify"),
            ("get", "/api/beverage-types"),
        ],
    )
    def test_a_signed_out_request_is_refused(
        self, client: TestClient, method: str, path: str
    ) -> None:
        response = getattr(client, method)(path)
        assert response.status_code == 401

    def test_the_refusal_says_what_to_do(self, client: TestClient) -> None:
        body = client.get("/api/queue").json()["detail"]
        assert body["code"] == "not_signed_in"
        assert body["what_to_do"]

    def test_health_stays_open(self, client: TestClient) -> None:
        # The platform calls this to decide whether the instance is alive.
        assert client.get("/health").status_code == 200

    def test_a_forged_cookie_is_not_a_session(self, client: TestClient) -> None:
        client.cookies.set("label_check_session", "eyJ1IjoiYWdlbnQifQ==.not-a-signature")
        assert client.get("/api/queue").status_code == 401


class TestSigningIn:
    def test_the_wrong_password_is_refused(self, client: TestClient) -> None:
        response = client.post("/api/login", json={"username": TEST_USERNAME, "password": "wrong"})
        assert response.status_code == 401

    def test_the_message_does_not_say_which_half_was_wrong(self, client: TestClient) -> None:
        wrong_user = client.post(
            "/api/login", json={"username": "nobody", "password": TEST_PASSWORD}
        ).json()["detail"]["message"]
        wrong_password = client.post(
            "/api/login", json={"username": TEST_USERNAME, "password": "wrong"}
        ).json()["detail"]["message"]
        assert wrong_user == wrong_password

    def test_signing_in_opens_the_queue(self, client: TestClient) -> None:
        sign_in(client)
        assert client.get("/api/queue").status_code == 200

    def test_signing_out_closes_it_again(self, client: TestClient) -> None:
        sign_in(client)
        client.post("/api/logout")
        assert client.get("/api/queue").status_code == 401

    def test_the_cookie_is_not_readable_by_scripts(self, client: TestClient) -> None:
        response = client.post(
            "/api/login", json={"username": TEST_USERNAME, "password": TEST_PASSWORD}
        )
        assert "httponly" in response.headers["set-cookie"].lower()


class TestTheQueue:
    def test_it_arrives_seeded(self, client: TestClient) -> None:
        sign_in(client)
        body = client.get("/api/queue").json()
        assert len(body["items"]) == 31

    def test_judgment_calls_sort_above_settled_ones(self, client: TestClient) -> None:
        sign_in(client)
        outcomes = [i["outcome"] for i in client.get("/api/queue").json()["items"]]
        assert outcomes[0] == "needs_review"
        assert outcomes.index("pass") > outcomes.index("fail")

    def test_a_seeded_row_carries_its_recorded_timing(self, client: TestClient) -> None:
        sign_in(client)
        items = client.get("/api/queue").json()["items"]
        timed = [i for i in items if i["outcome"] != "unreadable"]
        assert all(i["processing_ms"] > 0 for i in timed)

    def test_the_detail_view_carries_the_full_result(self, client: TestClient) -> None:
        sign_in(client)
        body = client.get("/api/queue/001_bourbon_clean").json()
        assert body["result"]["overall"] == "pass"
        assert body["result"]["fields"]

    def test_an_unknown_application_says_so(self, client: TestClient) -> None:
        sign_in(client)
        response = client.get("/api/queue/not-a-real-id")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "application_not_found"

    def test_a_decision_is_recorded_against_the_row(self, client: TestClient) -> None:
        sign_in(client)
        client.post(
            "/api/queue/001_bourbon_clean/decision",
            json={"action": "approve", "note": "Checked against the application."},
        )
        body = client.get("/api/queue/001_bourbon_clean").json()
        assert body["decision"]["action"] == "approve"
        assert body["decision"]["decided_by"] == TEST_USERNAME

    def test_a_decided_row_drops_below_the_undecided(self, client: TestClient) -> None:
        sign_in(client)
        first = client.get("/api/queue").json()["items"][0]["id"]
        client.post(f"/api/queue/{first}/decision", json={"action": "approve"})
        assert client.get("/api/queue").json()["items"][0]["id"] != first
