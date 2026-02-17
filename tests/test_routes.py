"""Endpoint integration tests using TestClient + SQLite."""
import io
from pathlib import Path
from unittest.mock import patch

import pytest


class TestHealthAndRoot:
    def test_health(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_root(self, client):
        r = client.get("/")
        assert r.status_code == 200
        content_type = r.headers.get("content-type", "")
        if "text/html" in content_type:
            assert "Log Analyzer" in r.text
        else:
            body = r.json()
            assert "message" in body


class TestUpload:
    @patch("app.routes.logs.run_ingestion")
    def test_valid_upload(self, mock_ingestion, client, sample_log_file, auth_headers):
        content = sample_log_file.read_bytes()
        r = client.post(
            "/logs/upload",
            files={"file": ("test.log", io.BytesIO(content), "text/plain")},
            headers=auth_headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "uploaded"
        assert "log_file_id" in body
        mock_ingestion.assert_called_once()

    def test_invalid_extension(self, client, auth_headers):
        r = client.post(
            "/logs/upload",
            files={"file": ("test.exe", io.BytesIO(b"data"), "application/octet-stream")},
            headers=auth_headers,
        )
        assert r.status_code == 400
        assert "Invalid file type" in r.json()["detail"]

    def test_no_filename(self, client, auth_headers):
        r = client.post(
            "/logs/upload",
            files={"file": ("", io.BytesIO(b"data"), "text/plain")},
            headers=auth_headers,
        )
        assert r.status_code in (400, 422)


class TestListFiles:
    def test_empty(self, client, auth_headers):
        r = client.get("/logs/files", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0
        assert body["items"] == []

    def test_with_data(self, client, seed_log_entries, auth_headers):
        r = client.get("/logs/files", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1

    def test_filter_by_status(self, client, seed_log_entries, auth_headers):
        r = client.get("/logs/files", params={"status": "processed"}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 1

        r = client.get("/logs/files", params={"status": "uploaded"}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 0


class TestGetFile:
    def test_found(self, client, seed_log_entries, auth_headers):
        file_id = seed_log_entries["log_file"].id
        r = client.get(f"/logs/files/{file_id}", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["id"] == file_id

    def test_not_found(self, client, auth_headers):
        r = client.get("/logs/files/99999", headers=auth_headers)
        assert r.status_code == 404


class TestLogEntries:
    def test_empty(self, client, auth_headers):
        r = client.get("/logs", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_with_data(self, client, seed_log_entries, auth_headers):
        r = client.get("/logs", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 10

    def test_level_filter(self, client, seed_log_entries, auth_headers):
        r = client.get("/logs", params={"level": "ERROR"}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 3

    def test_service_filter(self, client, seed_log_entries, auth_headers):
        r = client.get("/logs", params={"service": "billing"}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 3

    def test_keyword_search(self, client, seed_log_entries, auth_headers):
        # "Payment" matches 3 entries via case-insensitive ilike:
        # "Payment processed", "Payment failed: ...", "Slow payment processing"
        r = client.get("/logs", params={"keyword": "Payment"}, headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 3

    def test_pagination(self, client, seed_log_entries, auth_headers):
        r = client.get("/logs", params={"offset": 0, "limit": 3}, headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert len(body["items"]) == 3
        assert body["total"] == 10


class TestStatsSummary:
    def test_empty(self, client, auth_headers):
        r = client.get("/stats/summary", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total_entries"] == 0
        assert body["total_files"] == 0
        assert body["level_breakdown"] == []
        assert body["top_services"] == []

    def test_with_data(self, client, seed_log_entries, auth_headers):
        r = client.get("/stats/summary", headers=auth_headers)
        assert r.status_code == 200
        body = r.json()
        assert body["total_entries"] == 10
        assert body["total_files"] == 1
        assert len(body["level_breakdown"]) > 0
        assert len(body["top_services"]) > 0


class TestAnalyticsEndpoints:
    def test_anomalies_empty(self, client, auth_headers):
        r = client.get("/analytics/anomalies", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    def test_clusters_empty(self, client, auth_headers):
        r = client.get("/analytics/clusters", headers=auth_headers)
        assert r.status_code == 200
        assert r.json()["total"] == 0

    @patch("app.routes.analytics._run_analytics_background")
    def test_trigger_run(self, mock_run, client, auth_headers):
        r = client.post("/analytics/run", headers=auth_headers)
        assert r.status_code == 202
        assert r.json()["status"] == "accepted"


class TestExceptionHandler:
    def test_exception_handler_registered(self, client):
        from app.main import app
        # Verify the global exception handler is registered
        assert Exception in app.exception_handlers
