import pytest
from civicmesh_ai.schemas import (
    Clarification,
    ConfirmedLocation,
    Extraction,
    ExtractionRequest,
    ReviewDecision,
)
from pydantic import ValidationError


def test_unknown_fields_remain_unknown():
    """Verify unknown fields remain unknown."""
    extraction = Extraction()
    assert extraction.category is None
    assert extraction.summary is None
    assert extraction.location_description is None


@pytest.mark.parametrize(
    "extra",
    [
        {"authority_status": "resolved"},
        {"latitude": 12},
        {"owner_id": "untrusted"},
        {"receipt": "invented"},
        {"category": "road_damage"},
    ],
)
def test_model_cannot_emit_trusted_fields(extra):
    """Verify model cannot emit trusted fields."""
    with pytest.raises(ValidationError):
        Extraction.model_validate(extra)


@pytest.mark.parametrize(
    "latitude,longitude,confirmed",
    [
        (91, 0, True),
        (0, -181, True),
        (float("nan"), 0, True),
        (0, 0, False),
    ],
)
def test_location_bounds_and_confirmation(latitude, longitude, confirmed):
    """Verify location bounds and confirmation."""
    with pytest.raises(ValidationError):
        ConfirmedLocation(latitude=latitude, longitude=longitude, confirmed=confirmed)


def test_review_requires_boolean_and_answers_require_content():
    """Verify review requires boolean and answers require content."""
    with pytest.raises(ValidationError):
        ReviewDecision(approved="true")
    with pytest.raises(ValidationError):
        Clarification()


def test_input_and_history_are_bounded():
    """Verify input and history are bounded."""
    for text in ["  ", "x" * 10001]:
        with pytest.raises(ValidationError):
            ExtractionRequest(text=text)
    with pytest.raises(ValidationError):
        ExtractionRequest(text="Report", clarifications=[Clarification(text="Answer")] * 4)
