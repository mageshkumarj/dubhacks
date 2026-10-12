"""Consistent response envelope used by every endpoint, including errors."""

from typing import Any

SOURCE = "stub"


def ok(data: Any, meta: dict | None = None) -> dict:
    return {"success": True, "data": data, "error": None, "meta": meta or {}, "data_source": SOURCE}


def fail(message: str, code: str) -> dict:
    return {
        "success": False, "data": None, "error": {"code": code, "message": message},
        "meta": {}, "data_source": SOURCE,
    }
