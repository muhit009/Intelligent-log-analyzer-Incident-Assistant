from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime

from app.db.base import Base

class LogFile(Base):
    __tablename__ = "log_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    stored_path: Mapped[str] = mapped_column(String(1024), nullable=False)

    source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    environment: Mapped[str | None] = mapped_column(String(50), nullable=True)
    log_type: Mapped[str | None] = mapped_column(String(50), nullable=True)

    status: Mapped[str] = mapped_column(String(30), nullable=False, default="uploaded")

    total_lines: Mapped[int | None] = mapped_column(Integer, nullable=True)
    parsed_lines: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failed_lines: Mapped[int | None] = mapped_column(Integer, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    uploaded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
