import asyncio
import os
from pathlib import Path
import sys
from urllib.parse import parse_qs, urlparse

from fastapi.security import HTTPAuthorizationCredentials
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure backend imports resolve in tests.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite:///tmp/auth-session-token-tests.db")

from yudai.auth import auth_routes  # noqa: E402
import yudai.auth.github_oauth as github_oauth  # noqa: E402
from yudai.models import Base, SessionToken, User  # noqa: E402
from yudai.utils import ensure_utc, utc_now  # noqa: E402


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_auth_callback_creates_session_token_and_redirects(db_session, monkeypatch):
    async def fake_exchange_code(code: str):
        assert code == "oauth-test-code"
        return {
            "access_token": "gho_test_access_token",
            "installation": {"id": 123456},
            "permissions": {"contents": "write"},
            "repositories_url": "https://api.github.com/installation/repositories",
        }

    async def fake_user_info(access_token: str):
        assert access_token == "gho_test_access_token"
        return {
            "id": 424242,
            "login": "octocat",
            "name": "The Octocat",
            "email": "octocat@example.com",
            "avatar_url": "https://example.com/octocat.png",
        }

    monkeypatch.setattr(auth_routes, "exchange_code", fake_exchange_code)
    monkeypatch.setattr(auth_routes, "user_info", fake_user_info)
    monkeypatch.setattr(auth_routes, "get_frontend_base_url", lambda: "http://frontend.test")

    response = asyncio.run(
        auth_routes.auth_callback(
            code="oauth-test-code",
            db=db_session,
        )
    )

    assert response.status_code == 302

    redirect_url = response.headers["location"]
    parsed = urlparse(redirect_url)
    params = parse_qs(parsed.query)

    assert redirect_url.startswith("http://frontend.test/auth/success?")
    assert params["username"] == ["octocat"]
    assert params["email"] == ["octocat@example.com"]
    assert "session_token" in params

    session_token = params["session_token"][0]
    user = db_session.query(User).filter(User.github_username == "octocat").one()
    token_row = (
        db_session.query(SessionToken)
        .filter(SessionToken.session_token == session_token)
        .one()
    )

    assert token_row.user_id == user.id
    assert token_row.is_active is True
    assert ensure_utc(token_row.expires_at) > utc_now()


def test_api_user_accepts_session_token(db_session):
    user = User(
        github_username="session-user",
        github_user_id="9001",
        email="session-user@example.com",
        display_name="Session User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    session_token = github_oauth.create_session_token(db_session, user.id, expires_in_hours=1)
    credentials = HTTPAuthorizationCredentials(
        scheme="Bearer",
        credentials=session_token.session_token,
    )

    current_user = asyncio.run(
        github_oauth.get_current_user(
            credentials=credentials,
            db=db_session,
        )
    )
    payload = asyncio.run(auth_routes.api_get_user(current_user=current_user))

    assert payload == {
        "id": user.id,
        "github_username": "session-user",
        "github_id": "9001",
        "display_name": "Session User",
        "email": "session-user@example.com",
        "avatar_url": None,
    }


def test_get_current_user_accepts_internal_middleware_identity(db_session, monkeypatch):
    monkeypatch.setenv("YUDAI_INTERNAL_MIDDLEWARE_SECRET", "internal-test-secret")
    user = User(
        github_username="internal-user",
        github_user_id="9002",
        email="internal-user@example.com",
        display_name="Internal User",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    current_user = asyncio.run(
        github_oauth.get_current_user(
            credentials=None,
            db=db_session,
            x_yudai_internal_secret="internal-test-secret",
            x_yudai_user_id=str(user.id),
        )
    )

    assert current_user.id == user.id


def test_get_current_user_rejects_invalid_internal_middleware_identity(db_session, monkeypatch):
    monkeypatch.setenv("YUDAI_INTERNAL_MIDDLEWARE_SECRET", "internal-test-secret")

    with pytest.raises(Exception) as exc_info:
        asyncio.run(
            github_oauth.get_current_user(
                credentials=None,
                db=db_session,
                x_yudai_internal_secret="wrong-secret",
                x_yudai_user_id="1",
            )
        )

    assert getattr(exc_info.value, "status_code", None) == 401
