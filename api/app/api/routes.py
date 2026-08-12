"""HTTP routes for single-label verification.

Two of them, and one is a lookup:

    GET  /api/beverage-types   what the selector should offer, and what to say
                               about the options it must disable
    POST /api/verify           one label, one application, one report

An unreadable image comes back **200 with `overall: "unreadable"`**, not an
error status. It is one of four label outcomes, it carries partial information
worth showing, and the client renders it the same way it renders a verdict
(ui-spec resolution 2). Statuses in the 4xx range are reserved for requests that
were wrong — a beverage type we do not check, a file that is not an image.
"""

from __future__ import annotations

import base64
import time
import uuid

import structlog
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.api.models import (
    BeverageTypeOption,
    ErrorBody,
    FieldOutcome,
    VerificationResponse,
    WarningSubCheck,
)
from app.errors import LabelVerificationError, UnreadableImageError
from app.extraction.client import extract_from_text
from app.ocr.factory import get_engine
from app.pipeline import VerificationResult, verify
from app.review.store import QueueItem, queue
from app.rules.beverage_types import (
    BeverageTypeUnavailableError,
    Requirement,
    available_beverage_types,
    rules_for,
)
from app.rules.engine import Application

log = structlog.get_logger()

router = APIRouter(prefix="/api", tags=["verification"])

# 25 MB. Comfortably above a phone photograph of a bottle, well below anything
# that would tie up a worker for a minute.
MAX_UPLOAD_BYTES = 25 * 1024 * 1024

_WARNING_CHECK_NAMES = {
    "text_exact": "Text matches 27 CFR 16.21 exactly",
    "caps": "GOVERNMENT WARNING in capital letters",
    "bold": "GOVERNMENT WARNING in bold",
    "proportion": "Size relative to surrounding text",
    "contrast": "Contrasting background",
    "field_of_vision": "Brand, class and alcohol content on one side",
}


@router.get("/beverage-types", response_model=list[BeverageTypeOption])
def beverage_types() -> list[BeverageTypeOption]:
    """Every beverage type, including the ones that are not ready.

    The unavailable ones are returned rather than hidden so the UI can show
    them disabled with the reason beside them. Hiding scope makes a product
    look smaller than it is and leaves an agent guessing.
    """
    options = []
    for rules in available_beverage_types():
        alcohol = next(r for r in rules.fields if r.field == "alcohol_content")
        options.append(
            BeverageTypeOption(
                beverage_type=rules.beverage_type,
                display_name=rules.display_name,
                citation=rules.citation,
                available=rules.available,
                unavailable_reason=rules.unavailable_reason,
                alcohol_content_required=alcohol.requirement is Requirement.REQUIRED,
                alcohol_content_note=alcohol.condition,
            )
        )
    return options


def _crop_uri(crops: dict[str, bytes], field: str) -> str | None:
    data = crops.get(field)
    if not data:
        return None
    return "data:image/png;base64," + base64.b64encode(data).decode()


def _to_response(
    result: VerificationResult,
    *,
    application_id: str | None,
    reviewer: str | None,
) -> VerificationResponse:
    rules = rules_for(result.report.beverage_type)
    display_names = {rule.field: rule.display_name for rule in rules.fields}
    citations = {rule.field: rule.citation for rule in rules.fields}
    crops = dict(result.crops)

    return VerificationResponse(
        label_id=application_id,
        beverage_type=result.report.beverage_type,
        overall=result.report.overall.value,
        processing_ms=round(result.timings.total_ms),
        reviewer=reviewer or None,
        ocr_engine=result.ocr_engine,
        counts={verdict.value: count for verdict, count in result.report.counts.items()},
        stage_ms=result.timings.as_dict(),
        fields=[
            FieldOutcome(
                field=field.field,
                display_name=display_names.get(field.field, field.field),
                declared=field.declared,
                detected=field.detected,
                verdict=field.verdict.value,
                confidence=round(field.confidence, 2),
                reason=field.reason,
                crop_url=_crop_uri(crops, field.field),
                citation=citations.get(field.field),
            )
            for field in result.report.fields
        ],
        warning_checks=[
            WarningSubCheck(
                check=check.check.value,
                display_name=_WARNING_CHECK_NAMES.get(check.check.value, check.check.value),
                verdict=check.verdict.value,
                reason=check.reason,
            )
            for check in result.report.warning_checks
        ],
    )


