import os
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.db.base import Base
from app.db.session import get_db
from app.models import LogFile, LogEntry, PipelineRun, Anomaly, ErrorCluster
from app.models.user import User, UserRole
from app.core.security import hash_password, create_access_token


# In-memory SQLite for tests
TEST_DATABASE_URL = "sqlite://"


@pytest.fixture()
def db_session():
    """Per-test SQLite in-memory session with full rollback."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Enable foreign key support in SQLite
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_conn, connection_record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """TestClient with DB override."""
    from app.main import app

    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def sample_log_file():
    """Path to the sample.log fixture file."""
    return Path(__file__).parent / "fixtures" / "sample.txt"


@pytest.fixture()
def seed_log_entries(db_session):
    """Seed 10 log entries across 3 services with mixed levels."""
    lf = LogFile(
        filename="test.log",
        stored_path="/tmp/test.log",
        status="processed",
        source="unit-test",
        environment="test",
    )
    db_session.add(lf)
    db_session.flush()

    base_time = datetime(2025, 6, 15, 10, 0, 0)
    entries_data = [
        ("INFO", "auth-service", "User logged in"),
        ("INFO", "auth-service", "User logged out"),
        ("ERROR", "auth-service", "Authentication failed"),
        ("INFO", "billing", "Payment processed"),
        ("ERROR", "billing", "Payment failed: insufficient funds"),
        ("WARN", "billing", "Slow payment processing"),
        ("INFO", "gateway", "Request forwarded"),
        ("INFO", "gateway", "Health check ok"),
        ("ERROR", "gateway", "Upstream timeout"),
        ("DEBUG", "gateway", "Connection pool stats"),
    ]

    entries = []
    for i, (level, service, message) in enumerate(entries_data):
        entry = LogEntry(
            log_file_id=lf.id,
            line_number=i + 1,
            timestamp=base_time + timedelta(minutes=i),
            level=level,
            service=service,
            message=message,
            raw_line=f"2025-06-15T10:{i:02d}:00Z {level} {service} {message}",
            parse_status="parsed",
            parse_confidence=0.95,
            parser_name="app_v1",
        )
        entries.append(entry)

    db_session.add_all(entries)
    db_session.commit()

    return {"log_file": lf, "entries": entries}


@pytest.fixture()
def admin_token(db_session):
    """Create an admin user and return a valid JWT token."""
    user = User(
        username="testadmin",
        hashed_password=hash_password("adminpass123"),
        role=UserRole.admin.value,
    )
    db_session.add(user)
    db_session.commit()
    return create_access_token("testadmin", "admin")


@pytest.fixture()
def auth_headers(admin_token):
    """Authorization headers with admin JWT."""
    return {"Authorization": f"Bearer {admin_token}"}
