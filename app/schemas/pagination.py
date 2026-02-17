from typing import TypeVar, Generic, List
from pydantic import BaseModel
from fastapi import Query

T = TypeVar("T")


class PaginationParams:
    """Inject as Depends(PaginationParams) into endpoints."""
    def __init__(
        self,
        offset: int = Query(0, ge=0, description="Number of records to skip"),
        limit: int = Query(50, ge=1, le=500, description="Max records to return"),
    ):
        self.offset = offset
        self.limit = limit


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    offset: int
    limit: int
