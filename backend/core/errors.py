"""Error shape for every response: {"error": {"code", "message"}}."""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

SELF_APPROVAL_CONSTRAINT = "approval_requests_no_self_approval"

_CODES_BY_STATUS = {
    401: "unauthenticated",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "invalid_state",
    422: "validation_error",
}


class AppError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def unauthenticated(message: str = "Log in first") -> AppError:
    return AppError(401, "unauthenticated", message)


def forbidden(message: str) -> AppError:
    return AppError(403, "forbidden", message)


def self_approval(message: str = "You cannot decide a request you proposed") -> AppError:
    return AppError(403, "self_approval", message)


def not_found(message: str) -> AppError:
    return AppError(404, "not_found", message)


def invalid_state(message: str) -> AppError:
    return AppError(409, "invalid_state", message)


def error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _validation_message(exc: RequestValidationError) -> str:
    # Field locations and pydantic messages only. Submitted values are never echoed back.
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err.get("loc", ()))
        parts.append(f"{loc}: {err.get('msg', 'invalid')}")
    return "; ".join(parts) or "Invalid request"


def _constraint_name(exc: IntegrityError) -> str | None:
    diag = getattr(exc.orig, "diag", None)
    return getattr(diag, "constraint_name", None)


def install(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError) -> JSONResponse:
        return error_response(exc.status, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _CODES_BY_STATUS.get(exc.status_code, "http_error")
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "validation_error", _validation_message(exc))

    @app.exception_handler(IntegrityError)
    async def _integrity_error(_: Request, exc: IntegrityError) -> JSONResponse:
        # Database messages can contain row values, so they are never returned.
        if _constraint_name(exc) == SELF_APPROVAL_CONSTRAINT:
            return error_response(403, "self_approval", "You cannot decide a request you proposed")
        logger.warning("integrity error on constraint %s", _constraint_name(exc))
        return error_response(409, "invalid_state", "The change conflicts with the current state")

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled error: %s", type(exc).__name__)
        return error_response(500, "internal_error", "Internal error")
