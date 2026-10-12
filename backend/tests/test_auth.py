from typing import Annotated

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.errors import register_error_handlers
from app.core.security import create_access_token, hash_password
from app.db.session import get_session
from app.modules.auth.deps import require_role
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


def test_login_returns_token(client: TestClient, session: Session) -> None:
    make_user(session)
    response = client.post(
        "/api/v1/auth/login", json={"email": "storekeeper@example.com", "password": PASSWORD}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_is_case_insensitive_for_email(client: TestClient, session: Session) -> None:
    make_user(session)
    response = client.post(
        "/api/v1/auth/login", json={"email": "Storekeeper@Example.com", "password": PASSWORD}
    )
    assert response.status_code == 200


def test_login_with_wrong_password(client: TestClient, session: Session) -> None:
    make_user(session)
    response = client.post(
        "/api/v1/auth/login", json={"email": "storekeeper@example.com", "password": "nope"}
    )
    assert response.status_code == 401
    assert response.json()["code"] == "UNAUTHORIZED"


def test_login_unknown_email(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": PASSWORD}
    )
    assert response.status_code == 401


def test_login_inactive_user(client: TestClient, session: Session) -> None:
    make_user(session, is_active=False)
    response = client.post(
        "/api/v1/auth/login", json={"email": "storekeeper@example.com", "password": PASSWORD}
    )
    assert response.status_code == 401


def test_login_validation_error(client: TestClient) -> None:
    response = client.post("/api/v1/auth/login", json={"email": "a@example.com"})
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_me_returns_current_user(client: TestClient, session: Session) -> None:
    user = make_user(session, role="viewer")
    response = client.get("/api/v1/users/me", headers=auth_header(user))
    assert response.status_code == 200
    assert response.json() == {
        "id": user.id,
        "email": "viewer@example.com",
        "role": "viewer",
        "is_active": True,
    }


def test_me_without_token(client: TestClient) -> None:
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401


def test_me_with_garbage_token(client: TestClient) -> None:
    response = client.get("/api/v1/users/me", headers={"Authorization": "Bearer abc"})
    assert response.status_code == 401


def test_me_for_deactivated_user(client: TestClient, session: Session) -> None:
    user = make_user(session)
    headers = auth_header(user)
    user.is_active = False
    session.flush()
    assert client.get("/api/v1/users/me", headers=headers).status_code == 401


@pytest.mark.parametrize(
    ("user_role", "required", "expected"),
    [
        ("viewer", "viewer", 200),
        ("viewer", "storekeeper", 403),
        ("viewer", "admin", 403),
        ("storekeeper", "storekeeper", 200),
        ("storekeeper", "admin", 403),
        ("admin", "viewer", 200),
        ("admin", "storekeeper", 200),
        ("admin", "admin", 200),
    ],
)
def test_role_hierarchy(session: Session, user_role: str, required: str, expected: int) -> None:
    app = FastAPI()
    register_error_handlers(app)
    app.dependency_overrides[get_session] = lambda: session

    @app.get("/protected")
    def protected(user: Annotated[User, Depends(require_role(required))]) -> dict[str, str]:
        return {"role": user.role}

    user = make_user(session, role=user_role)
    response = TestClient(app).get("/protected", headers=auth_header(user))
    assert response.status_code == expected
    if expected == 403:
        assert response.json()["code"] == "FORBIDDEN"
