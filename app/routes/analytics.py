from datetime import datetime
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.db.session import get_db, SessionLocal
from app.models.anomaly import Anomaly
from app.models.error_cluster import ErrorCluster
from app.schemas.analytics import (
    AnomalyResponse,
    ErrorClusterResponse,
)
from app.schemas.pagination import PaginationParams, PaginatedResponse
from app.services.analytics import run_analytics
from app.core.dependencies import RequireAdmin, RequireViewer

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/anomalies", response_model=PaginatedResponse[AnomalyResponse], dependencies=[RequireViewer])
def list_anomalies(
    db: Session = Depends(get_db),
    pagination: PaginationParams = Depends(),
    start: Optional[datetime] = Query(None, description="Filter anomalies after this time"),
    end: Optional[datetime] = Query(None, description="Filter anomalies before this time"),
):
    query = select(Anomaly)
    count_query = select(func.count(Anomaly.id))

    if start is not None:
        query = query.where(Anomaly.window_start >= start)
        count_query = count_query.where(Anomaly.window_start >= start)
    if end is not None:
        query = query.where(Anomaly.window_end <= end)
        count_query = count_query.where(Anomaly.window_end <= end)

    total = db.execute(count_query).scalar_one()

    query = query.order_by(Anomaly.score.asc())
    query = query.offset(pagination.offset).limit(pagination.limit)
    anomalies = db.execute(query).scalars().all()

    return PaginatedResponse(
        items=anomalies, total=total, offset=pagination.offset, limit=pagination.limit,
    )


@router.get("/clusters", response_model=PaginatedResponse[ErrorClusterResponse], dependencies=[RequireViewer])
def list_clusters(
    db: Session = Depends(get_db),
    pagination: PaginationParams = Depends(),
):
    count_query = select(func.count(ErrorCluster.id))
    total = db.execute(count_query).scalar_one()

    query = (
        select(ErrorCluster)
        .order_by(ErrorCluster.count.desc())
        .offset(pagination.offset)
        .limit(pagination.limit)
    )
    clusters = db.execute(query).scalars().all()

    return PaginatedResponse(
        items=clusters, total=total, offset=pagination.offset, limit=pagination.limit,
    )


def _run_analytics_background(
    trigger: str = "manual",
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> None:
    db = SessionLocal()
    try:
        run_analytics(db, trigger=trigger, start=start, end=end)
    finally:
        db.close()


@router.post("/run", status_code=202, dependencies=[RequireAdmin])
def trigger_analytics(
    background_tasks: BackgroundTasks,
    start: Optional[datetime] = Query(None, description="Analyze entries after this time"),
    end: Optional[datetime] = Query(None, description="Analyze entries before this time"),
):
    background_tasks.add_task(
        _run_analytics_background,
        trigger="manual",
        start=start,
        end=end,
    )
    return {"status": "accepted", "message": "Analytics run has been queued"}
