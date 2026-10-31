from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.api.routes.foundation import router
from app.core.config import get_settings
from app.core.errors import ServiceError
from app.schemas.contracts import ErrorResponse


def create_app():
    settings = get_settings()
    errors = {code: {"model": ErrorResponse} for code in (401, 403, 404, 422, 500, 501, 503)}
    app = FastAPI(title="CivicMesh API", version="0.1.0", responses=errors)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        expose_headers=["X-Request-ID"],
    )

    def error(request, status, code, message, details=None):
        request_id = getattr(request.state, "request_id", str(uuid4()))
        return JSONResponse(
            status_code=status,
            content={
                "code": code,
                "message": message,
                "request_id": request_id,
                "details": details,
            },
            headers={"X-Request-ID": request_id},
        )

    @app.middleware("http")
    async def request_id(request: Request, call_next):
        request.state.request_id = str(uuid4())
        try:
            response = await call_next(request)
        except Exception:
            return error(request, 500, "internal_error", "An internal error occurred.")
        response.headers["X-Request-ID"] = request.state.request_id
        return response

    @app.exception_handler(ServiceError)
    async def service_error(request, exc):
        return error(request, exc.status, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        details = [{"field": ".".join(map(str, e["loc"])), "type": e["type"]} for e in exc.errors()]
        return error(request, 422, "validation_error", "Request validation failed.", details)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return error(request, exc.status_code, "http_error", "Request could not be served.")

    app.include_router(router)
    return app


app = create_app()
