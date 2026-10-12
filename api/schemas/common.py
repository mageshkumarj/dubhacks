from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ErrorBody(BaseModel):
    code: str
    message: str


class Envelope(BaseModel, Generic[T]):
    """Every response uses this shape: success flag, data (null on error), error (null on success)."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    data: T | None
    error: ErrorBody | None
    meta: dict[str, Any]
    data_source: str
