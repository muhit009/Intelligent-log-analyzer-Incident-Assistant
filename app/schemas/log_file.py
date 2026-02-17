from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class LogFileResponse(BaseModel):
    id: int
    filename: str
    source: Optional[str] = None
    environment: Optional[str] = None
    log_type: Optional[str] = None
    status: str
    total_lines: Optional[int] = None
    parsed_lines: Optional[int] = None
    failed_lines: Optional[int] = None
    error: Optional[str] = None
    uploaded_at: datetime
    processed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
