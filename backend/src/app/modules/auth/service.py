from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import Unauthorized
from app.core.security import create_access_token, verify_password
from app.modules.auth.models import User

ROLE_LEVELS = {"viewer": 1, "storekeeper": 2, "admin": 3}


def authenticate(session: Session, email: str, password: str) -> User:
    user = session.scalar(select(User).where(User.email == email.strip().lower()))
    if user is None or not user.is_active or not verify_password(password, user.password_hash):
        raise Unauthorized("Неверный email или пароль")
    return user


def login(session: Session, email: str, password: str) -> str:
    user = authenticate(session, email, password)
    return create_access_token(user.id, user.role)


def get_active_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise Unauthorized("Пользователь не найден или отключён")
    return user
