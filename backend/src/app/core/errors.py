from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    """Доменная ошибка: сервис кидает её, а HTTP-ответ формируется здесь."""

    status_code = 400
    code = "ERROR"

    def __init__(self, detail: str, meta: dict[str, str] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.meta = meta or {}


class NotFound(AppError):
    status_code = 404
    code = "NOT_FOUND"


class Conflict(AppError):
    status_code = 409
    code = "CONFLICT"


class Forbidden(AppError):
    status_code = 403
    code = "FORBIDDEN"


class Unauthorized(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


def _body(code: str, detail: str, meta: dict | None = None) -> dict:
    return {"code": code, "detail": detail, "meta": meta or {}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(
            _body(exc.code, exc.detail, exc.meta), status_code=exc.status_code, headers=headers
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"field": ".".join(str(part) for part in error["loc"][1:]), "message": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            _body("VALIDATION_ERROR", "Некорректные данные запроса", {"errors": errors}),
            status_code=422,
        )
