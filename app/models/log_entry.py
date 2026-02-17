from datetime import datetime
from sqlalchemy import (
    Integer, String, DateTime, ForeignKey, Text, Float,
    Index, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base

class LogEntry(Base):
    __tablename__ = "log_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    log_file_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("log_files.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    line_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Parsed fields (nullable)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    level: Mapped[str | None] = mapped_column(String(16), nullable=True, index=True)
    service: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Always store raw line
    raw_line: Mapped[str] = mapped_column(Text, nullable=False)

    # Parsing metadata
    parse_status: Mapped[str] = mapped_column(String(16), nullable=False, default="failed", index=True)
    parse_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    parse_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    parser_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("log_file_id", "line_number", name="uq_log_entries_file_line"),
        Index("idx_log_entries_ts_level_service", "timestamp", "level", "service"),
    )
