"""Pytest fixtures using an isolated SQLite database."""

from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.db.database import build_engine, get_db, init_db
from app.db.seed import seed_initial_data
from app.main import create_app


@pytest.fixture()
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
    """Yield a FastAPI TestClient backed by an isolated temporary SQLite DB."""
    db_file = tmp_path / "test_nexus.db"
    test_engine = build_engine(f"sqlite:///{db_file.as_posix()}")
    TestSessionLocal = sessionmaker(bind=test_engine, autoflush=False, autocommit=False, expire_on_commit=False)

    init_db(target_engine=test_engine)
    with TestSessionLocal() as db:
        seed_initial_data(db)

    app = create_app(initialize_db=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = TestSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client

    test_engine.dispose()

