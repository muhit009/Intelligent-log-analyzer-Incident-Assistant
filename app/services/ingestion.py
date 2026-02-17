import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.models.log_file import LogFile
from app.models.log_entry import LogEntry
from app.services.parsers import parse_line

logger = logging.getLogger(__name__)
BATCH_SIZE = 2000

def process_log_file(db: Session, log_file_id: int) -> None:
    logger.info("Ingestion started for log_file_id=%d", log_file_id)
    lf = db.get(LogFile, log_file_id)
    logger.debug("LogFile record: %s, path=%s", lf, getattr(lf, "stored_path", None))
    if not lf:
        return

    lf.status = "processing"
    lf.error = None
    db.commit()

    total = 0
    parsed = 0
    failed = 0
    batch: list[LogEntry] = []

    try:
        path = Path(lf.stored_path)
    # If stored_path is relative, resolve it from project root (best effort)
        if not path.is_absolute():
            path = (Path.cwd() / path).resolve()
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            for line_number, raw_line in enumerate(f, start=1):
                total += 1
                d = parse_line(raw_line)

                status = d.get("parse_status", "failed")
                if status == "failed":
                    failed += 1
                else:
                    parsed += 1

                batch.append(
                    LogEntry(
                        log_file_id=lf.id,
                        line_number=line_number,
                        timestamp=d.get("timestamp"),
                        level=d.get("level"),
                        service=d.get("service"),
                        message=d.get("message"),
                        raw_line=d.get("raw_line") or raw_line.rstrip("\n"),
                        parse_status=status,
                        parse_error=d.get("parse_error"),
                        parse_confidence=d.get("parse_confidence"),
                        parser_name=d.get("parser_name"),
                    )
                )

                if len(batch) >= BATCH_SIZE:
                    db.add_all(batch)
                    db.commit()
                    batch.clear()
        logger.info("Ingestion complete for path=%s", path)

        if batch:
            db.add_all(batch)
            db.commit()

        lf.total_lines = total
        lf.parsed_lines = parsed
        lf.failed_lines = failed
        lf.status = "processed"
        lf.processed_at = datetime.utcnow()
        db.commit()

    except Exception as e:
        lf.status = "failed"
        lf.error = str(e)
        lf.processed_at = datetime.utcnow()
        db.commit()
        raise
