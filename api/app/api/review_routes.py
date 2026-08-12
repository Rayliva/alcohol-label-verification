"""Sign in, and work a queue of applications.

The queue is the front door. An agent pulls up an application that is already
waiting for them and reads a verdict that has already been computed — which is
the workflow the brief describes ("An agent pulls up an application, looks at
the label artwork, and checks that what's on the label matches"), rather than
asking them to key in the application first.

Uploading is still here, on /api/verify, and still synchronous: that is where
the five-second budget is demonstrated.
"""

from __future__ import annotations

import mimetypes
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.auth import COOKIE_NAME, check_credentials, issue_session, require_agent
from app.config import settings
from app.review.store import SAMPLES, queue

# Two routers so the gate is structural: `public` carries exactly the two
# routes that must work without a session (sign in, sign out), and everything
# on `router` is guarded at include time in main.py. A route added here is
# closed by default rather than open by default.
public = APIRouter(prefix="/api", tags=["review"])
router = APIRouter(prefix="/api", tags=["review"])


class Credentials(BaseModel):
    username: str
    password: str


class SessionBody(BaseModel):
    username: str


class DecisionBody(BaseModel):
    action: Literal["approve", "reject", "override"]
    note: str = Field(default="", max_length=2000)


@public.post("/login", response_model=SessionBody)
def login(credentials: Credentials, response: Response) -> SessionBody:
    if not check_credentials(credentials.username, credentials.password):
        # One message for both wrong-user and wrong-password: saying which was
        # wrong tells an attacker which half to keep.
        raise HTTPException(
            status_code=401,
            detail={
                "code": "sign_in_failed",
                "message": "That username and password did not match.",
                "what_to_do": "Check both and try again.",
            },
        )
    response.set_cookie(
        COOKIE_NAME,
        issue_session(credentials.username),
        httponly=True,
        samesite="lax",
        # Secure unless explicitly switched off for local http. This was
        # derived from the CORS origin string, which on the deployed instance
        # still began with http://localhost — so the flag was off in
        # production, over HTTPS, which is exactly where it matters.
        secure=not settings.insecure_cookies,
        path="/",
    )
    return SessionBody(username=credentials.username)


@public.post("/logout")
def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"signed_out": True}


@router.get("/session", response_model=SessionBody)
def session(username: str = Depends(require_agent)) -> SessionBody:
    return SessionBody(username=username)


@router.get("/queue")
def list_queue(username: str = Depends(require_agent)) -> dict[str, Any]:
    items = queue.list()
    return {
        "items": [item.summary() for item in items],
        "counts": {
            outcome: sum(1 for i in items if i.outcome == outcome)
            for outcome in ("needs_review", "unreadable", "fail", "pass")
        },
        "awaiting_decision": sum(1 for i in items if i.decision is None),
    }


@router.get("/queue/{item_id}")
def get_item(item_id: str, username: str = Depends(require_agent)) -> dict[str, Any]:
    item = queue.get(item_id)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "application_not_found",
                "message": f"No application {item_id!r} is in the queue.",
                "what_to_do": "Go back to the queue and pick an application from the list.",
            },
        )
    return {
        **item.summary(),
        "result": item.result,
        "unreadable": item.unreadable,
        "has_image": bool(item.image_name),
    }


@router.get("/queue/{item_id}/image")
def get_image(item_id: str, username: str = Depends(require_agent)) -> FileResponse:
    item = queue.get(item_id)
    if item is None or not item.image_name:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "label_image_unavailable",
                "message": "The artwork for this application is not available.",
                "what_to_do": "The verdict and evidence below were recorded and are still valid.",
            },
        )
    # Seeded artwork only, and the name comes from the record rather than the
    # request, so a path cannot be steered from outside.
    path = (SAMPLES / item.image_name).resolve()
    if not path.is_file() or SAMPLES.resolve() not in path.parents:
        raise HTTPException(status_code=404, detail={"code": "label_image_unavailable"})
    return FileResponse(path, media_type=mimetypes.guess_type(path.name)[0] or "image/jpeg")


@router.post("/queue/{item_id}/decision")
def decide(
    item_id: str, body: DecisionBody, username: str = Depends(require_agent)
) -> dict[str, Any]:
    item = queue.decide(item_id, action=body.action, note=body.note, by=username)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "application_not_found",
                "message": f"No application {item_id!r} is in the queue.",
                "what_to_do": "Go back to the queue and pick an application from the list.",
            },
        )
    # Where to go from here: the first undecided item in the queue's own
    # order, so deciding flows straight into the next application.
    next_item = queue.next_undecided()
    return {**item.summary(), "next_id": next_item.id if next_item else None}
