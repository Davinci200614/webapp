from typing import Annotated

from fastapi import APIRouter, Depends, Header

from ..auth import LoginRequest, current_role, login, logout

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/login")
def create_session(payload: LoginRequest):
    token, operator = login(payload)
    return {"access_token": token, "token_type": "bearer", "operator": operator}


@router.post("/logout")
def delete_session(authorization: Annotated[str | None, Header()] = None):
    if authorization and authorization.startswith("Bearer "):
        logout(authorization.removeprefix("Bearer ").strip())
    return {"ok": True}


@router.get("/me")
def session_identity(role: str = Depends(current_role)):
    return {"role": role}
