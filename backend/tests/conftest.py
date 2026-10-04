import os

# Must be set before the app modules are imported.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://hga:hga@localhost:5432/hga_test")
os.environ["SIMILARITY_THRESHOLD"] = "0.3"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.agent.llm import set_llm
from app.core.security import CurrentUser, get_current_user
from app.db.session import SessionLocal, engine, init_db
from app.main import app
from app.services.embeddings import set_embeddings
from tests.fakes import HashEmbeddings, ScriptedChatModel, default_responder

ALICE = CurrentUser(id="user-alice", username="alice", roles=["user"])
BOB = CurrentUser(id="user-bob", username="bob", roles=["user"])
ADMIN = CurrentUser(id="user-admin", username="admin", roles=["user", "admin"])


@pytest.fixture(autouse=True)
def _fakes():
    set_embeddings(HashEmbeddings())
    set_llm(ScriptedChatModel(responder=default_responder))
    yield
    set_embeddings(None)
    set_llm(None)


@pytest.fixture(autouse=True)
def _clean_db():
    init_db()
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE messages, conversations, chunks, documents RESTART IDENTITY CASCADE"))
    yield


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def as_user():
    """Return a TestClient authenticated as the given user."""

    def _make(user: CurrentUser = ALICE) -> TestClient:
        app.dependency_overrides[get_current_user] = lambda: user
        return TestClient(app)

    yield _make
    app.dependency_overrides.clear()


@pytest.fixture
def anon_client():
    app.dependency_overrides.clear()
    return TestClient(app)
