from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel
from math import ceil

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    page_size: int
    total_pages: int
    has_next: bool
    has_prev: bool


class ErrorResponse(BaseModel):
    detail: str
    code: Optional[str] = None
    field: Optional[str] = None


class SuccessResponse(BaseModel):
    message: str
    data: Optional[Any] = None


def paginate(items: List[Any], total: int, page: int, page_size: int) -> PaginatedResponse:
    total_pages = ceil(total / page_size) if page_size > 0 else 0
    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        has_next=page < total_pages,
        has_prev=page > 1,
    )


def build_skip_limit(page: int, page_size: int) -> tuple[int, int]:
    page = max(1, page)
    page_size = min(max(1, page_size), 200)
    skip = (page - 1) * page_size
    return skip, page_size
