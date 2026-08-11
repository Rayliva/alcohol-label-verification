"""One shared agent credential, carried in a signed cookie.

Deliberately not an identity system. The brief asks for no accounts and this
prototype stores nothing, so there is no user table, no password hash at rest
and no reset flow — there is a gate on a public URL, and a session cookie that
proves someone passed it.

What it still does properly: the credential comes from the environment
(.claude/rules/secrets.md), it is compared in constant time, the cookie is
signed so it cannot be forged, and a missing credential stops the app at boot
rather than quietly serving an open one.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Cookie, HTTPException

from app.config import settings

COOKIE_NAME = "label_check_session"
SESSION_MAX_AGE_SECONDS = 12 * 60 * 60

# Regenerated per process when unset, which logs everyone out on restart. That
# is a nuisance, not a hole; a shared secret checked into source would be one.
_FALLBACK_SECRET = secrets.token_urlsafe(32)


def _secret() -> bytes:
    return (settings.session_secret or _FALLBACK_SECRET).encode()


def _sign(payload: bytes) -> str:
    return base64.urlsafe_b64encode(hmac.new(_secret(), payload, hashlib.sha256).digest()).decode()


def credentials_are_configured() -> bool:
    return bool(settings.agent_username and settings.agent_password)


def check_credentials(username: str, password: str) -> bool:
    """Constant-time comparison, so a wrong answer takes as long as a right one."""
    user_ok = hmac.compare_digest(username or "", settings.agent_username)
    password_ok = hmac.compare_digest(password or "", settings.agent_password)
    return user_ok and password_ok


def issue_session(username: str) -> str:
    payload = json.dumps({"u": username, "t": int(time.time())}, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(payload).decode() + "." + _sign(payload)


def read_session(token: str | None) -> str | None:
    """Return the signed-in username, or None. Never raises on bad input."""
    if not token or "." not in token:
        return None
    encoded, _, signature = token.partition(".")
    try:
        payload = base64.urlsafe_b64decode(encoded.encode())
    except (ValueError, TypeError):
        return None
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        claims = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if int(time.time()) - int(claims.get("t", 0)) > SESSION_MAX_AGE_SECONDS:
        return None
    username = claims.get("u")
    return username if isinstance(username, str) else None


def require_agent(
    label_check_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
) -> str:
    """FastAPI dependency. 401 with a cause, never a bare one."""
    username = read_session(label_check_session)
    if username is None:
        raise HTTPException(
            status_code=401,
            detail={
                "code": "not_signed_in",
                "message": "This session has expired or was never signed in.",
                "what_to_do": "Sign in again to continue reviewing labels.",
            },
        )
    return username
