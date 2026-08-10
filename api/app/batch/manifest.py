"""Reading and checking the manifest that pairs images with applications.

Everything here happens **before** any label is processed. An importer sends 250
applications at peak season; a four-minute run that fails at minute three on a
problem visible at second one is exactly the experience that made the last
vendor pilot fail.

Every problem is reported specifically — by row number or by filename — because
"3 rows have errors" tells an agent nothing they can act on.

See docs/specs/batch.md 2.1
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field

from app.errors import LabelVerificationError

# The field names the single-label route already uses, so an agent who has used
# one screen recognises the other.
FIELD_COLUMNS = (
    "brand_name",
    "class_type",
    "alcohol_content",
    "net_contents",
    "bottler_address",
    "country_of_origin",
)
COLUMNS = ("application_id", "image", "beverage_type", *FIELD_COLUMNS)

# Without these a row cannot be checked at all.
REQUIRED_COLUMNS = ("image",)
REQUIRED_FIELDS = ("brand_name", "class_type", "net_contents", "bottler_address")


class ManifestError(LabelVerificationError):
    """The manifest could not be read at all."""


@dataclass(frozen=True)
class ManifestRow:
    row_number: int
    image: str
    application_id: str
    beverage_type: str
    fields: dict[str, str | None]


@dataclass(frozen=True)
class Problem:
    """One thing wrong, named specifically enough to fix."""

    kind: str
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    rows: tuple[ManifestRow, ...]
    matched: tuple[ManifestRow, ...]
    problems: tuple[Problem, ...]
    image_count: int

    @property
    def ready(self) -> bool:
        return bool(self.matched)

    def as_dict(self) -> dict[str, object]:
        return {
            "image_count": self.image_count,
            "row_count": len(self.rows),
            "matched_count": len(self.matched),
            "problem_count": len(self.problems),
            "problems": [{"kind": p.kind, "detail": p.detail} for p in self.problems],
            "ready": self.ready,
        }


def template_csv() -> str:
    """The spreadsheet an agent should start from.

    Handed out rather than described: nobody should have to guess column names,
    and a wrong guess costs a whole upload.
    """
    example = {
        "application_id": "APP-10001",
        "image": "old-tom-front.png",
        "beverage_type": "spirits",
        "brand_name": "OLD TOM DISTILLERY",
        "class_type": "Kentucky Straight Bourbon Whiskey",
        "alcohol_content": "45% Alc./Vol. (90 Proof)",
        "net_contents": "750 mL",
        "bottler_address": "Bottled by Old Tom Distillery, Bardstown, Kentucky",
        "country_of_origin": "",
    }
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(COLUMNS), lineterminator="\n")
    writer.writeheader()
    writer.writerow(example)
    return buffer.getvalue()


def _row_from(raw: dict[str, str], row_number: int) -> ManifestRow:
    cleaned = {key.strip().lower(): (value or "").strip() for key, value in raw.items() if key}
    return ManifestRow(
        row_number=row_number,
        image=cleaned.get("image", ""),
        application_id=cleaned.get("application_id", ""),
        beverage_type=cleaned.get("beverage_type", "") or "spirits",
        fields={name: cleaned.get(name) or None for name in FIELD_COLUMNS},
    )


def parse(content: bytes, filename: str = "") -> list[ManifestRow]:
    """Read a CSV or JSON manifest into rows, or say why it could not be read."""
    text = content.decode("utf-8-sig", errors="replace").strip()
    if not text:
        raise ManifestError(
            code="manifest_empty",
            message="The spreadsheet is empty.",
            what_to_do="Upload a file with one row per application.",
        )

    looks_like_json = text.startswith("[") or text.startswith("{") or filename.endswith(".json")
    rows: list[ManifestRow] = []

    if looks_like_json:
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ManifestError(
                code="manifest_unreadable",
                message=f"The JSON file could not be read (line {exc.lineno}, column {exc.colno}).",
                what_to_do="Fix the file, or upload a CSV instead.",
            ) from exc
        entries = payload if isinstance(payload, list) else payload.get("labels", [])
        for index, entry in enumerate(entries, start=1):
            if isinstance(entry, dict):
                rows.append(_row_from({str(k): str(v) for k, v in entry.items()}, index))
        header = set(entries[0]) if entries and isinstance(entries[0], dict) else set()
    else:
        reader = csv.DictReader(io.StringIO(text))
        header = {(name or "").strip().lower() for name in (reader.fieldnames or [])}
        for index, raw in enumerate(reader, start=1):
            rows.append(_row_from(raw, index))

    recognised = {name.lower() for name in header} & set(COLUMNS)
    if not recognised:
        raise ManifestError(
            code="manifest_columns_unrecognised",
            message=(
                "This file's columns are not the ones the tool expects, so none of it "
                "could be read."
            ),
            what_to_do=(
                "Download the template spreadsheet. Its columns are: " + ", ".join(COLUMNS) + "."
            ),
        )

    if not rows:
        raise ManifestError(
            code="manifest_no_rows",
            message="The spreadsheet has column names but no rows underneath them.",
            what_to_do="Add one row per application and upload it again.",
        )
    return rows


def preflight(rows: list[ManifestRow], image_names: list[str]) -> PreflightReport:
    """Match rows to images and name every mismatch before anything runs."""
    available = {name for name in image_names}
    problems: list[Problem] = []
    matched: list[ManifestRow] = []
    claimed: set[str] = set()

    for row in rows:
        if not row.image:
            problems.append(
                Problem(
                    kind="row_without_image_name",
                    detail=(
                        f"Row {row.row_number} does not name an image file, so it cannot "
                        "be checked."
                    ),
                )
            )
            continue

        if row.image not in available:
            problems.append(
                Problem(
                    kind="image_not_uploaded",
                    detail=(
                        f"Row {row.row_number}"
                        + (f" ({row.application_id})" if row.application_id else "")
                        + f" names {row.image}, which is not among the uploaded images. "
                        "It will be skipped."
                    ),
                )
            )
            continue

        missing = [name for name in REQUIRED_FIELDS if not row.fields.get(name)]
        if missing:
            problems.append(
                Problem(
                    kind="row_missing_field",
                    detail=(
                        f"Row {row.row_number} has no "
                        + ", ".join(name.replace("_", " ") for name in missing)
                        + ". That is required, so this row cannot be checked."
                    ),
                )
            )
            continue

        claimed.add(row.image)
        matched.append(row)

    for name in image_names:
        if name not in claimed:
            problems.append(
                Problem(
                    kind="image_not_in_manifest",
                    detail=(
                        f"Image {name} is not named in any spreadsheet row. It will be skipped."
                    ),
                )
            )

    return PreflightReport(
        rows=tuple(rows),
        matched=tuple(matched),
        problems=tuple(problems),
        image_count=len(image_names),
    )


@dataclass
class ManifestUpload:
    """What arrived with the request, before any of it is trusted."""

    manifest: bytes
    filename: str
    images: dict[str, bytes] = field(default_factory=dict)

    def preflight(self) -> PreflightReport:
        return preflight(parse(self.manifest, self.filename), list(self.images))
