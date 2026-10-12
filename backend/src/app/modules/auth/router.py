from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_session
from app.modules.auth import service
from app.modules.auth.deps import require_role
from app.modules.auth.models import User
from app.modules.auth.schemas import LoginRequest, TokenResponse, UserRead

router = APIRouter()


@router.post("/auth/login", response_model=TokenResponse, tags=["auth"])
def login(
    payload: LoginRequest, session: Annotated[Session, Depends(get_session)]
) -> TokenResponse:
    return TokenResponse(access_token=service.login(session, payload.email, payload.password))


@router.get("/users/me", response_model=UserRead, tags=["auth"])
def read_me(user: Annotated[User, Depends(require_role("viewer"))]) -> User:
    return user
