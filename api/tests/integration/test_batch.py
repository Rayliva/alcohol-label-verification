"""Batch review — docs/specs/batch.md §4.

The brief's second explicit ask: *"during peak season, we get these big
importers who dump 200, 300 label applications on us at once… If there was some
way to handle batch uploads, that would be huge."*

The failure this suite guards against is a four-minute run that dies at minute
three on a problem visible at second one.
"""

from __future__ import annotations

import json
import time

import pytest
from fastapi.testclient import TestClient

from app.batch.manifest import ManifestError, parse, preflight, template_csv
from app.main import app
from tests.support import corpus

pytestmark = pytest.mark.integration

HEADER = (
    "application_id,image,beverage_type,brand_name,class_type,"
    "alcohol_content,net_contents,bottler_address,country_of_origin\n"
)


def row(image: str, application_id: str = "APP-1", **overrides: str) -> str:
    values = {
        "brand_name": "OLD TOM DISTILLERY",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "bottler_address": "Bottled by Old Tom Distillery, Bardstown, Kentucky",
        "country_of_origin": "",
        **overrides,
    }
    return (
        f'{application_id},{image},spirits,"{values["brand_name"]}",'
        f'"{values["class_type"]}","{values["alcohol_content"]}",'
        f'"{values["net_contents"]}","{values["bottler_address"]}",'
        f'"{values["country_of_origin"]}"\n'
    )


@pytest.fixture(scope="module")
def labels() -> dict[str, corpus.CorpusLabel]:
    return {label.label_id: label for label in corpus.load()}


class TestManifestParsing:
    def test_csv_and_json_produce_the_same_rows(self) -> None:
        csv_rows = parse((HEADER + row("a.png")).encode())
        json_rows = parse(
            json.dumps(
                [
                    {
                        "application_id": "APP-1",
                        "image": "a.png",
                        "beverage_type": "spirits",
                        "brand_name": "OLD TOM DISTILLERY",
                        "class_type": "Kentucky Straight Bourbon Whiskey",
                        "alcohol_content": "45% Alc./Vol. (90 Proof)",
                        "net_contents": "750 mL",
                        "bottler_address": "Bottled by Old Tom Distillery, Bardstown, Kentucky",
                    }
                ]
            ).encode()
        )
        assert csv_rows[0].image == json_rows[0].image
        assert csv_rows[0].fields["brand_name"] == json_rows[0].fields["brand_name"]

    def test_the_template_parses_through_the_same_parser(self) -> None:
        rows = parse(template_csv().encode())
        assert rows[0].image
        assert rows[0].fields["brand_name"]

    def test_a_file_with_the_wrong_columns_lists_the_expected_ones(self) -> None:
        with pytest.raises(ManifestError) as raised:
            parse(b"id,file,name,strength\nAPP-1,a.png,OLD TOM,45\n")
        assert "image" in raised.value.what_to_do
        assert raised.value.code == "manifest_columns_unrecognised"

    def test_an_empty_file_says_so(self) -> None:
        with pytest.raises(ManifestError) as raised:
            parse(b"")
        assert raised.value.what_to_do

    def test_a_header_with_no_rows_says_so(self) -> None:
        with pytest.raises(ManifestError) as raised:
            parse(HEADER.encode())
        assert raised.value.code == "manifest_no_rows"


class TestPreflight:
    def test_a_row_naming_a_missing_image_is_reported_with_its_row_number(self) -> None:
        rows = parse((HEADER + row("not-uploaded.png", "APP-9")).encode())
        report = preflight(rows, ["something-else.png"])
        detail = next(p.detail for p in report.problems if p.kind == "image_not_uploaded")
        assert "Row 1" in detail
        assert "not-uploaded.png" in detail
        assert "APP-9" in detail

    def test_an_image_named_in_no_row_is_reported_by_filename(self) -> None:
        rows = parse((HEADER + row("a.png")).encode())
        report = preflight(rows, ["a.png", "orphan.png"])
        detail = next(p.detail for p in report.problems if p.kind == "image_not_in_manifest")
        assert "orphan.png" in detail

    def test_a_row_missing_a_required_field_names_the_field(self) -> None:
        rows = parse((HEADER + row("a.png", brand_name="")).encode())
        report = preflight(rows, ["a.png"])
        detail = next(p.detail for p in report.problems if p.kind == "row_missing_field")
        assert "Row 1" in detail
        assert "brand name" in detail

    def test_good_rows_still_match_when_others_are_broken(self) -> None:
        rows = parse((HEADER + row("a.png", "APP-1") + row("missing.png", "APP-2")).encode())
        report = preflight(rows, ["a.png"])
        assert len(report.matched) == 1
        assert report.ready


