from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src import database as db
from src.dependencies import get_current_user

router = APIRouter(prefix="/me", tags=["me"])


class LocaleUpdate(BaseModel):
    locale: str = Field(pattern=r"^(de|en)$")


@router.get("")
async def get_me(user: dict = Depends(get_current_user)):
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Nicht authentifiziert")
    row = db.get_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "id": row["id"],
        "username": row["ldap_username"],
        "display_name": row["display_name"],
        "email": row["email"],
        "role": row["role"],
        "locale": row.get("locale", "de"),
    }


@router.patch("/locale")
async def update_locale(payload: LocaleUpdate, user: dict = Depends(get_current_user)):
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Nicht authentifiziert")
    db.update_user_locale(user_id, payload.locale)
    return {"locale": payload.locale}
