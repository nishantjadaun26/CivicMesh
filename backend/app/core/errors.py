"""Standardized application exceptions and error response models."""

from typing import Any

from pydantic import BaseModel


class ErrorResponse(BaseModel):
    """Consistent error payload across all endpoints."""
    code: str
    message: str
    request_id: str
    details: dict[str, Any] | None = None


class AppError(Exception):
    """Base application exception."""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Authentication required or invalid token", details: dict[str, Any] | None = None):
        super().__init__(code="unauthorized", message=message, status_code=401, details=details)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Access denied for requested resource", details: dict[str, Any] | None = None):
        super().__init__(code="forbidden", message=message, status_code=403, details=details)


class NotFoundError(AppError):
    def __init__(self, message: str = "Requested resource was not found", details: dict[str, Any] | None = None):
        super().__init__(code="not_found", message=message, status_code=404, details=details)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict with current resource state", details: dict[str, Any] | None = None):
        super().__init__(code="conflict", message=message, status_code=409, details=details)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed", details: dict[str, Any] | None = None):
        super().__init__(code="validation_error", message=message, status_code=422, details=details)


class ServiceUnavailableError(AppError):
    def __init__(self, message: str = "Service or configuration is unavailable", details: dict[str, Any] | None = None):
        super().__init__(code="service_unavailable", message=message, status_code=503, details=details)


class RateLimitError(AppError):
    def __init__(self, message: str = "Too many requests", details: dict[str, Any] | None = None):
        super().__init__(code="rate_limit_exceeded", message=message, status_code=429, details=details)
