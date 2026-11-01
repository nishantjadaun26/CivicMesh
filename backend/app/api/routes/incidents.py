"""Approved public incident listing, detail views, and follow-up submissions."""

from typing import Annotated
from uuid import UUID, uuid4

from backend.app.api.dependencies.auth import get_current_user_id
from backend.app.core.errors import NotFoundError
from backend.app.database.models import Incident, StatusEvent
from backend.app.database.session import get_db
from backend.app.schemas.incidents import (
    FollowUpCreateRequest,
    FollowUpResponse,
    IncidentDetailResponse,
    IncidentPublicResponse,
    StatusEventResponse,
)
from backend.app.services.storage.media import StorageService
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/incidents", tags=["Incidents"])


@router.get(
    "",
    response_model=list[IncidentPublicResponse],
    summary="List approved public incidents",
    description="Returns public projections of verified community incidents. Omits private citizen details.",
)
async def list_public_incidents(
    db: Annotated[AsyncSession, Depends(get_db)],
    category: str | None = Query(default=None, description="Filter by category (garbage, water_leak)"),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[IncidentPublicResponse]:
    """Retrieve approved public incidents for map and listing screens."""
    stmt = select(Incident).where(Incident.is_public == True)  # noqa: E712
    if category:
        stmt = stmt.where(Incident.category == category)
    stmt = stmt.order_by(Incident.created_at.desc()).offset((page - 1) * limit).limit(limit)

    result = await db.execute(stmt)
    incidents = result.scalars().all()

    return [
        IncidentPublicResponse(
            id=inc.id,
            category=inc.category,  # type: ignore
            latitude=inc.latitude,
            longitude=inc.longitude,
            observed_condition=inc.observed_condition,
            authority_status=inc.authority_status,
            is_public=inc.is_public,
            created_at=inc.created_at,
            updated_at=inc.updated_at,
        )
        for inc in incidents
    ]


@router.get(
    "/{incident_id}",
    response_model=IncidentDetailResponse,
    summary="Retrieve approved incident details and verified timeline",
)
async def get_incident_detail(
    incident_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> IncidentDetailResponse:
    """Read public incident details and auditable timeline."""
    stmt = select(Incident).where(Incident.id == incident_id, Incident.is_public == True)  # noqa: E712
    res = await db.execute(stmt)
    inc = res.scalar_one_or_none()
    if not inc:
        raise NotFoundError("Public incident not found")

    events_stmt = (
        select(StatusEvent)
        .where(StatusEvent.incident_id == incident_id)
        .order_by(StatusEvent.created_at.asc())
    )
    events_res = await db.execute(events_stmt)
    events = events_res.scalars().all()

    APPROVED_EVENT_TYPES = {"citizen_observation", "ai_assessment", "authority_update"}

    timeline = []
    for ev in events:
        if ev.event_type not in APPROVED_EVENT_TYPES:
            continue

        raw = ev.payload if isinstance(ev.payload, dict) else {}
        sanitized_payload = {}
        if ev.event_type == "citizen_observation":
            if "description" in raw and raw["description"]:
                sanitized_payload["description"] = raw["description"]
            if "same_location_confirmed" in raw:
                sanitized_payload["same_location_confirmed"] = bool(raw["same_location_confirmed"])
        elif ev.event_type == "ai_assessment":
            for key in ["outcome", "rationale", "condition"]:
                if key in raw:
                    sanitized_payload[key] = raw[key]
        elif ev.event_type == "authority_update":
            for key in ["official_status", "authority_name", "update_summary"]:
                if key in raw:
                    sanitized_payload[key] = raw[key]

        timeline.append(
            StatusEventResponse(
                id=ev.id,
                event_type=ev.event_type,
                payload=sanitized_payload,
                created_at=ev.created_at,
            )
        )

    return IncidentDetailResponse(
        id=inc.id,
        category=inc.category,  # type: ignore
        latitude=inc.latitude,
        longitude=inc.longitude,
        observed_condition=inc.observed_condition,
        authority_status=inc.authority_status,
        is_public=inc.is_public,
        created_at=inc.created_at,
        updated_at=inc.updated_at,
        timeline=timeline,
    )


@router.post(
    "/{incident_id}/follow-ups",
    response_model=FollowUpResponse,
    status_code=201,
    summary="Submit citizen follow-up evidence",
)
async def submit_follow_up(
    incident_id: UUID,
    request: FollowUpCreateRequest,
    user_id: Annotated[UUID, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FollowUpResponse:
    """Submit follow-up observation and evidence without altering official authority status."""
    stmt = select(Incident).where(Incident.id == incident_id)
    res = await db.execute(stmt)
    inc = res.scalar_one_or_none()
    if not inc:
        raise NotFoundError("Incident not found")

    # Bind follow-up evidence to this incident
    if request.evidence_ids:
        await StorageService.verify_and_bind_evidence(
            owner_id=user_id,
            evidence_ids=request.evidence_ids,
            db=db,
            incident_id=incident_id,
        )

    follow_up_id = uuid4()
    # Record citizen observation status event (evidence binding & event commit together)
    event = StatusEvent(
        id=follow_up_id,
        incident_id=incident_id,
        event_type="citizen_observation",
        payload={
            "description": request.text,
            "same_location_confirmed": request.same_location_confirmed,
        },
    )
    db.add(event)
    await db.commit()

    return FollowUpResponse(
        id=follow_up_id,
        incident_id=incident_id,
        status="recorded",
        created_at=event.created_at,
    )
