"""HTTP routes for batch review.

    GET  /api/batch/template   the spreadsheet to start from
    POST /api/batch/preflight  what would happen, before anything runs
    POST /api/batch            start a run, get a job id back
    GET  /api/batch/{id}       progress and results so far
    POST /api/batch/{id}/stop  stop between labels, keeping what is done

Pre-flight is a separate call on purpose. An agent uploading 250 applications
sees every mismatch — named by filename or row number — before committing to a
four-minute run, which is the failure the last vendor pilot never fixed.

See docs/specs/batch.md
"""

from __future__ import annotations

import csv
import io
from typing import Any

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse

from app.api.routes import _to_response
from app.batch.manifest import (
    COLUMNS,
    ManifestError,
    ManifestRow,
    ManifestUpload,
    template_csv,
)
from app.batch.store import Job, run_job, store
from app.errors import UnreadableImageError
from app.extraction.client import extract_from_text
from app.ocr.factory import get_engine
from app.pipeline import verify
from app.rules.engine import Application

router = APIRouter(prefix="/api/batch", tags=["batch"])


@router.get("/template", response_class=PlainTextResponse)
def template() -> PlainTextResponse:
    """The spreadsheet an agent should start from, with one example row."""
    return PlainTextResponse(
        template_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="label-check-template.csv"'},
    )


async def _collect(images: list[UploadFile], manifest: UploadFile) -> ManifestUpload:
    upload = ManifestUpload(
        manifest=await manifest.read(),
        filename=manifest.filename or "",
    )
    for image in images:
        name = image.filename or ""
        if name in upload.images:
            upload.duplicates.append(name)
            continue
        upload.images[name] = await image.read()
    return upload


def _preflight_or_400(upload: ManifestUpload) -> Any:
    try:
        return upload.preflight()
    except ManifestError as exc:
        raise HTTPException(status_code=400, detail=exc.as_dict()) from exc


@router.post("/preflight")
async def preflight(
    images: list[UploadFile] = File(default_factory=list),
    manifest: UploadFile = File(...),
) -> dict[str, object]:
    """What would happen if this run started, reported before it does."""
    report = _preflight_or_400(await _collect(images, manifest))
    return report.as_dict()


def _check_one(image_bytes: bytes, declared: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """One label, through exactly the same pipeline the single-label route uses.

    One code path, so a batch verdict and a single-label verdict on the same
    image can never disagree.
    """
    application = Application(
        beverage_type=declared.get("beverage_type", "spirits"),
        application_id=declared.get("application_id") or None,
        fields=declared.get("fields", {}),
    )
    try:
        result = verify(
            image_bytes,
            application,
            ocr=get_engine(),
            extract=lambda text: extract_from_text(text).fields,
        )
    except UnreadableImageError as exc:
        return "unreadable", {"error": exc.as_dict(), "brand_name": None, "issues": 0}

    response = _to_response(
        result,
        application_id=application.application_id,
        reviewer=None,
    )
    brand = next((f for f in response.fields if f.field == "brand_name"), None)
    return response.overall, {
        "brand_name": brand.detected if brand else None,
        "issues": sum(1 for f in response.fields if f.verdict != "pass"),
        "label": response.model_dump(),
    }


def _work_item(row: ManifestRow, images: dict[str, bytes]) -> tuple[str, str, bytes, dict]:
    return (
        row.application_id or row.image,
        row.image,
        images[row.image],
        {
            "beverage_type": row.beverage_type,
            "application_id": row.application_id,
            "fields": dict(row.fields),
        },
    )


@router.post("")
async def start(
    background: BackgroundTasks,
    images: list[UploadFile] = File(default_factory=list),
    manifest: UploadFile = File(...),
    concurrency: int = Form(8),
) -> dict[str, object]:
    """Start a run. Returns immediately with a job id to poll."""
    upload = await _collect(images, manifest)
    report = _preflight_or_400(upload)

    if not report.matched:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "nothing_to_check",
                "message": "No spreadsheet row matched an uploaded image.",
                "what_to_do": (
                    "Check that the image column holds the exact filenames you uploaded."
                ),
            },
        )

    job = store.create(
        total=len(report.matched),
        problems=[{"kind": p.kind, "detail": p.detail} for p in report.problems],
    )
    work = [_work_item(row, upload.images) for row in report.matched]
    background.add_task(run_job, job, work, _check_one, concurrency)
    return {"job_id": job.id, **report.as_dict()}


def _job_or_404(job_id: str) -> Job:
    job = store.get(job_id)
    if job is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "job_not_found",
                "message": "That batch is not in progress on this server.",
                "what_to_do": ("Nothing is stored between restarts, so start the batch again."),
            },
        )
    return job


@router.get("/{job_id}/label/{index}")
def label_detail(job_id: str, index: int) -> dict[str, object]:
    """The full report for one label in the batch.

    Served on demand rather than inside every progress poll: the report carries
    base64 evidence crops, and 300 of those is about 21 MB — re-sent on every
    tick of a run that lasts minutes.
    """
    job = _job_or_404(job_id)
    results = list(job.results)
    if not 0 <= index < len(results):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "label_not_found",
                "message": f"This batch has no label {index}.",
                "what_to_do": f"Ask for a label between 0 and {max(0, len(results) - 1)}.",
            },
        )
    payload = results[index].payload.get("label")
    if payload is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "label_has_no_report",
                "message": "That label could not be checked, so it has no report.",
                "what_to_do": "The batch table shows the reason on its row.",
            },
        )
    return payload  # type: ignore[return-value]


@router.get("/{job_id}")
def progress(job_id: str) -> dict[str, object]:
    """Progress and every result finished so far.

    Readable mid-run on purpose: an agent can start working the failures before
    the run ends (ui-spec Screen 5).
    """
    return _job_or_404(job_id).snapshot()


@router.post("/{job_id}/stop")
def stop(job_id: str) -> dict[str, object]:
    """Stop between labels. Everything already checked stays."""
    job = _job_or_404(job_id)
    job.stop()
    return job.snapshot()


@router.get("/{job_id}/export")
def export(job_id: str) -> PlainTextResponse:
    """Every result so far as a CSV, problems first."""
    job = _job_or_404(job_id)
    order = {"fail": 0, "unreadable": 1, "error": 2, "needs_review": 3, "pass": 4}
    rows = sorted(job.snapshot()["results"], key=lambda r: order.get(r["outcome"], 9))  # type: ignore[index,arg-type]

    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(["application_id", "image", "outcome", "brand_name", "issues", "reason"])
    for row in rows:
        writer.writerow(
            [
                row.get("application_id", ""),
                row.get("image", ""),
                row.get("outcome", ""),
                row.get("brand_name") or "",
                row.get("issues", ""),
                (row.get("error") or {}).get("message", ""),
            ]
        )
    return PlainTextResponse(
        buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="batch-{job_id}.csv"'},
    )


__all__ = ["COLUMNS", "router"]
