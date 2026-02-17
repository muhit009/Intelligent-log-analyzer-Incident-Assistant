"""Analytics logic tests with mocking for SQLite compatibility."""
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from app.services.analytics import (
    _generate_anomaly_description,
    _detect_anomalies,
    _cluster_errors,
    run_analytics,
    MIN_SAMPLES_FOR_ANOMALY,
)
from app.models.pipeline_run import PipelineRun
from app.models.anomaly import Anomaly


class TestGenerateAnomalyDescription:
    def test_basic(self):
        feat = {
            "total_count": 100,
            "error_count": 10,
            "error_rate": 0.1,
            "unique_services": 3,
            "warn_count": 5,
        }
        desc = _generate_anomaly_description(feat)
        assert "100 events" in desc
        assert "10.0% error rate" in desc
        assert "10 errors" in desc
        assert "3 services" in desc

    def test_zero_errors(self):
        feat = {
            "total_count": 50,
            "error_count": 0,
            "error_rate": 0.0,
            "unique_services": 1,
            "warn_count": 0,
        }
        desc = _generate_anomaly_description(feat)
        assert "50 events" in desc
        assert "error rate" not in desc
        assert "errors" not in desc


class TestDetectAnomalies:
    def test_too_few_windows(self, db_session):
        """When there are fewer windows than MIN_SAMPLES_FOR_ANOMALY, skip."""
        run = PipelineRun(trigger="test", status="running", started_at=datetime.utcnow())
        db_session.add(run)
        db_session.flush()

        features = [
            {
                "window_start": datetime(2025, 1, 1, i, 0),
                "window_end": datetime(2025, 1, 1, i, 2),
                "total_count": 10,
                "error_count": 1,
                "error_rate": 0.1,
                "unique_services": 2,
                "warn_count": 0,
            }
            for i in range(MIN_SAMPLES_FOR_ANOMALY - 1)
        ]

        count = _detect_anomalies(db_session, features, pipeline_run_id=run.id)
        assert count == 0

    def test_outlier_detection(self, db_session):
        """20 normal windows + 1 outlier should produce at least 1 anomaly."""
        run = PipelineRun(trigger="test", status="running", started_at=datetime.utcnow())
        db_session.add(run)
        db_session.flush()

        base_time = datetime(2025, 6, 15, 10, 0, 0)
        features = []
        for i in range(20):
            features.append({
                "window_start": base_time + timedelta(minutes=i * 2),
                "window_end": base_time + timedelta(minutes=i * 2 + 2),
                "total_count": 10,
                "error_count": 1,
                "error_rate": 0.1,
                "unique_services": 2,
                "warn_count": 1,
            })

        # Add one extreme outlier
        features.append({
            "window_start": base_time + timedelta(minutes=40),
            "window_end": base_time + timedelta(minutes=42),
            "total_count": 1000,
            "error_count": 500,
            "error_rate": 0.5,
            "unique_services": 15,
            "warn_count": 100,
        })

        count = _detect_anomalies(db_session, features, pipeline_run_id=run.id)
        assert count >= 1

        anomalies = db_session.query(Anomaly).all()
        assert len(anomalies) >= 1


class TestClusterErrors:
    def test_too_few_errors(self, db_session):
        """When there are fewer errors than MIN_ERRORS, skip."""
        run = PipelineRun(trigger="test", status="running", started_at=datetime.utcnow())
        db_session.add(run)
        db_session.flush()

        count = _cluster_errors(db_session, pipeline_run_id=run.id)
        assert count == 0


class TestRunAnalytics:
    @patch("app.services.analytics._cluster_errors")
    @patch("app.services.analytics._extract_window_features")
    def test_completed_status(self, mock_features, mock_clusters, db_session):
        """Mocking DB-dependent functions to verify run_analytics flow."""
        mock_features.return_value = []  # no features -> anomaly detection skipped
        mock_clusters.return_value = 0

        result = run_analytics(db_session, trigger="test")
        assert result.status == "completed"
        assert result.anomalies_detected == 0
        assert result.clusters_created == 0
        assert result.duration_seconds is not None

    @patch("app.services.analytics._cluster_errors")
    @patch("app.services.analytics._extract_window_features")
    def test_failed_status(self, mock_features, mock_clusters, db_session):
        """Verify that exceptions result in 'failed' status."""
        mock_features.side_effect = RuntimeError("DB exploded")

        result = run_analytics(db_session, trigger="test")
        assert result.status == "failed"
        assert "DB exploded" in result.error
