"""Google Cloud Vision OCR adapter.

Default engine in production. Credentials arrive as a JSON string in the
environment rather than a file path, so nothing is written to disk and nothing
can be baked into an image. See .claude/rules/secrets.md
"""

from __future__ import annotations

import json
import time

from app.config import settings
from app.ocr.base import BoundingBox, OcrResult, TextBlock


class CloudVisionEngine:
    name = "cloud"

    def __init__(self) -> None:
        from google.cloud import vision
        from google.oauth2 import service_account

        raw = settings.google_application_credentials_json
        if not raw:
            raise RuntimeError(
                "GOOGLE_APPLICATION_CREDENTIALS_JSON is not set. "
                "Set OCR_ENGINE=fake to run without credentials."
            )
        try:
            info = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"GOOGLE_APPLICATION_CREDENTIALS_JSON is not valid JSON "
                f"({exc.msg} at line {exc.lineno} col {exc.colno}; value is "
                f"{len(raw)} chars and "
                f"{'does' if raw.lstrip().startswith('{') else 'does not'} begin with "
                f"an opening brace). It must be the full service-account key, "
                f"including the outer braces."
            ) from exc

        required = ("type", "project_id", "private_key", "client_email")
        missing = [k for k in required if k not in info]
        if missing:
            raise RuntimeError(
                f"GOOGLE_APPLICATION_CREDENTIALS_JSON parsed but is missing {missing}. "
                f"Keys present: {sorted(info)[:8]}. Paste the whole service-account file."
            )

        credentials = service_account.Credentials.from_service_account_info(info)
        self._client = vision.ImageAnnotatorClient(credentials=credentials)
        self._vision = vision

    def extract(self, image_bytes: bytes) -> OcrResult:
        vision = self._vision
        image = vision.Image(content=image_bytes)

        started = time.perf_counter()
        response = self._client.document_text_detection(image=image)
        elapsed_ms = (time.perf_counter() - started) * 1000

        if response.error.message:
            # Surface the provider's own reason rather than a generic failure.
            raise RuntimeError(f"Cloud Vision error: {response.error.message}")

        blocks: list[TextBlock] = []
        width = height = 0

        for page in response.full_text_annotation.pages:
            width = max(width, page.width)
            height = max(height, page.height)
            for block in page.blocks:
                for paragraph in block.paragraphs:
                    text = "".join(
                        "".join(s.text for s in word.symbols)
                        + (
                            " "
                            if word.symbols
                            and word.symbols[-1].property.detected_break.type_
                            in (1, 2)  # SPACE, SURE_SPACE
                            else ""
                        )
                        for word in paragraph.words
                    ).strip()
                    if not text:
                        continue
                    blocks.append(
                        TextBlock(
                            text=text,
                            box=_to_box(paragraph.bounding_box),
                            confidence=(
                                paragraph.confidence if paragraph.confidence is not None else None
                            ),
                        )
                    )

        return OcrResult(
            full_text=response.full_text_annotation.text,
            blocks=tuple(blocks),
            image_width=width,
            image_height=height,
            engine=self.name,
            latency_ms=elapsed_ms,
        )


def _to_box(bounding_poly: object) -> BoundingBox:
    """Cloud Vision returns four corner vertices; normalise to x/y/w/h."""
    vertices = bounding_poly.vertices  # type: ignore[attr-defined]
    xs = [v.x for v in vertices]
    ys = [v.y for v in vertices]
    x, y = min(xs), min(ys)
    return BoundingBox(x=x, y=y, width=max(xs) - x, height=max(ys) - y)
