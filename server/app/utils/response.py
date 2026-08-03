"""统一响应格式"""

from typing import Any, Optional
from fastapi.responses import JSONResponse


def success(data: Any = None, message: str = "success") -> dict:
    return {"code": 0, "message": message, "data": data}


def error(message: str = "error", code: int = -1, data: Any = None) -> dict:
    return {"code": code, "message": message, "data": data}


def error_response(message: str = "error", code: int = -1, status_code: int = 400, data: Any = None):
    return JSONResponse(
        status_code=status_code,
        content={"code": code, "message": message, "data": data},
    )
