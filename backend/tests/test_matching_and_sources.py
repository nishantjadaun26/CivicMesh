"""Tests for incident matching logic and anti-SSRF official source security."""

from uuid import uuid4

import pytest
from backend.app.core.errors import ValidationError
from backend.app.database.models import Incident
from backend.app.schemas.common import ConfirmedLocation
from backend.app.services.matching.incident_matcher import (
    IncidentMatcher,
    haversine_distance_meters,
)
from backend.app.services.routing.official_sources import is_safe_ip, validate_url_safe
from sqlalchemy.ext.asyncio import AsyncSession


def test_haversine_distance():
    # Known distance: New Delhi (28.6139, 77.2090) to nearby point ~100m away
    dist = haversine_distance_meters(28.6139, 77.2090, 28.6148, 77.2090)
    assert 90 <= dist <= 110


@pytest.mark.asyncio
async def test_incident_matcher_radius_and_category(db_session: AsyncSession):
    matcher = IncidentMatcher(max_distance_meters=300.0)
    report_id = uuid4()
    owner_id = uuid4()

    loc = ConfirmedLocation(latitude=28.6139, longitude=77.2090, confirmed=True)

    # 1. Nearby incident (same category, ~100m)
    inc_near = Incident(
        id=uuid4(),
        category="garbage",
        latitude=28.6148,
        longitude=77.2090,
        observed_condition="Garbage pile near roadside",
        authority_status="unknown",
        is_public=True,
    )
    # 2. Far incident (same category, ~2km)
    inc_far = Incident(
        id=uuid4(),
        category="garbage",
        latitude=28.6300,
        longitude=77.2090,
        observed_condition="Far away garbage",
        authority_status="unknown",
        is_public=True,
    )
    # 3. Nearby incident (different category, ~50m)
    inc_diff_cat = Incident(
        id=uuid4(),
        category="water_leak",
        latitude=28.6142,
        longitude=77.2090,
        observed_condition="Water leak",
        authority_status="unknown",
        is_public=True,
    )
    db_session.add_all([inc_near, inc_far, inc_diff_cat])
    await db_session.commit()

    candidates = await matcher.find_candidates(
        report_id=report_id,
        owner_id=owner_id,
        category="garbage",
        location=loc,
        db=db_session,
    )

    # Only inc_near should match
    assert len(candidates) == 1
    assert candidates[0].incident_id == inc_near.id
    assert candidates[0].category == "garbage"
    assert candidates[0].distance_meters is not None
    assert candidates[0].distance_meters < 300.0


def test_anti_ssrf_ip_blocking():
    # Private / loopback IPs must be blocked
    assert is_safe_ip("127.0.0.1") is False
    assert is_safe_ip("10.0.0.1") is False
    assert is_safe_ip("192.168.1.1") is False
    assert is_safe_ip("169.254.169.254") is False
    assert is_safe_ip("::1") is False
    assert is_safe_ip("0.0.0.0") is False

    # Public IPs must be allowed
    assert is_safe_ip("8.8.8.8") is True
    assert is_safe_ip("1.1.1.1") is True


def test_anti_ssrf_url_validation():
    # Disallowed schemes
    with pytest.raises(ValidationError, match="Invalid URL scheme"):
        validate_url_safe("ftp://example.com/doc.pdf")

    with pytest.raises(ValidationError, match="Invalid URL scheme"):
        validate_url_safe("file:///etc/passwd")

    # Localhost / private hosts
    with pytest.raises(ValidationError, match="resolves to restricted IP"):
        validate_url_safe("http://127.0.0.1:8000/internal")

    with pytest.raises(ValidationError, match="resolves to restricted IP"):
        validate_url_safe("http://169.254.169.254/latest/meta-data")
