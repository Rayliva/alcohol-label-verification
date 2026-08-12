"""The pipeline end to end — docs/specs/pipeline.md §4.

Runs against real corpus images with OCR and extraction held perfect, so what is
under test here is the pipeline itself: the quality gate, the measurements, the
crops, and the wiring.
"""

from __future__ import annotations

import pytest

from app.errors import UnreadableImageError
from app.pipeline import verify
from app.rules.types import Verdict, WarningCheckName
from tests.support import corpus

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def labels() -> dict[str, corpus.CorpusLabel]:
    return {label.label_id: label for label in corpus.load()}


@pytest.fixture(scope="module")
def ocr() -> corpus.CorpusOcrEngine:
    return corpus.CorpusOcrEngine()


def run(label: corpus.CorpusLabel, ocr: corpus.CorpusOcrEngine, calls: list | None = None):
    def extract(text: str):
        if calls is not None:
            calls.append(text)
        return label.detected

    return verify(label.image_bytes, label.application, ocr=ocr, extract=extract)


class TestCompliantLabel:
    def test_a_clean_label_passes(self, labels, ocr) -> None:
        result = run(labels["t1-clean-classic-1"], ocr)
        assert result.report.overall is Verdict.PASS

    def test_every_configured_field_is_reported(self, labels, ocr) -> None:
        result = run(labels["t1-clean-classic-1"], ocr)
        assert {r.field for r in result.report.fields} == {
            "brand_name",
            "class_type",
            "alcohol_content",
            "net_contents",
            "bottler_address",
            "government_warning",
        }

    def test_the_extraction_model_is_called_once(self, labels, ocr) -> None:
        # Latency is the top risk in the PRD. One call per label, always.
        calls: list[str] = []
        run(labels["t1-clean-classic-1"], ocr, calls)
        assert len(calls) == 1

    def test_the_extraction_call_sees_text_and_never_pixels(self, labels, ocr) -> None:
        calls: list[str] = []
        run(labels["t1-clean-classic-1"], ocr, calls)
        assert "OLD TOM DISTILLERY" in calls[0]


class TestEvidenceCrops:
    def test_every_field_found_on_the_label_has_a_crop(self, labels, ocr) -> None:
        result = run(labels["t1-clean-classic-1"], ocr)
        for name in ("brand_name", "class_type", "net_contents", "government_warning"):
            assert result.crops.get(name), f"no crop for {name}"

    def test_a_crop_is_a_png(self, labels, ocr) -> None:
        result = run(labels["t1-clean-classic-1"], ocr)
        assert result.crops["brand_name"].startswith(b"\x89PNG")

    def test_a_field_absent_from_the_label_has_no_crop(self, labels, ocr) -> None:
        # There is no region to show. The UI keeps the panel and says so
        # rather than collapsing the row (ui-spec resolution 3).
        result = run(labels["t2-brand-missing"], ocr)
        assert "brand_name" not in result.crops
        assert "brand_name" in result.crops_missing


class TestMeasurements:
    def test_text_heights_are_measured(self, labels, ocr) -> None:
        result = run(labels["t1-clean-classic-1"], ocr)
        report = result.report
        proportion = next(
            c for c in report.warning_checks if c.check is WarningCheckName.PROPORTION
        )
        assert proportion.verdict is not Verdict.NEEDS_REVIEW or "%" in proportion.reason

    def test_a_shrunken_warning_is_caught(self, labels, ocr) -> None:
        result = run(labels["t2-warning-too-small"], ocr)
        proportion = next(
            c for c in result.report.warning_checks if c.check is WarningCheckName.PROPORTION
        )
        assert proportion.verdict is Verdict.FAIL

    def test_a_low_contrast_warning_is_caught(self, labels, ocr) -> None:
        result = run(labels["t2-warning-low-contrast"], ocr)
        contrast = next(
            c for c in result.report.warning_checks if c.check is WarningCheckName.CONTRAST
        )
        assert contrast.verdict is not Verdict.PASS

    def test_a_field_on_the_back_panel_reaches_a_person(self, labels, ocr) -> None:
        result = run(labels["t5-field-of-vision-1"], ocr)
        check = next(
            c for c in result.report.warning_checks if c.check is WarningCheckName.FIELD_OF_VISION
        )
        # Not FAIL: panels are inferred from aspect ratio, which cannot tell
        # two-panel artwork from a landscape single-panel export. The split
        # still reaches an agent with where each field was seen.
        assert check.verdict is Verdict.NEEDS_REVIEW


class TestUnreadableImages:
    @pytest.mark.parametrize(
        ("label_id", "code"),
        [
            ("t4-tiny", "image_too_small"),
            ("t4-blur-heavy", "image_too_blurry"),
            ("t4-near-black", "image_too_dark"),
            ("t4-noise", "image_too_noisy"),
            ("t4-skew-crop", "label_cropped"),
        ],
    )
    def test_each_failure_names_its_own_cause(self, labels, ocr, label_id, code) -> None:
        # "Processing failed" teaches an agent nothing, so they reject the
        # application and stop using the tool.
        with pytest.raises(UnreadableImageError) as raised:
            run(labels[label_id], ocr)
        assert raised.value.code == code

    def test_the_message_says_what_to_do_next(self, labels, ocr) -> None:
        with pytest.raises(UnreadableImageError) as raised:
            run(labels["t4-tiny"], ocr)
        assert raised.value.what_to_do
        assert "400" in raised.value.message

    def test_an_unreadable_image_produces_no_verdicts(self, labels, ocr) -> None:
        # "We could not read this" is not "this label is non-compliant".
        with pytest.raises(UnreadableImageError):
            run(labels["t4-blur-heavy"], ocr)

    def test_a_readable_but_degraded_image_is_not_rejected(self, labels, ocr) -> None:
        for label_id in ("t4-blur-light", "t4-low-light", "t4-skew", "t4-jpeg-artefacts"):
            label = labels[label_id]
            try:
                run(label, ocr)
            except corpus.CorpusMissingError:
                # Degraded images carry no ground-truth OCR by design; reaching
                # this point means the quality gate let them through, which is
                # what this test is about.
                continue
            except UnreadableImageError as exc:
                pytest.fail(f"{label_id} was rejected as {exc.code}, but it is readable")

    def test_a_file_that_is_not_an_image_says_so(self, labels, ocr) -> None:
        label = labels["t1-clean-classic-1"]
        with pytest.raises(UnreadableImageError) as raised:
            verify(b"not an image", label.application, ocr=ocr, extract=lambda _: label.detected)
        assert raised.value.code == "unsupported_file"


class TestTimings:
    def test_every_stage_is_timed(self, labels, ocr) -> None:
        # NFR-1 requires published numbers, and we cannot publish what we do
        # not measure.
        timings = run(labels["t1-clean-classic-1"], ocr).timings.as_dict()
        for stage in ("decode_ms", "quality_ms", "ocr_ms", "extraction_ms", "rules_ms"):
            assert stage in timings

    def test_the_stages_add_up_to_no_more_than_the_total(self, labels, ocr) -> None:
        timings = run(labels["t1-clean-classic-1"], ocr).timings
        stages = (
            timings.decode_ms
            + timings.quality_ms
            + timings.ocr_ms
            + timings.extraction_ms
            + timings.rules_ms
            + timings.crops_ms
        )
        assert stages <= timings.total_ms + 1.0
