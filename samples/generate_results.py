"""Run the real pipeline over api/app/samples and store what it found.

The seeded review queue must show verdicts the moment it loads, on every
restart, without spending an OCR or model call. So the answers are computed
once, here, and committed. Re-run this only when the pipeline's output changes.

    OCR_ENGINE=cloud api/.venv/Scripts/python.exe samples/generate_results.py

Needs both credentials. Everything it writes came from the same code path a
live upload takes — these are recorded results, not hand-written fixtures.
"""

from __future__ import annotations

import base64
import io
import json
import pathlib
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "api"))

from app.api.routes import _to_response  # noqa: E402
from app.errors import UnreadableImageError  # noqa: E402
from app.extraction.client import extract_from_text  # noqa: E402
from app.ocr.factory import get_engine  # noqa: E402
from app.pipeline.run import verify  # noqa: E402
from app.rules.engine import Application  # noqa: E402

# Their manifest names the application fields differently.
FIELD_MAP = {
    "brand": "brand_name",
    "class_type": "class_type",
    "abv": "alcohol_content",
    "net_contents": "net_contents",
    "origin": "country_of_origin",
}


def _as_jpeg(data_uri: str | None, quality: int = 78) -> str | None:
    """Re-encode a base64 PNG crop as JPEG. Same evidence, a tenth the bytes."""
    if not data_uri or not data_uri.startswith("data:image/png;base64,"):
        return data_uri
    raw = base64.b64decode(data_uri.split(",", 1)[1])
    buffer = io.BytesIO()
    Image.open(io.BytesIO(raw)).convert("RGB").save(
        buffer, "JPEG", quality=quality, optimize=True
    )
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def main(limit: int | None = None) -> None:
    labels = HERE.parent / "api" / "app" / "samples"
    manifest = json.loads((labels / "manifest.json").read_text(encoding="utf-8"))
    if limit:
        manifest = manifest[:limit]

    ocr = get_engine()
    records = []
    for entry in manifest:
        image_bytes = (labels / entry["image"]).read_bytes()
        application = Application(
            beverage_type=entry["beverage"],
            application_id=entry["id"],
            fields={
                ours: entry["cola_application"].get(theirs)
                for theirs, ours in FIELD_MAP.items()
            }
            # Their manifest models no bottler on the application side, only on
            # the label. A real COLA application declares one, and without it
            # every label here comes back NEEDS_REVIEW ("the label shows a value,
            # the application did not") — correct behaviour, useless as a seed.
            # So the declared value is what the label prints. Where the defect is
            # a missing bottler there is nothing to copy, and the application
            # still declares one: that is precisely the violation.
            | {
                "bottler_address": entry["label_printed"].get("bottler")
                or f"BOTTLED BY {entry['label_printed']['brand']}"
            },
        )
        record: dict[str, object] = {
            "id": entry["id"],
            "image": entry["image"],
            "beverage_type": entry["beverage"],
            "declared": dict(application.fields),
            "expected_verdict": entry["expected_verdict"],
            "defect": entry["defect"],
        }
        try:
            result = verify(
                image_bytes,
                application,
                ocr=ocr,
                extract=lambda text: extract_from_text(text).fields,
            )
        except UnreadableImageError as exc:
            record["unreadable"] = {
                "code": exc.code,
                "message": exc.message,
                "what_to_do": exc.what_to_do,
            }
            print(f"  {entry['id']:32s} unreadable: {exc.code}")
        else:
            response = _to_response(
                result, application_id=entry["id"]
            )
            payload = response.model_dump(mode="json")
            # Crops are 99% of the stored bytes as base64 PNG. JPEG carries the
            # same evidence at a tenth the size, and these are photographs.
            for field in payload["fields"]:
                field["crop_url"] = _as_jpeg(field["crop_url"])
            record["result"] = payload
            print(
                f"  {entry['id']:32s} {response.overall:12s} "
                f"{response.processing_ms:5d} ms"
            )
        records.append(record)

    out = labels / "results.json"
    out.write_text(json.dumps(records, indent=1), encoding="utf-8")
    print(f"\nwrote {out} ({out.stat().st_size / 1e6:.1f} MB) for {len(records)} labels")


if __name__ == "__main__":
    main(limit=int(sys.argv[1]) if len(sys.argv) > 1 else None)
