from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.db.session import get_db
from app.models.log_entry import LogEntry
from app.models.log_file import LogFile
from app.schemas.stats import StatsSummaryResponse, LevelBreakdown, TopService
from app.core.dependencies import RequireViewer

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/summary", response_model=StatsSummaryResponse, dependencies=[RequireViewer])
def get_stats_summary(db: Session = Depends(get_db)):
    total_entries = db.execute(
        select(func.count(LogEntry.id))
    ).scalar_one()

    total_files = db.execute(
        select(func.count(LogFile.id))
    ).scalar_one()

    level_rows = db.execute(
        select(LogEntry.level, func.count(LogEntry.id))
        .where(LogEntry.level.is_not(None))
        .group_by(LogEntry.level)
        .order_by(func.count(LogEntry.id).desc())
    ).all()
    level_breakdown = [
        LevelBreakdown(level=row[0], count=row[1]) for row in level_rows
    ]

    service_rows = db.execute(
        select(LogEntry.service, func.count(LogEntry.id))
        .where(LogEntry.service.is_not(None))
        .group_by(LogEntry.service)
        .order_by(func.count(LogEntry.id).desc())
        .limit(10)
    ).all()
    top_services = [
        TopService(service=row[0], count=row[1]) for row in service_rows
    ]

    return StatsSummaryResponse(
        total_entries=total_entries,
        total_files=total_files,
        level_breakdown=level_breakdown,
        top_services=top_services,
    )
