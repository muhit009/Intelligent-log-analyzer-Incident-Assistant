"""Tests for auth & RBAC: unit tests for security utils, integration tests for endpoints."""

import time

import pytest
from datetime import timedelta

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_api_key,
    hash_api_key,
)
from app.models.user import User, UserRole


# ── Unit tests ──────────────────────────────────────────────────────────────


class TestPasswordHashing:
    def test_round_trip(self):
        hashed = hash_password("my-secret-password")
        assert verify_password("my-secret-password", hashed)

    def test_wrong_password(self):
        hashed = hash_password("correct")
        assert not verify_password("wrong", hashed)


class TestJWT:
    def test_round_trip(self):
        token = create_access_token("alice", "admin")
        payload = decode_access_token(token)
        assert payload["sub"] == "alice"
        assert payload["role"] == "admin"

    def test_expired_token(self):
        token = create_access_token("alice", "viewer", expires_delta=timedelta(seconds=-1))
        with pytest.raises(Exception):
            decode_access_token(token)


class TestAPIKeyUtils:
    def test_generate_length(self):
        key = generate_api_key()
        assert len(key) == 48

    def test_hash_deterministic(self):
        key = generate_api_key()
        assert hash_api_key(key) == hash_api_key(key)

    def test_different_keys_different_hashes(self):
        k1, k2 = generate_api_key(), generate_api_key()
        assert hash_api_key(k1) != hash_api_key(k2)


# ── Integration tests ──────────────────────────────────────────────────────


@pytest.fixture()
def admin_user(db_session):
    user = User(
        username="admin",
        hashed_password=hash_password("adminpass123"),
        role=UserRole.admin.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def viewer_user(db_session):
    user = User(
        username="viewer",
        hashed_password=hash_password("viewerpass123"),
        role=UserRole.viewer.value,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class TestLogin:
    def test_login_success(self, client, admin_user):
        r = client.post("/auth/login", json={"username": "admin", "password": "adminpass123"})
        assert r.status_code == 200
        data = r.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_wrong_password(self, client, admin_user):
        r = client.post("/auth/login", json={"username": "admin", "password": "wrong"})
        assert r.status_code == 401

    def test_login_nonexistent_user(self, client):
        r = client.post("/auth/login", json={"username": "nobody", "password": "pass"})
        assert r.status_code == 401


class TestMe:
    def test_me_with_jwt(self, client, admin_user):
        token = create_access_token("admin", "admin")
        r = client.get("/auth/me", headers=_auth_header(token))
        assert r.status_code == 200
        assert r.json()["username"] == "admin"

    def test_me_with_api_key(self, client, admin_user, db_session):
        # Create an API key via the endpoint
        token = create_access_token("admin", "admin")
        r = client.post(
            "/auth/api-keys",
            json={"name": "test-key"},
            headers=_auth_header(token),
        )
        assert r.status_code == 201
        raw_key = r.json()["raw_key"]

        r = client.get("/auth/me", headers={"X-API-Key": raw_key})
        assert r.status_code == 200
        assert r.json()["username"] == "admin"

    def test_me_unauthenticated(self, client):
        r = client.get("/auth/me")
        assert r.status_code == 401


class TestUserCreation:
    def test_admin_creates_user(self, client, admin_user):
        token = create_access_token("admin", "admin")
        r = client.post(
            "/auth/users",
            json={"username": "newuser", "password": "newpass123", "role": "viewer"},
            headers=_auth_header(token),
        )
        assert r.status_code == 201
        assert r.json()["username"] == "newuser"
        assert r.json()["role"] == "viewer"

    def test_viewer_cannot_create_user(self, client, viewer_user):
        token = create_access_token("viewer", "viewer")
        r = client.post(
            "/auth/users",
            json={"username": "newuser", "password": "newpass123"},
            headers=_auth_header(token),
        )
        assert r.status_code == 403

    def test_duplicate_username_rejected(self, client, admin_user):
        token = create_access_token("admin", "admin")
        client.post(
            "/auth/users",
            json={"username": "dup", "password": "password123"},
            headers=_auth_header(token),
        )
        r = client.post(
            "/auth/users",
            json={"username": "dup", "password": "password123"},
            headers=_auth_header(token),
        )
        assert r.status_code == 409


class TestAPIKeyCRUD:
    def test_create_and_list(self, client, admin_user):
        token = create_access_token("admin", "admin")
        r = client.post(
            "/auth/api-keys",
            json={"name": "my-key"},
            headers=_auth_header(token),
        )
        assert r.status_code == 201
        assert "raw_key" in r.json()

        r = client.get("/auth/api-keys", headers=_auth_header(token))
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["name"] == "my-key"
        assert "raw_key" not in r.json()[0]

    def test_revoke_key(self, client, admin_user):
        token = create_access_token("admin", "admin")
        r = client.post(
            "/auth/api-keys",
            json={"name": "to-revoke"},
            headers=_auth_header(token),
        )
        key_id = r.json()["id"]
        raw_key = r.json()["raw_key"]

        r = client.delete(f"/auth/api-keys/{key_id}", headers=_auth_header(token))
        assert r.status_code == 204

        # Revoked key should not authenticate
        r = client.get("/auth/me", headers={"X-API-Key": raw_key})
        assert r.status_code == 401


class TestRouteGuards:
    def test_public_routes_no_auth(self, client):
        assert client.get("/health").status_code == 200
        assert client.get("/").status_code == 200

    def test_viewer_can_read(self, client, viewer_user, seed_log_entries):
        token = create_access_token("viewer", "viewer")
        headers = _auth_header(token)
        assert client.get("/logs", headers=headers).status_code == 200
        assert client.get("/logs/files", headers=headers).status_code == 200
        assert client.get("/stats/summary", headers=headers).status_code == 200
        assert client.get("/analytics/anomalies", headers=headers).status_code == 200
        assert client.get("/analytics/clusters", headers=headers).status_code == 200

    def test_viewer_blocked_from_admin_routes(self, client, viewer_user):
        token = create_access_token("viewer", "viewer")
        headers = _auth_header(token)
        assert client.post("/analytics/run", headers=headers).status_code == 403

    def test_admin_can_access_all(self, client, admin_user, seed_log_entries):
        token = create_access_token("admin", "admin")
        headers = _auth_header(token)
        assert client.get("/logs", headers=headers).status_code == 200
        assert client.post("/analytics/run", headers=headers).status_code == 202

    def test_unauthenticated_blocked(self, client):
        assert client.get("/logs").status_code == 401
        assert client.get("/stats/summary").status_code == 401