@router.post("/verify", response_model=VerificationResponse)
async def verify_label(
    image: UploadFile = File(description="Label artwork, JPG or PNG"),
    beverage_type: str = Form("spirits"),
    application_id: str | None = Form(None),
    reviewer: str | None = Form(None),
    brand_name: str | None = Form(None),
    class_type: str | None = Form(None),
    alcohol_content: str | None = Form(None),
    net_contents: str | None = Form(None),
    bottler_address: str | None = Form(None),
    country_of_origin: str | None = Form(None),
) -> VerificationResponse:
    """Check one label against the values declared in its application."""
    started = time.perf_counter()
    image_bytes = await image.read()
    if not image_bytes:
        raise _bad_request(
            code="empty_upload",
            message="No image arrived with the request.",
            what_to_do="Choose the label artwork file and submit again.",
        )
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise _bad_request(
            code="image_too_large",
            message=(
                f"That file is {len(image_bytes) // (1024 * 1024)} MB, over the "
                f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB limit."
            ),
            what_to_do="Send a smaller copy. A normal photograph is a few megabytes.",
        )

    application = Application(
        beverage_type=beverage_type,
        application_id=application_id or None,
        fields={
            "brand_name": brand_name,
            "class_type": class_type,
            "alcohol_content": alcohol_content,
            "net_contents": net_contents,
            "bottler_address": bottler_address,
            "country_of_origin": country_of_origin,
        },
    )

    try:
        rules_for(beverage_type)
    except KeyError as exc:
        raise _bad_request(
            code="unknown_beverage_type",
            message=str(exc).strip("\"'"),
            what_to_do="Choose spirits, wine, or malt beverage.",
        ) from exc

    try:
        result = verify(
            image_bytes,
            application,
            ocr=get_engine(),
            extract=lambda text: extract_from_text(text).fields,
        )
    except UnreadableImageError as exc:
        # A label outcome, not a request failure. The agent sees the same
        # screen, carrying a reason they can act on. The elapsed time is real:
        # batch progress aggregates all four buckets, and reporting zero here
        # makes its estimate wrong.
        return VerificationResponse(
            label_id=application_id or None,
            beverage_type=beverage_type,
            overall="unreadable",
            processing_ms=round((time.perf_counter() - started) * 1000),
            reviewer=reviewer or None,
            error=ErrorBody(**exc.as_dict(), partial_fields_shown=False),
        )
    except BeverageTypeUnavailableError as exc:
        raise _bad_request(
            code="beverage_type_unavailable",
            message=str(exc),
            what_to_do="Check a distilled spirits label, which works today.",
        ) from exc
    except LabelVerificationError as exc:
        raise HTTPException(status_code=502, detail=exc.as_dict()) from exc
    except (OSError, RuntimeError, ValueError) as exc:
        # A provider that is down, unauthenticated, or misconfigured. The
        # agent's screen has a line for exactly this (ui-spec Screen 7), and it
        # is not "processing failed".
        log.error("verification_failed", error=str(exc)[:500])
        raise HTTPException(
            status_code=502,
            detail={
                "code": "service_unavailable",
                "message": "Can't reach the label reading service right now.",
                "what_to_do": "Your entry has been kept. Try again in a moment.",
            },
        ) from exc

    response = _to_response(result, application_id=application_id, reviewer=reviewer)
    # A checked label joins the queue, so an agent who uploads one finds it
    # beside everything else waiting rather than losing it when they navigate
    # away. It lives for the life of the process, like the rest of the queue.
    queue.add(
        QueueItem(
            id=f"upload-{uuid.uuid4().hex[:8]}",
            brand=brand_name or application_id or "Uploaded label",
            beverage_type=beverage_type,
            outcome=response.overall,
            processing_ms=response.processing_ms,
            source="uploaded",
            received_at=time.time(),
            result=response.model_dump(mode="json"),
        )
    )
    return response


def _bad_request(*, code: str, message: str, what_to_do: str) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={"code": code, "message": message, "what_to_do": what_to_do},
    )
