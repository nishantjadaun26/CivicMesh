from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Category = Literal["garbage", "water_leak"]
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
ReportText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)
]
MAX_CLARIFICATION_ROUNDS = 3


class Schema(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ConfirmedLocation(Schema):
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    confirmed: Literal[True]


class Extraction(Schema):
    """Untrusted model observations. No identity, coordinates or authority status fields."""

    category: Category | None = None
    summary: ShortText | None = None
    language: Literal["hi", "en", "mixed", "other"] | None = None
    location_description: ShortText | None = None
    uncertainties: list[ShortText] = Field(default_factory=list, max_length=10)


class ReportInput(Schema):
    report_id: UUID
    text: ReportText
    category: Category | None = None
    location: ConfirmedLocation | None = None


class Clarification(Schema):
    text: Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)] = ""
    category: Category | None = None
    location: ConfirmedLocation | None = None

    @model_validator(mode="after")
    def has_answer(self):
        if not self.text and self.category is None and self.location is None:
            raise ValueError("Provide text, a category or a confirmed location")
        return self


class ExtractionRequest(Schema):
    """Only evidence is sent to the model; report identifiers are deliberately excluded."""

    text: ReportText
    clarifications: list[Clarification] = Field(
        default_factory=list, max_length=MAX_CLARIFICATION_ROUNDS
    )


class ReviewDecision(Schema):
    approved: bool = Field(strict=True)


class ExtractionResult(Schema):
    report_id: UUID
    extraction: Extraction
    category: Category | None
    location: ConfirmedLocation | None
    status: Literal["ready_for_backend", "needs_information", "rejected"]
    missing_fields: list[str]
    authority_status: Literal["unknown"] = "unknown"
