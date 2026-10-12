from sqlalchemy.orm import Session

from app.core.security import create_access_token, hash_password
from app.modules.auth.models import User

PASSWORD = "correct-password"


def make_user(session: Session, role: str = "storekeeper", **overrides) -> User:
    values = {
        "email": f"{role}@example.com",
        "password_hash": hash_password(PASSWORD),
        "role": role,
    }
    user = User(**{**values, **overrides})
    session.add(user)
    session.flush()
    return user


def auth_header(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user.id, user.role)}"}
