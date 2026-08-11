"""The HTTP surface — docs/ui-spec.md → Data shape.

Driven through the real app with the corpus behind it, so what is under test is
the contract the frontend will code against.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import sign_in
from tests.support import corpus

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def labels() -> dict[str, corpus.CorpusLabel]:
    return {label.label_id: label for label in corpus.load()}


@pytest.fixture()
def client(monkeypatch, labels) -> TestClient:
    """The app with its two boundaries — OCR and the model — replaced."""
    ocr = corpus.CorpusOcrEngine()
    detected = {label.label_id: label.detected for label in labels.values()}
    by_text: dict[str, object] = {}
    for label in labels.values():
        try:
            by_text[ocr.extract(label.image_bytes).full_text] = detected[label.label_id]
        except corpus.CorpusMissingError:
            continue

    class _Extraction:
        def __init__(self, fields):
            self.fields = fields

    monkeypatch.setattr("app.api.routes.get_engine", lambda: ocr)
    monkeypatch.setattr(
        "app.api.routes.extract_from_text",
        lambda text, **_: _Extraction(by_text[text]),
    )
    with TestClient(app, base_url="https://testserver") as test_client:
        sign_in(test_client)
        yield test_client


def post(client: TestClient, label: corpus.CorpusLabel, **overrides):
    declared = {**label.variant.application, **overrides}
    return client.post(
        "/api/verify",
        files={"image": (label.variant.image_name, label.image_bytes, "image/png")},
        data={
            "beverage_type": label.variant.beverage_type,
            "application_id": label.label_id,
            **{k: v for k, v in declared.items() if v is not None},
        },
    )


class TestVerifyRoute:
    def test_a_compliant_label_returns_a_pass(self, client, labels) -> None:
        body = post(client, labels["t1-clean-classic-1"]).json()
        assert body["overall"] == "pass"

    def test_the_response_carries_the_shape_the_ui_was_designed_against(
        self, client, labels
    ) -> None:
        body = post(client, labels["t1-clean-classic-1"]).json()
        for key in ("label_id", "beverage_type", "overall", "processing_ms", "fields"):
            assert key in body
        first = body["fields"][0]
        for key in ("field", "display_name", "declared", "detected", "verdict", "reason"):
            assert key in first

    def test_every_field_carries_its_regulation(self, client, labels) -> None:
        body = post(client, labels["t1-clean-classic-1"]).json()
        assert all("CFR" in field["citation"] for field in body["fields"])

    def test_the_warning_sub_checks_come_back_named_for_a_person(self, client, labels) -> None:
        body = post(client, labels["t1-clean-classic-1"]).json()
        names = {check["display_name"] for check in body["warning_checks"]}
        assert "GOVERNMENT WARNING in capital letters" in names

    def test_an_evidence_crop_comes_back_with_each_field_found(self, client, labels) -> None:
        body = post(client, labels["t1-clean-classic-1"]).json()
        brand = next(f for f in body["fields"] if f["field"] == "brand_name")
        assert brand["crop_url"].startswith("data:image/png;base64,")

    def test_a_field_absent_from_the_label_has_no_crop(self, client, labels) -> None:
        body = post(client, labels["t2-brand-missing"]).json()
        brand = next(f for f in body["fields"] if f["field"] == "brand_name")
        assert brand["crop_url"] is None
        assert brand["verdict"] == "fail"

    def test_a_violation_is_reported_with_a_readable_reason(self, client, labels) -> None:
        body = post(client, labels["t2-warning-title-case"]).json()
        assert body["overall"] == "fail"
        caps = next(c for c in body["warning_checks"] if c["check"] == "caps")
        assert "capital letters" in caps["reason"]

    def test_per_stage_timings_are_reported(self, client, labels) -> None:
        body = post(client, labels["t1-clean-classic-1"]).json()
        assert body["stage_ms"]["ocr_ms"] >= 0
        assert body["processing_ms"] >= 0


class TestUnreadableImages:
    def test_an_unreadable_image_is_an_outcome_not_an_error_status(self, client, labels) -> None:
        # It is one of four label outcomes and the client renders it the same
        # way it renders a verdict (ui-spec resolution 2).
        response = post(client, labels["t4-tiny"])
        assert response.status_code == 200
        body = response.json()
        assert body["overall"] == "unreadable"

    def test_the_error_says_what_happened_and_what_to_do(self, client, labels) -> None:
        body = post(client, labels["t4-blur-heavy"]).json()
        assert body["error"]["code"] == "image_too_blurry"
        assert body["error"]["what_to_do"]

    def test_an_unreadable_label_reports_no_verdicts(self, client, labels) -> None:
        body = post(client, labels["t4-near-black"]).json()
        assert body["fields"] == []


class TestRequestErrors:
    def test_a_beverage_type_that_is_not_ready_says_so(self, client, labels) -> None:
        response = post(client, labels["t1-clean-classic-1"], **{})
        assert response.status_code == 200
        wine = client.post(
            "/api/verify",
            files={"image": ("x.png", labels["t1-clean-classic-1"].image_bytes, "image/png")},
            data={"beverage_type": "wine", "brand_name": "X"},
        )
        assert wine.status_code == 400
        assert "coming next" in wine.json()["detail"]["message"]

    def test_an_unknown_beverage_type_lists_the_known_ones(self, client, labels) -> None:
        response = client.post(
            "/api/verify",
            files={"image": ("x.png", labels["t1-clean-classic-1"].image_bytes, "image/png")},
            data={"beverage_type": "mead"},
        )
        assert response.status_code == 400
        assert "spirits" in response.json()["detail"]["message"]

    def test_a_file_that_is_not_an_image_says_so(self, client) -> None:
        response = client.post(
            "/api/verify",
            files={"image": ("notes.txt", b"just some text", "text/plain")},
            data={"beverage_type": "spirits"},
        )
        assert response.json()["error"]["code"] == "unsupported_file"


class TestBeverageTypesRoute:
    def test_all_three_types_are_offered(self, client) -> None:
        body = client.get("/api/beverage-types").json()
        assert {option["beverage_type"] for option in body} == {"spirits", "wine", "malt"}

    def test_an_unavailable_option_explains_itself(self, client) -> None:
        # A disabled control that does not say why is a dead end
        # (.claude/rules/accessibility.md, rule 9).
        body = client.get("/api/beverage-types").json()
        for option in body:
            if not option["available"]:
                assert option["unavailable_reason"]

    def test_the_conditional_alcohol_rule_reaches_the_form(self, client) -> None:
        body = client.get("/api/beverage-types").json()
        wine = next(o for o in body if o["beverage_type"] == "wine")
        assert wine["alcohol_content_required"] is False
        assert "table wine" in wine["alcohol_content_note"]


class TestRoutesAreReachable:
    """A mount at "/" swallows every path beneath it.

    Registering the frontend above /health took the health check off the air in
    production for the length of one deploy. This is the test that would have
    caught it.
    """

    def test_every_named_route_answers_on_its_own_path(self, client) -> None:
        for path in ("/health", "/api/beverage-types", "/api/batch/template", "/docs"):
            assert client.get(path).status_code == 200, path

    def test_the_frontend_is_served_at_the_root(self, client) -> None:
        response = client.get("/")
        assert response.status_code == 200
        assert "<!doctype html>" in response.text.lower()
