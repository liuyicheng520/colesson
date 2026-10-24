"""Unified API response wrapper."""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

from app.core.error_codes import ErrorCode
from app.core.timeutil import beijing_now_naive

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(default=ErrorCode.SUCCESS, description="业务状态码，0表示成功")
    message: str = Field(default="success", description="响应消息")
    data: T | None = Field(default=None, description="响应数据")
    timestamp: datetime = Field(default_factory=beijing_now_naive, description="响应时间戳(北京时间)")

    @classmethod
    def success(cls, data: T | None = None, message: str = "success") -> "ApiResponse[T]":
        return cls(code=ErrorCode.SUCCESS, message=message, data=data)

    @classmethod
    def fail(cls, code: int, message: str, data: Any = None) -> "ApiResponse[Any]":
        return cls(code=code, message=message, data=data)


class PageData(BaseModel, Generic[T]):
    items: list[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总记录数")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=20, description="每页大小")
    pages: int = Field(default=0, description="总页数")

    @classmethod
    def build(cls, items: list[T], total: int, page: int, page_size: int) -> "PageData[T]":
        pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return cls(items=items, total=total, page=page, page_size=page_size, pages=pages)
