from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class ErrorCluster(Base):
    __tablename__ = "error_clusters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    label: Mapped[int] = mapped_column(Integer, nullable=False)
    example_message: Mapped[str] = mapped_column(Text, nullable=False)
    count: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    keywords: Mapped[str | None] = mapped_column(String(500), nullable=True)

    first_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    pipeline_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
