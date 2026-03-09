"""Common schemas for pagination and error responses."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    offset: int = Field(0, ge=0)
    limit: int = Field(50, ge=1, le=500)


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int


class ErrorResponse(BaseModel):
    detail: str


class CompareReportResponse(BaseModel, Generic[T]):
    items: list[T]
    requested_tickers: list[str]
    unresolved_tickers: list[str] = Field(default_factory=list)
