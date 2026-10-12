from collections.abc import Callable
from typing import Annotated

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import Forbidden, Unauthorized
from app.core.security import decode_access_token
from app.db.session import get_session
from app.modules.auth import service
from app.modules.auth.models import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: Annotated[Session, Depends(get_session)],
) -> User:
    if credentials is None:
        raise Unauthorized("Требуется авторизация")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
        raise Unauthorized("Недействительный токен") from exc
    return service.get_active_user(session, user_id)


def require_role(minimal_role: str) -> Callable[..., User]:
    """viewer < storekeeper < admin: пользователь с ролью не ниже указанной."""

    def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if service.ROLE_LEVELS.get(user.role, 0) < service.ROLE_LEVELS[minimal_role]:
            raise Forbidden("Недостаточно прав для этого действия")
        return user

    return dependency
