from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class LogEntryResponse(BaseModel):
    id: int
    log_file_id: int
    line_number: int
    timestamp: Optional[datetime] = None
    level: Optional[str] = None
    service: Optional[str] = None
    message: Optional[str] = None
    raw_line: str
    parse_status: str
    parse_confidence: Optional[float] = None
    parser_name: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
