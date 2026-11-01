"""Isolated fixtures only. No test data is imported by application modules."""

from uuid import UUID

import pytest
from civicmesh_ai.schemas import ConfirmedLocation, ReportInput


@pytest.fixture
def report():
    """Provide isolated fixtures for report verification."""
    return ReportInput(
        report_id=UUID(int=1),
        text="Water is leaking from a pipe.",
        category="water_leak",
        # Test boundary coordinates, not operational or demo location data.
        location=ConfirmedLocation(latitude=0, longitude=0, confirmed=True),
    )
