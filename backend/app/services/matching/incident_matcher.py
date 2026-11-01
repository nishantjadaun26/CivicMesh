"""Incident candidate matching service based on location, category, and temporal proximity."""

import math
from datetime import datetime, timedelta, timezone
from uuid import UUID

from backend.app.database.models import Incident, IncidentReport
from backend.app.schemas.common import Category, ConfirmedLocation
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points in meters on the WGS84 sphere."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


class IncidentCandidateItem:
    def __init__(self, incident_id: UUID, category: str, reason: str, distance_meters: float | None = None):
        self.incident_id = incident_id
        self.category = category
        self.reason = reason
        self.distance_meters = distance_meters

    def to_dict(self) -> dict:
        return {
            "incident_id": str(self.incident_id),
            "category": self.category,
            "reason": self.reason,
            "distance_meters": round(self.distance_meters, 1) if self.distance_meters is not None else None,
        }


class IncidentMatcher:
    """Find candidate existing incidents for a new citizen report."""

    def __init__(self, max_distance_meters: float = 300.0, max_age_days: int = 14):
        self.max_distance_meters = max_distance_meters
        self.max_age_days = max_age_days

    async def find_candidates(
        self,
        *,
        report_id: UUID,
        owner_id: UUID,
        category: Category,
        location: ConfirmedLocation,
        db: AsyncSession,
        limit: int = 20,
    ) -> list[IncidentCandidateItem]:
        """Search incidents matching category and within radius, sorted by distance."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.max_age_days)

        # Query active incidents of the same category created within recent cutoff
        stmt = (
            select(Incident)
            .where(Incident.category == category)
            .where(Incident.is_public.is_(True))
            .where(Incident.created_at >= cutoff)
        )
        result = await db.execute(stmt)
        incidents = result.scalars().all()

        candidates: list[IncidentCandidateItem] = []
        for inc in incidents:
            dist = haversine_distance_meters(
                location.latitude,
                location.longitude,
                inc.latitude,
                inc.longitude,
            )
            if dist <= self.max_distance_meters:
                reason = f"Same category '{category}' observed {round(dist)}m away within last {self.max_age_days} days"
                candidates.append(
                    IncidentCandidateItem(
                        incident_id=inc.id,
                        category=inc.category,
                        reason=reason,
                        distance_meters=dist,
                    )
                )

        # Sort closest first
        candidates.sort(key=lambda c: c.distance_meters if c.distance_meters is not None else float("inf"))
        return candidates[:limit]

    @staticmethod
    async def record_membership(
        *,
        incident_id: UUID,
        report_id: UUID,
        similarity_score: float | None,
        db: AsyncSession,
    ) -> IncidentReport:
        """Create a reversible association between a report and an incident."""
        assoc = IncidentReport(
            incident_id=incident_id,
            report_id=report_id,
            similarity_score=similarity_score,
            is_active=True,
        )
        db.add(assoc)
        await db.commit()
        return assoc
