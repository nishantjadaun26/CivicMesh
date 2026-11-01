"""CivicMesh FastAPI Application."""

import logging
import uuid

from backend.app.api.routes.health import router as health_router
from backend.app.api.routes.incidents import router as incidents_router
from backend.app.api.routes.jobs import router as jobs_router
from backend.app.api.routes.reports import router as reports_router
from backend.app.api.routes.uploads import router as uploads_router
from backend.app.core.config import get_settings
from backend.app.core.errors import AppError, ErrorResponse
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

logger = logging.getLogger("civicmesh.api")
settings = get_settings()

app = FastAPI(
    title="CivicMesh API",
    description="Backend APIs for citizen reporting, incident matching, and AI verification workflows.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach unique request_id to each HTTP request and response header."""
    request_id = request.headers.get("X-Request-ID", f"req-{uuid.uuid4().hex[:12]}")
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response


# -----------------------------------------------------------------------------
# Global Error Handlers
# -----------------------------------------------------------------------------
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=exc.code,
            message=exc.message,
            request_id=request_id,
            details=exc.details,
        ).model_dump(),
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", "unknown")
    errors = []
    for err in exc.errors():
        loc = " -> ".join(str(loc_part) for loc_part in err.get("loc", []))
        errors.append(f"{loc}: {err.get('msg')}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=ErrorResponse(
            code="validation_error",
            message="Request schema validation failed",
            request_id=request_id,
            details={"errors": errors},
        ).model_dump(),
    )


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException):
    request_id = getattr(request.state, "request_id", "unknown")
    code = "http_error"
    if exc.status_code == 401:
        code = "unauthorized"
    elif exc.status_code == 403:
        code = "forbidden"
    elif exc.status_code == 404:
        code = "not_found"
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            code=code,
            message=str(exc.detail),
            request_id=request_id,
        ).model_dump(),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", "unknown")
    logger.exception("Unhandled server error [request_id=%s]: %s", request_id, exc)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            code="internal_server_error",
            message="An unexpected error occurred. Please try again later.",
            request_id=request_id,
        ).model_dump(),
    )


# -----------------------------------------------------------------------------
# Routers Registration
# -----------------------------------------------------------------------------
app.include_router(health_router)
app.include_router(uploads_router)
app.include_router(reports_router)
app.include_router(jobs_router)
app.include_router(incidents_router)


# -----------------------------------------------------------------------------
# Custom OpenAPI with Standardized ErrorResponse
# -----------------------------------------------------------------------------
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    components = openapi_schema.setdefault("components", {}).setdefault("schemas", {})
    components["ErrorResponse"] = ErrorResponse.model_json_schema()
    components.pop("HTTPValidationError", None)
    components.pop("ValidationError", None)

    error_ref = {"application/json": {"schema": {"$ref": "#/components/schemas/ErrorResponse"}}}

    for path, path_item in openapi_schema.get("paths", {}).items():
        for method, op in path_item.items():
            if not isinstance(op, dict) or "responses" not in op:
                continue

            params = op.get("parameters", [])
            has_auth = any(p.get("name") == "authorization" for p in params)
            has_id = "{" in path

            if has_auth:
                op["responses"]["401"] = {"description": "Unauthorized", "content": error_ref}
                op["responses"]["403"] = {"description": "Forbidden", "content": error_ref}
            if has_id:
                op["responses"]["404"] = {"description": "Not Found", "content": error_ref}
            if "answers" in path or op.get("operationId", "").startswith("create_"):
                op["responses"]["409"] = {"description": "Conflict with current state", "content": error_ref}
            if "422" in op["responses"]:
                op["responses"]["422"] = {"description": "Validation Error", "content": error_ref}

    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi
