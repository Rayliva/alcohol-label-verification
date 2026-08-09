"""Loading the corpus for tests, with no credentials and no network.

Two fakes stand in for the two boundaries this system has:

* `CorpusOcrEngine` replays the boxes the renderer actually drew, recorded in
  `corpus/fixtures/ocr/`. It is what a perfect OCR engine would return.
* `spec_extractor` returns exactly what the artwork says, taken from the render
  spec rather than from a model.

Holding both perfect is deliberate. It measures the rule engine and the geometry
measurements *on their own*, so a wrong verdict is attributable to a rule rather
than to a misread character. The end-to-end number with real OCR and a real
extraction call is a separate, credential-bearing measurement — and the README
publishes both rather than letting the flattering one stand for the product.
"""

from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from corpus.generate import CATALOGUE, Variant  # noqa: E402

from app.extraction.schema import ExtractedFields  # noqa: E402
from app.ocr.base import BoundingBox, OcrResult, TextBlock  # noqa: E402
from app.rules.engine import Application  # noqa: E402

IMAGES = REPO_ROOT / "corpus" / "out"
OCR_FIXTURES = REPO_ROOT / "corpus" / "fixtures" / "ocr"


class CorpusMissingError(RuntimeError):
    """The corpus has not been generated. It is gitignored on purpose."""


@dataclass(frozen=True)
class CorpusLabel:
    variant: Variant
    image_bytes: bytes

    @property
    def label_id(self) -> str:
        return self.variant.label_id

    @property
    def application(self) -> Application:
        return Application(
            beverage_type=self.variant.beverage_type,
            fields=dict(self.variant.application),
            application_id=self.variant.label_id,
        )

    @property
    def detected(self) -> ExtractedFields:
        """What the artwork actually says, from the render spec."""
        spec = self.variant.spec
        return ExtractedFields(
            brand_name=spec.brand,
            class_type=spec.class_type,
            alcohol_content=spec.alcohol_content,
            net_contents=spec.net_contents,
            bottler_address=spec.bottler,
            country_of_origin=None,
            government_warning=spec.warning,
        )


def require_corpus() -> None:
    if not IMAGES.exists() or not any(IMAGES.glob("t1-*.png")):
        raise CorpusMissingError(
            f"No corpus images in {IMAGES}. corpus/out/ is gitignored — regenerate "
            "with: api/.venv/Scripts/python.exe corpus/generate.py --all"
        )


def load(tiers: tuple[int, ...] = (1, 2, 3, 4, 5)) -> list[CorpusLabel]:
    require_corpus()
    labels = []
    for variant in CATALOGUE:
        if variant.tier not in tiers:
            continue
        path = IMAGES / variant.image_name
        if not path.exists():
            raise CorpusMissingError(f"{path} is missing. Regenerate the corpus.")
        labels.append(CorpusLabel(variant=variant, image_bytes=path.read_bytes()))
    return labels


class CorpusOcrEngine:
    """Replays the boxes the renderer drew, keyed by image content."""

    name = "corpus"

    def __init__(self) -> None:
        self._by_digest: dict[str, OcrResult] = {}
        for fixture in sorted(OCR_FIXTURES.glob("*.json")):
            payload = json.loads(fixture.read_text(encoding="utf-8"))
            image = IMAGES / payload["image"]
            if not image.exists():
                continue
            self._by_digest[_digest(image.read_bytes())] = _to_result(payload)

    def extract(self, image_bytes: bytes) -> OcrResult:
        try:
            return self._by_digest[_digest(image_bytes)]
        except KeyError:
            raise CorpusMissingError(
                "No ground-truth OCR for this image. Regenerate the corpus so the "
                "fixture and the image agree."
            ) from None


def spec_extractor(label: CorpusLabel) -> ExtractedFields:
    return label.detected


def _digest(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


def _to_result(payload: dict) -> OcrResult:
    blocks = tuple(
        TextBlock(
            text=entry["text"],
            box=BoundingBox(
                x=entry["x"], y=entry["y"], width=entry["width"], height=entry["height"]
            ),
            confidence=0.99,
        )
        for entry in payload["blocks"]
    )
    return OcrResult(
        full_text="\n".join(b.text for b in blocks),
        blocks=blocks,
        image_width=payload["width"],
        image_height=payload["height"],
        engine="corpus",
        latency_ms=0.0,
    )
