from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel


class AnomalyResponse(BaseModel):
    id: int
    window_start: datetime
    window_end: datetime
    score: float
    features: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
    pipeline_run_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ErrorClusterResponse(BaseModel):
    id: int
    label: int
    example_message: str
    count: int
    keywords: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    pipeline_run_id: Optional[int] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PipelineRunResponse(BaseModel):
    id: int
    trigger: str
    status: str
    anomalies_detected: Optional[int] = None
    clusters_created: Optional[int] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None

    model_config = {"from_attributes": True}
