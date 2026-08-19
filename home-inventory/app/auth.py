"""One password, one signed cookie. No users table, per constitution principle I."""

import hmac
import time

from fastapi import Cookie, Depends, HTTPException, Response, status
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.config import Settings, get_settings

COOKIE_NAME = "session"
_SALT = "my-stuff-session"


def _serializer(settings: Settings) -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.session_secret, salt=_SALT)


def password_is_correct(candidate: str, settings: Settings) -> bool:
    # Constant-time so the response time does not leak how much of the password was right.
    return hmac.compare_digest(candidate, settings.app_password)


def issue_session(response: Response, settings: Settings) -> None:
    max_age = settings.session_max_age_days * 24 * 60 * 60
    token = _serializer(settings).dumps({"issued": int(time.time())})
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=max_age,
        httponly=True,
        samesite="lax",
        # Set on Cloud Run, which is HTTPS-only; left off for plain-HTTP local development,
        # where the browser would otherwise discard the cookie entirely.
        secure=settings.storage_backend == "gcs",
        path="/",
    )


def clear_session(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


def require_session(
    session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    settings: Settings = Depends(get_settings),
) -> None:
    """Dependency guarding every router that touches inventory data (FR-020)."""
    if session is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not signed in")
    max_age = settings.session_max_age_days * 24 * 60 * 60
    try:
        _serializer(settings).loads(session, max_age=max_age)
    except BadSignature as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session is not valid") from exc
