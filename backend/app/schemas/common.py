"""Common shared schemas, value objects and constraints."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Category = Literal["garbage", "water_leak"]

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
ReportText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]
OptionalReportText = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10000)]


class BaseSchema(BaseModel):
    model_config = ConfigDict(
        from_attributes=True,
        extra="forbid",
        revalidate_instances="always",
    )


class ConfirmedLocation(BaseSchema):
    """Explicit coordinate values confirmed by citizen."""
    latitude: float = Field(ge=-90.0, le=90.0, allow_inf_nan=False, description="WGS84 latitude")
    longitude: float = Field(ge=-180.0, le=180.0, allow_inf_nan=False, description="WGS84 longitude")
    confirmed: Literal[True] = Field(description="Explicit manual confirmation flag")


class PaginationParams(BaseSchema):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)


class PaginationMeta(BaseSchema):
    page: int
    limit: int
    total: int
    has_more: bool
