from typing import List
from pydantic import BaseModel


class LevelBreakdown(BaseModel):
    level: str
    count: int


class TopService(BaseModel):
    service: str
    count: int


class StatsSummaryResponse(BaseModel):
    total_entries: int
    total_files: int
    level_breakdown: List[LevelBreakdown]
    top_services: List[TopService]
