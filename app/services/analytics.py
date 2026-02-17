import logging
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans

from sqlalchemy.orm import Session
from sqlalchemy import select, func, case, delete

from app.models.log_entry import LogEntry
from app.models.anomaly import Anomaly
from app.models.error_cluster import ErrorCluster
from app.models.pipeline_run import PipelineRun

logger = logging.getLogger(__name__)

WINDOW_MINUTES = 2
MAX_CLUSTERS = 20
MIN_SAMPLES_FOR_ANOMALY = 5
MIN_ERRORS_FOR_CLUSTERING = 2
ISOLATION_FOREST_CONTAMINATION = 0.1


def _extract_window_features(
    db: Session,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> list[dict]:
    if end is None:
        end = datetime.utcnow()
    if start is None:
        start = end - timedelta(hours=24)

    bucket_seconds = WINDOW_MINUTES * 60

    # Bucket timestamps into 2-minute windows using epoch math
    bucket_expr = func.to_timestamp(
        func.floor(func.extract("epoch", LogEntry.timestamp) / bucket_seconds)
        * bucket_seconds
    )

    query = (
        select(
            bucket_expr.label("window_start"),
            func.count(LogEntry.id).label("total_count"),
            func.sum(case((LogEntry.level == "ERROR", 1), else_=0)).label("error_count"),
            func.sum(case((LogEntry.level.in_(["WARN", "WARNING"]), 1), else_=0)).label("warn_count"),
            func.sum(case((LogEntry.level == "INFO", 1), else_=0)).label("info_count"),
            func.sum(case((LogEntry.level == "DEBUG", 1), else_=0)).label("debug_count"),
            func.count(func.distinct(LogEntry.service)).label("unique_services"),
        )
        .where(LogEntry.timestamp.is_not(None))
        .where(LogEntry.timestamp >= start)
        .where(LogEntry.timestamp <= end)
        .group_by(bucket_expr)
        .order_by(bucket_expr)
    )

    rows = db.execute(query).all()

    features = []
    for row in rows:
        ws = row.window_start
        if hasattr(ws, "replace") and ws.tzinfo is not None:
            ws = ws.replace(tzinfo=None)
        we = ws + timedelta(minutes=WINDOW_MINUTES)
        total = row.total_count or 0
        error = int(row.error_count or 0)
        warn = int(row.warn_count or 0)
        info = int(row.info_count or 0)
        debug = int(row.debug_count or 0)

        features.append({
            "window_start": ws,
            "window_end": we,
            "total_count": total,
            "error_count": error,
            "warn_count": warn,
            "info_count": info,
            "debug_count": debug,
            "error_rate": round(error / total, 4) if total > 0 else 0.0,
            "unique_services": row.unique_services or 0,
        })

    return features


def _generate_anomaly_description(feat: dict) -> str:
    parts = [f"{feat['total_count']} events in window"]
    if feat["error_rate"] > 0:
        parts.append(f"{feat['error_rate'] * 100:.1f}% error rate")
    if feat["error_count"] > 0:
        parts.append(f"{feat['error_count']} errors")
    parts.append(f"{feat['unique_services']} services")
    return "Anomalous window: " + ", ".join(parts)


def _detect_anomalies(
    db: Session,
    features: list[dict],
    pipeline_run_id: int,
) -> int:
    if len(features) < MIN_SAMPLES_FOR_ANOMALY:
        logger.info(
            "Skipping anomaly detection: only %d windows (need >= %d)",
            len(features), MIN_SAMPLES_FOR_ANOMALY,
        )
        return 0

    feature_keys = ["total_count", "error_count", "error_rate", "unique_services", "warn_count"]
    X = np.array([[f[k] for k in feature_keys] for f in features], dtype=np.float64)

    clf = IsolationForest(
        contamination=ISOLATION_FOREST_CONTAMINATION,
        random_state=42,
        n_estimators=100,
    )
    clf.fit(X)

    predictions = clf.predict(X)
    scores = clf.decision_function(X)

    # Delete old anomalies in this time range
    if features:
        range_start = features[0]["window_start"]
        range_end = features[-1]["window_end"]
        db.execute(
            delete(Anomaly).where(
                Anomaly.window_start >= range_start,
                Anomaly.window_end <= range_end,
            )
        )

    anomaly_count = 0
    for feat, pred, score in zip(features, predictions, scores):
        if pred == -1:
            anomaly = Anomaly(
                window_start=feat["window_start"],
                window_end=feat["window_end"],
                score=float(score),
                features={k: feat[k] for k in feature_keys},
                description=_generate_anomaly_description(feat),
                pipeline_run_id=pipeline_run_id,
            )
            db.add(anomaly)
            anomaly_count += 1

    db.flush()
    return anomaly_count


def _cluster_errors(
    db: Session,
    pipeline_run_id: int,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> int:
    if end is None:
        end = datetime.utcnow()
    if start is None:
        start = end - timedelta(hours=24)

    query = (
        select(LogEntry.id, LogEntry.message, LogEntry.timestamp)
        .where(LogEntry.timestamp.is_not(None))
        .where(LogEntry.timestamp >= start)
        .where(LogEntry.timestamp <= end)
        .where(
            (LogEntry.level == "ERROR") | (LogEntry.parse_status == "failed")
        )
        .where(LogEntry.message.is_not(None))
        .where(LogEntry.message != "")
    )

    rows = db.execute(query).all()

    if len(rows) < MIN_ERRORS_FOR_CLUSTERING:
        logger.info(
            "Skipping error clustering: only %d error messages (need >= %d)",
            len(rows), MIN_ERRORS_FOR_CLUSTERING,
        )
        return 0

    messages = [row.message for row in rows]
    timestamps = [row.timestamp for row in rows]

    vectorizer = TfidfVectorizer(
        max_features=1000,
        stop_words="english",
        max_df=0.95,
        min_df=1,
    )

    try:
        tfidf_matrix = vectorizer.fit_transform(messages)
    except ValueError:
        logger.warning("TF-IDF produced empty vocabulary; skipping clustering")
        return 0

    n_samples = len(messages)
    n_clusters = min(MAX_CLUSTERS, max(2, n_samples // 5))
    n_clusters = min(n_clusters, n_samples)
    if n_clusters < 2:
        n_clusters = 2

    kmeans = KMeans(
        n_clusters=n_clusters,
        random_state=42,
        n_init=10,
        max_iter=300,
    )
    labels = kmeans.fit_predict(tfidf_matrix)

    feature_names = vectorizer.get_feature_names_out()

    # Delete old clusters in this time range
    db.execute(delete(ErrorCluster))

    cluster_count = 0
    for cluster_label in range(n_clusters):
        indices = [i for i, l in enumerate(labels) if l == cluster_label]
        if not indices:
            continue

        cluster_timestamps = [timestamps[i] for i in indices]

        # Find example: closest to centroid
        centroid = kmeans.cluster_centers_[cluster_label]
        cluster_vectors = tfidf_matrix[indices]
        distances = np.linalg.norm(cluster_vectors.toarray() - centroid, axis=1)
        closest_idx = indices[int(np.argmin(distances))]
        example_message = messages[closest_idx]

        # Top keywords from centroid
        top_indices = centroid.argsort()[-5:][::-1]
        keywords = ", ".join(feature_names[i] for i in top_indices if centroid[i] > 0)

        valid_ts = [t for t in cluster_timestamps if t is not None]
        first_seen = min(valid_ts) if valid_ts else None
        last_seen = max(valid_ts) if valid_ts else None

        error_cluster = ErrorCluster(
            label=cluster_label,
            example_message=example_message[:2000],
            count=len(indices),
            keywords=keywords[:500] if keywords else None,
            first_seen=first_seen,
            last_seen=last_seen,
            pipeline_run_id=pipeline_run_id,
        )
        db.add(error_cluster)
        cluster_count += 1

    db.flush()
    return cluster_count


def run_analytics(
    db: Session,
    trigger: str = "manual",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> PipelineRun:
    run = PipelineRun(
        trigger=trigger,
        status="running",
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.flush()

    try:
        features = _extract_window_features(db, start=start, end=end)
        anomaly_count = _detect_anomalies(db, features, pipeline_run_id=run.id)

        cluster_count = _cluster_errors(db, pipeline_run_id=run.id, start=start, end=end)

        run.status = "completed"
        run.anomalies_detected = anomaly_count
        run.clusters_created = cluster_count
        run.finished_at = datetime.utcnow()
        run.duration_seconds = (run.finished_at - run.started_at).total_seconds()

        db.commit()
        logger.info(
            "Analytics run %d completed: %d anomalies, %d clusters in %.1fs",
            run.id, anomaly_count, cluster_count, run.duration_seconds,
        )

    except Exception as e:
        logger.exception("Analytics run %d failed: %s", run.id, e)
        run.status = "failed"
        run.error = str(e)[:2000]
        run.finished_at = datetime.utcnow()
        run.duration_seconds = (run.finished_at - run.started_at).total_seconds()
        db.commit()

    return run
