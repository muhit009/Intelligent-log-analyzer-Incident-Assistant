import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, func

logger = logging.getLogger(__name__)

from app.core.config import settings, ensure_upload_dir
from app.db.session import get_db, SessionLocal
from app.models.log_file import LogFile
from app.models.log_entry import LogEntry
from app.services.ingestion import process_log_file
from app.schemas.log_entry import LogEntryResponse
from app.schemas.log_file import LogFileResponse
from app.schemas.pagination import PaginationParams, PaginatedResponse
from app.core.dependencies import RequireAdmin, RequireViewer

router = APIRouter(prefix="/logs", tags=["logs"])


def validate_extension(filename: str) -> None:
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {sorted(settings.ALLOWED_EXTENSIONS)}"
        )


def run_ingestion(log_file_id: int) -> None:
    logger.info("Background ingestion started for log_file_id=%d", log_file_id)
    db = SessionLocal()
    try:
        process_log_file(db, log_file_id)
    finally:
        db.close()

    # Run analytics in a separate session after ingestion
    db2 = SessionLocal()
    try:
        from app.services.analytics import run_analytics
        run_analytics(db2, trigger="post_ingestion")
    except Exception as e:
        logger.error("Post-ingestion analytics failed: %s", e)
    finally:
        db2.close()


@router.post("/upload", dependencies=[RequireAdmin])
async def upload_log_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    source: str | None = Form(None),
    environment: str | None = Form(None),
    log_type: str | None = Form(None),
    db: Session = Depends(get_db),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename")

    validate_extension(file.filename)

    upload_dir: Path = ensure_upload_dir()
    stored_name = f"{uuid.uuid4().hex}_{file.filename}"
    stored_path = (upload_dir / stored_name).resolve()
    bytes_written = 0
    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024

    try:
        with stored_path.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > max_bytes:
                    raise HTTPException(status_code=413, detail="File too large")
                f.write(chunk)
    except HTTPException:
        if stored_path.exists():
            stored_path.unlink(missing_ok=True)
        raise
    except Exception as e:
        if stored_path.exists():
            stored_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=str(e))

    log_file = LogFile(
        filename=file.filename,
        stored_path=str(stored_path),
        source=source,
        environment=environment,
        log_type=log_type,
        status="uploaded",
    )
    db.add(log_file)
    db.commit()
    db.refresh(log_file)

    background_tasks.add_task(run_ingestion, log_file.id)

    return {
        "log_file_id": log_file.id,
        "status": log_file.status,
    }


@router.get("/files", response_model=PaginatedResponse[LogFileResponse], dependencies=[RequireViewer])
def list_log_files(
    db: Session = Depends(get_db),
    pagination: PaginationParams = Depends(),
    status: Optional[str] = Query(None, description="Filter by processing status"),
):
    query = select(LogFile)
    count_query = select(func.count(LogFile.id))

    if status is not None:
        query = query.where(LogFile.status == status)
        count_query = count_query.where(LogFile.status == status)

    total = db.execute(count_query).scalar_one()

    query = query.order_by(LogFile.uploaded_at.desc())
    query = query.offset(pagination.offset).limit(pagination.limit)
    files = db.execute(query).scalars().all()

    return PaginatedResponse(
        items=files, total=total, offset=pagination.offset, limit=pagination.limit,
    )


@router.get("/files/{file_id}", response_model=LogFileResponse, dependencies=[RequireViewer])
def get_log_file(file_id: int, db: Session = Depends(get_db)):
    lf = db.get(LogFile, file_id)
    if not lf:
        raise HTTPException(status_code=404, detail="Log file not found")
    return lf


@router.get("", response_model=PaginatedResponse[LogEntryResponse], dependencies=[RequireViewer])
def get_log_entries(
    db: Session = Depends(get_db),
    pagination: PaginationParams = Depends(),
    start: Optional[datetime] = Query(None, description="Entries at or after this timestamp"),
    end: Optional[datetime] = Query(None, description="Entries at or before this timestamp"),
    level: Optional[str] = Query(None, description="Log level (e.g. ERROR, INFO)"),
    service: Optional[str] = Query(None, description="Service name"),
    source: Optional[str] = Query(None, description="Log file source"),
    environment: Optional[str] = Query(None, description="Log file environment"),
    keyword: Optional[str] = Query(None, description="Keyword search in message"),
    file_id: Optional[int] = Query(None, description="Specific log file ID"),
):
    query = select(LogEntry)
    count_query = select(func.count(LogEntry.id))

    # JOIN to LogFile only when needed
    if source is not None or environment is not None:
        query = query.join(LogFile, LogEntry.log_file_id == LogFile.id)
        count_query = count_query.join(LogFile, LogEntry.log_file_id == LogFile.id)

    if start is not None:
        query = query.where(LogEntry.timestamp >= start)
        count_query = count_query.where(LogEntry.timestamp >= start)
    if end is not None:
        query = query.where(LogEntry.timestamp <= end)
        count_query = count_query.where(LogEntry.timestamp <= end)
    if level is not None:
        query = query.where(LogEntry.level == level.upper())
        count_query = count_query.where(LogEntry.level == level.upper())
    if service is not None:
        query = query.where(LogEntry.service == service)
        count_query = count_query.where(LogEntry.service == service)
    if source is not None:
        query = query.where(LogFile.source == source)
        count_query = count_query.where(LogFile.source == source)
    if environment is not None:
        query = query.where(LogFile.environment == environment)
        count_query = count_query.where(LogFile.environment == environment)
    if keyword is not None:
        query = query.where(LogEntry.message.ilike(f"%{keyword}%"))
        count_query = count_query.where(LogEntry.message.ilike(f"%{keyword}%"))
    if file_id is not None:
        query = query.where(LogEntry.log_file_id == file_id)
        count_query = count_query.where(LogEntry.log_file_id == file_id)

    total = db.execute(count_query).scalar_one()

    query = query.order_by(LogEntry.timestamp.desc().nulls_last())
    query = query.offset(pagination.offset).limit(pagination.limit)
    entries = db.execute(query).scalars().all()

    return PaginatedResponse(
        items=entries, total=total, offset=pagination.offset, limit=pagination.limit,
    )
