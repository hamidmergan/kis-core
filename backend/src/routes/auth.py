from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from src.dependencies import get_settings, get_session_store

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
async def login(body: LoginRequest, response: Response):
    settings = get_settings()
    if body.password != settings.app_password:
        raise HTTPException(status_code=401, detail="Falsches Passwort")

    store = get_session_store()
    token = store.create()
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.session_max_age_seconds,
        secure=False,  # Set True behind HTTPS/Nginx
    )
    return {"status": "ok"}


@router.post("/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session")
    if token:
        store = get_session_store()
        store.destroy(token)
    response.delete_cookie("session")
    return {"status": "ok"}


@router.get("/status")
async def auth_status(request: Request):
    token = request.cookies.get("session")
    if not token:
        return {"authenticated": False}
    store = get_session_store()
    return {"authenticated": store.validate(token)}