class TestRunningABatch:
    @pytest.fixture()
    def client(self, monkeypatch, labels) -> TestClient:
        ocr = corpus.CorpusOcrEngine()
        by_text = {}
        for label in labels.values():
            try:
                by_text[ocr.extract(label.image_bytes).full_text] = label.detected
            except corpus.CorpusMissingError:
                continue

        class _Extraction:
            def __init__(self, fields):
                self.fields = fields

        monkeypatch.setattr("app.api.batch_routes.get_engine", lambda: ocr)
        monkeypatch.setattr("app.api.routes.get_engine", lambda: ocr)
        monkeypatch.setattr(
            "app.api.batch_routes.extract_from_text",
            lambda text, **_: _Extraction(by_text[text]),
        )
        with TestClient(app) as test_client:
            yield test_client

    def _upload(self, client, labels, ids):
        manifest = HEADER + "".join(
            row(labels[label_id].variant.image_name, f"APP-{index}")
            for index, label_id in enumerate(ids, start=1)
        )
        files = [
            ("images", (labels[i].variant.image_name, labels[i].image_bytes, "image/png"))
            for i in ids
        ]
        files.append(("manifest", ("manifest.csv", manifest.encode(), "text/csv")))
        return files

    def test_preflight_runs_before_anything_is_checked(self, client, labels) -> None:
        files = self._upload(client, labels, ["t1-clean-classic-1"])
        response = client.post("/api/batch/preflight", files=files)
        body = response.json()
        assert body["matched_count"] == 1
        assert body["ready"] is True

    def test_a_run_finishes_and_reports_every_label(self, client, labels) -> None:
        ids = ["t1-clean-classic-1", "t2-warning-title-case", "t2-volume-different"]
        started = client.post("/api/batch", files=self._upload(client, labels, ids)).json()
        job_id = started["job_id"]
        assert started["matched_count"] == 3

        deadline = time.time() + 30
        while time.time() < deadline:
            body = client.get(f"/api/batch/{job_id}").json()
            if body["state"] in ("finished", "stopped"):
                break
            time.sleep(0.05)

        assert body["state"] == "finished"
        assert body["done"] == body["total"] == 3
        assert {r["outcome"] for r in body["results"]} <= {
            "pass",
            "needs_review",
            "fail",
            "unreadable",
            "error",
        }

    def test_progress_is_determinate_throughout(self, client, labels) -> None:
        # "47 of 200 checked", never a spinner (accessibility rule 8).
        ids = ["t1-clean-classic-1", "t1-clean-modern-1"]
        job_id = client.post("/api/batch", files=self._upload(client, labels, ids)).json()["job_id"]
        body = client.get(f"/api/batch/{job_id}").json()
        assert body["total"] == 2
        assert 0 <= body["done"] <= body["total"]

    def test_the_time_estimate_is_measured_not_assumed(self, client, labels) -> None:
        ids = ["t1-clean-classic-1", "t1-clean-modern-1"]
        job_id = client.post("/api/batch", files=self._upload(client, labels, ids)).json()["job_id"]
        deadline = time.time() + 30
        while time.time() < deadline:
            body = client.get(f"/api/batch/{job_id}").json()
            if body["state"] == "finished":
                break
            time.sleep(0.05)
        assert body["seconds_per_label"] is not None

    def test_an_unreadable_label_is_its_own_bucket_and_does_not_stop_the_run(
        self, client, labels
    ) -> None:
        ids = ["t4-tiny", "t1-clean-classic-1"]
        job_id = client.post("/api/batch", files=self._upload(client, labels, ids)).json()["job_id"]
        deadline = time.time() + 30
        while time.time() < deadline:
            body = client.get(f"/api/batch/{job_id}").json()
            if body["state"] == "finished":
                break
            time.sleep(0.05)
        assert body["counts"]["unreadable"] == 1
        assert body["done"] == 2
        unreadable = next(r for r in body["results"] if r["outcome"] == "unreadable")
        assert unreadable["error"]["what_to_do"]

    def test_pre_flight_problems_travel_with_the_job(self, client, labels) -> None:
        files = self._upload(client, labels, ["t1-clean-classic-1"])
        files.append(
            ("images", ("orphan.png", labels["t1-clean-modern-1"].image_bytes, "image/png"))
        )
        body = client.post("/api/batch", files=files).json()
        assert any("orphan.png" in problem["detail"] for problem in body["problems"])

    def test_a_batch_that_matches_nothing_is_refused_with_a_reason(self, client, labels) -> None:
        manifest = HEADER + row("nothing-like-this.png")
        files = [
            (
                "images",
                ("a.png", labels["t1-clean-classic-1"].image_bytes, "image/png"),
            ),
            ("manifest", ("manifest.csv", manifest.encode(), "text/csv")),
        ]
        response = client.post("/api/batch", files=files)
        assert response.status_code == 400
        assert response.json()["detail"]["what_to_do"]

    def test_an_unknown_job_says_nothing_is_stored(self, client) -> None:
        response = client.get("/api/batch/deadbeef")
        assert response.status_code == 404
        assert "stored" in response.json()["detail"]["what_to_do"]

    def test_results_export_as_csv_problems_first(self, client, labels) -> None:
        ids = ["t1-clean-classic-1", "t2-volume-different"]
        job_id = client.post("/api/batch", files=self._upload(client, labels, ids)).json()["job_id"]
        deadline = time.time() + 30
        while time.time() < deadline:
            if client.get(f"/api/batch/{job_id}").json()["state"] == "finished":
                break
            time.sleep(0.05)
        text = client.get(f"/api/batch/{job_id}/export").text
        lines = text.strip().splitlines()
        assert lines[0].startswith("application_id,image,outcome")
        assert "fail" in lines[1]

    def test_the_template_is_downloadable(self, client) -> None:
        response = client.get("/api/batch/template")
        assert response.status_code == 200
        assert "image" in response.text.splitlines()[0]
