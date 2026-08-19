from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.auth import clear_session, issue_session, password_is_correct, require_session
from app.config import Settings, get_settings
from app.schemas import LoginRequest

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
def login(
    body: LoginRequest, response: Response, settings: Settings = Depends(get_settings)
) -> None:
    if not password_is_correct(body.password, settings):
        # Deliberately says nothing about why (FR-021 scenario 3).
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect password")
    issue_session(response, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    clear_session(response)


@router.get("/me")
def me(_: None = Depends(require_session)) -> dict[str, bool]:
    return {"authenticated": True}
