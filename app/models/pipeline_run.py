from datetime import datetime
from sqlalchemy import Integer, String, DateTime, Text, Float
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class PipelineRun(Base):
    __tablename__ = "pipeline_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    trigger: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")

    anomalies_detected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    clusters_created: Mapped[int | None] = mapped_column(Integer, nullable=True)

    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
