"""Inputs that are not the happy path — regressions from the pre-push review.

Every test here reproduces a defect found by review on 2026-08-09. They are
grouped by what an agent would actually have seen: a bare 500, a compliant
label rejected as damaged, or a violation quietly downgraded.
"""

from __future__ import annotations

from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from app.errors import ExtractionError, UnreadableImageError
from app.main import app
from app.ocr.base import BoundingBox, OcrResult, TextBlock
from app.pipeline import verify
from app.pipeline.measure import measure
from app.pipeline.quality import require_readable
from app.rules.engine import Application
from app.rules.types import Verdict, WarningCheckName
from app.rules.warning import STATUTORY_WARNING, check_warning
from tests.conftest import sign_in
from tests.support import corpus

pytestmark = pytest.mark.integration


def png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(scope="module")
def labels() -> dict[str, corpus.CorpusLabel]:
    return {label.label_id: label for label in corpus.load()}


@pytest.fixture(scope="module")
def ocr() -> corpus.CorpusOcrEngine:
    return corpus.CorpusOcrEngine()


class TestMalformedFiles:
    """None of these may reach the client as an untyped 500.

    Every error surfaced in the UI has to say what went wrong and what to do
    about it (.claude/rules/error-handling.md).
    """

    def test_a_decompression_bomb_is_reported_not_crashed(self, labels, ocr) -> None:
        # 68 bytes on disk, 30000x30000 declared. The upload size check cannot
        # see it.
        bomb = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
            b"\x00\x00\x75\x30\x00\x00\x75\x30\x08\x02\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        with pytest.raises(UnreadableImageError) as raised:
            verify(
                bomb,
                labels["t1-clean-classic-1"].application,
                ocr=ocr,
                extract=lambda _: labels["t1-clean-classic-1"].detected,
            )
        assert raised.value.code
        assert raised.value.what_to_do

    def test_a_truncated_image_is_reported_not_crashed(self, labels, ocr) -> None:
        whole = png(Image.new("RGB", (1000, 1400), "white"))
        with pytest.raises(UnreadableImageError) as raised:
            verify(
                whole[: len(whole) // 2],
                labels["t1-clean-classic-1"].application,
                ocr=ocr,
                extract=lambda _: labels["t1-clean-classic-1"].detected,
            )
        assert raised.value.code
        assert raised.value.what_to_do

    def test_a_pdf_is_named_as_the_problem(self, labels, ocr) -> None:
        with pytest.raises(UnreadableImageError) as raised:
            verify(
                b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n",
                labels["t1-clean-classic-1"].application,
                ocr=ocr,
                extract=lambda _: labels["t1-clean-classic-1"].detected,
            )
        assert "PDF" in raised.value.message or "PDF" in raised.value.what_to_do


class TestPhotographOrientation:
    def test_a_portrait_photo_with_exif_rotation_is_uprighted(self, labels, ocr) -> None:
        # Every phone writes Orientation=6 for a portrait shot. Decoding without
        # honouring it hands the agent sideways evidence crops and makes a
        # one-panel label look like a two-panel container.
        from app.pipeline.run import _decode

        upright = Image.open(BytesIO(labels["t1-clean-classic-1"].image_bytes)).convert("RGB")
        # What a camera stores for a portrait shot: sensor pixels rotated 90
        # counter-clockwise, plus a tag saying "rotate clockwise to display".
        exif = Image.Exif()
        exif[0x0112] = 6
        buffer = BytesIO()
        upright.rotate(90, expand=True).save(buffer, format="JPEG", exif=exif, quality=95)

        assert Image.open(BytesIO(buffer.getvalue())).size == (1400, 1000)
        assert _decode(buffer.getvalue()).size == upright.size

        result = verify(
            buffer.getvalue(),
            labels["t1-clean-classic-1"].application,
            ocr=lambda_engine(ocr, labels["t1-clean-classic-1"]),
            extract=lambda _: labels["t1-clean-classic-1"].detected,
        )
        assert result.report.overall in (Verdict.PASS, Verdict.NEEDS_REVIEW)


def lambda_engine(ocr: corpus.CorpusOcrEngine, label: corpus.CorpusLabel):
    """An engine that returns one label's ground truth whatever it is handed."""
    known = ocr.extract(label.image_bytes)

    class _Engine:
        name = "corpus"

        def extract(self, image_bytes: bytes) -> OcrResult:
            return known

    return _Engine()


class TestIntactLabelsAreNotRejected:
    def test_a_label_with_a_dark_header_band_is_not_called_cropped(self, labels) -> None:
        # A full-bleed band along one edge is an ordinary label design. Calling
        # it "the label runs off the edge of the frame" sends an agent to
        # re-photograph an intact bottle.
        image = Image.open(BytesIO(labels["t1-clean-classic-1"].image_bytes)).convert("RGB")
        ImageDraw.Draw(image).rectangle([0, 0, image.width, 40], fill="#1c2b3a")
        require_readable(image)

    def test_a_label_with_a_dark_left_edge_is_not_called_cropped(self, labels) -> None:
        image = Image.open(BytesIO(labels["t1-clean-classic-1"].image_bytes)).convert("RGB")
        ImageDraw.Draw(image).rectangle([0, 0, 40, image.height], fill="#1c2b3a")
        require_readable(image)

    def test_a_genuinely_cropped_label_is_still_caught(self, labels) -> None:
        with pytest.raises(UnreadableImageError) as raised:
            require_readable(Image.open(BytesIO(labels["t4-skew-crop"].image_bytes)).convert("RGB"))
        assert raised.value.code == "label_cropped"


class TestWarningProportionScalesCorrectly:
    def test_a_warning_that_wraps_more_does_not_get_easier_to_pass(self) -> None:
        # The violation this check exists for makes the warning smaller, which
        # makes it wrap onto more lines. Counting those continuation lines as
        # body text meant the check weakened exactly as the violation worsened,
        # and a warning at a third of body height passed.
        verdicts = []
        for line_count in (3, 6, 9):
            ocr = _warning_over_lines(line_count, warning_height=5, body_height=30)
            layout = measure(Image.new("RGB", (1000, 1400), "white"), ocr, {})
            report = check_warning(detected=STATUTORY_WARNING, layout=layout)
            verdicts.append(
                next(c.verdict for c in report.checks if c.check is WarningCheckName.PROPORTION)
            )
        # One ratio, one verdict, however many lines the warning wraps onto.
        assert set(verdicts) == {Verdict.FAIL}, verdicts


def _warning_over_lines(lines: int, *, warning_height: int, body_height: int) -> OcrResult:
    """OCR output where the warning is split across `lines` blocks."""
    blocks = [
        TextBlock(
            text=text,
            box=BoundingBox(
                x=70, y=100 + index * (body_height + 10), width=800, height=body_height
            ),
            confidence=0.99,
        )
        for index, text in enumerate(
            ["OLD TOM DISTILLERY", "Kentucky Straight Bourbon Whiskey", "45% Alc./Vol.", "750 mL"]
        )
    ]
    words = STATUTORY_WARNING.split()
    per_line = max(1, len(words) // lines)
    y = 900
    for index in range(lines):
        chunk = " ".join(words[index * per_line : (index + 1) * per_line])
        if not chunk:
            continue
        blocks.append(
            TextBlock(
                text=chunk,
                box=BoundingBox(x=70, y=y, width=800, height=warning_height),
                confidence=0.99,
            )
        )
        y += warning_height + 3
    return OcrResult(
        full_text="\n".join(b.text for b in blocks),
        blocks=tuple(blocks),
        image_width=1000,
        image_height=1400,
        engine="synthetic",
        latency_ms=0.0,
    )


class TestServiceFailuresAreTyped:
    def test_an_extraction_failure_reaches_the_client_with_a_code(
        self, monkeypatch, labels
    ) -> None:
        ocr = corpus.CorpusOcrEngine()
        label = labels["t1-clean-classic-1"]

        def explode(_text: str, **_: object):
            raise ConnectionError("connection reset")

        monkeypatch.setattr("app.api.routes.get_engine", lambda: ocr)
        monkeypatch.setattr("app.api.routes.extract_from_text", explode)

        with TestClient(app, base_url="https://testserver") as client:
            sign_in(client)
            response = client.post(
                "/api/verify",
                files={"image": ("label.png", label.image_bytes, "image/png")},
                data={"beverage_type": "spirits", "brand_name": "OLD TOM DISTILLERY"},
            )
        assert response.status_code != 500 or "code" in response.json().get("detail", {})
        body = response.json()
        detail = body.get("detail", body)
        assert detail.get("code")
        assert detail.get("what_to_do")

    def test_an_unparseable_model_response_is_typed(self) -> None:
        from app.extraction.client import parse_response

        class _Usage:
            input_tokens: int = 0
            output_tokens: int = 0

        class _Block:
            type = "text"
            text = '{"brand_name": "Old T'

        class _Response:
            def __init__(self) -> None:
                self.content = [_Block()]
                self.usage = _Usage()

        with pytest.raises(ExtractionError) as raised:
            parse_response(_Response(), "claude-haiku-4-5", 1.0)
        assert raised.value.code
        assert raised.value.what_to_do


class TestUnreadableResponsesReportTheirCost:
    def test_processing_time_is_reported_even_when_the_image_is_unreadable(
        self, monkeypatch, labels
    ) -> None:
        # Screen 5 aggregates timing across all four buckets. Reporting zero for
        # the unreadable one makes the batch estimate wrong.
        ocr = corpus.CorpusOcrEngine()
        monkeypatch.setattr("app.api.routes.get_engine", lambda: ocr)
        monkeypatch.setattr(
            "app.api.routes.extract_from_text",
            lambda text, **_: labels["t4-tiny"].detected,
        )
        with TestClient(app, base_url="https://testserver") as client:
            sign_in(client)
            response = client.post(
                "/api/verify",
                files={"image": ("tiny.png", labels["t4-tiny"].image_bytes, "image/png")},
                data={"beverage_type": "spirits"},
            )
        body = response.json()
        assert body["overall"] == "unreadable"
        assert body["processing_ms"] > 0


class TestOcrConfidence:
    def test_uniformly_unconfident_ocr_is_reported_as_unreadable(self, labels) -> None:
        # Cloud Vision returns 0.0 for a paragraph it could not read. Mapping
        # that to None disabled the confidence gate entirely.
        from app.pipeline.quality import require_text

        blocks = tuple(
            TextBlock(
                text="lorem ipsum dolor sit amet consectetur",
                box=BoundingBox(x=0, y=index * 40, width=500, height=30),
                confidence=0.0,
            )
            for index in range(4)
        )
        result = OcrResult(
            full_text="\n".join(b.text for b in blocks),
            blocks=blocks,
            image_width=1000,
            image_height=1400,
            engine="fake",
            latency_ms=0.0,
        )
        with pytest.raises(UnreadableImageError) as raised:
            require_text(result)
        assert raised.value.code == "text_unreadable"


class TestApplicationShape:
    def test_an_application_with_no_fields_still_returns_verdicts(self, labels, ocr) -> None:
        label = labels["t1-clean-classic-1"]
        result = verify(
            label.image_bytes,
            Application(beverage_type="spirits", fields={}),
            ocr=ocr,
            extract=lambda _: label.detected,
        )
        assert result.report.fields
