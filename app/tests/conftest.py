import os
from collections.abc import Callable

import pytest


# SECURITY: unit tests must never inherit the PostgreSQL URL from Compose.
# A previous implementation used setdefault(), allowing pytest to connect to
# the live lab database and drop its tables during fixture cleanup.
test_database_url = os.environ.get("SANOLIFOOD_TEST_DATABASE_URL", "sqlite+pysqlite:///:memory:")
if not test_database_url.startswith("sqlite"):
    raise RuntimeError("SANOLIFOOD_TEST_DATABASE_URL debe apuntar a una base SQLite aislada.")

os.environ["DATABASE_URL"] = test_database_url
os.environ["APP_ENV"] = "test"
os.environ["APP_VERSION"] = "0.7.0"
os.environ["SESSION_SECRET"] = "test-session-secret-with-more-than-thirty-two-characters"
os.environ["SOAR_INTERNAL_TOKEN"] = "test-soar-internal-token-with-more-than-thirty-two-characters"
os.environ["SOAR_DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SOAR_RESPONSE_MODE"] = "dry-run"
os.environ["SOAR_EVIDENCE_DIR"] = "/tmp/sanolifood-soar-test-evidence"

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from sanolifood.core.security import hash_password
from sanolifood.database.base import Base
from sanolifood.database.session import engine
from sanolifood.main import app
from sanolifood.models import User
from sanolifood.soar.database import SoarBase, soar_engine


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.create_all(engine)
    SoarBase.metadata.create_all(soar_engine)
    yield
    SoarBase.metadata.drop_all(soar_engine)
    Base.metadata.drop_all(engine)


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def user_factory() -> Callable[..., User]:
    def create_user(
        *,
        username: str = "admin.sanolifood",
        password: str = "SanoliFood!2026",
        role: str = "admin",
        full_name: str = "Administrador SanoliFood",
    ) -> User:
        with Session(engine) as db:
            user = User(
                username=username,
                email=f"{username}@sanolifood.local",
                full_name=full_name,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            db.expunge(user)
            return user

    return create_user
