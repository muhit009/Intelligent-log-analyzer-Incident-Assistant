from datetime import datetime
from sqlalchemy import Integer, DateTime, Text, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base


class Anomaly(Base):
    __tablename__ = "anomalies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    window_start: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    window_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    score: Mapped[float] = mapped_column(Float, nullable=False, index=True)

    features: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    pipeline_run_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
