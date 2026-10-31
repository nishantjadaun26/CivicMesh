"""BackendTools and WorkflowLocks adapters for LangGraph AI workflow integration."""

import asyncio
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from backend.app.database.models import Evidence
from backend.app.schemas.common import Category, ConfirmedLocation
from backend.app.services.matching.incident_matcher import IncidentMatcher
from backend.app.services.routing.official_sources import OfficialSourceService
from sqlalchemy.ext.asyncio import AsyncSession


class BackendToolsAdapter:
    """Implements the BackendTools protocol expected by civicmesh_ai."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.matcher = IncidentMatcher()

    async def load_evidence(
        self,
        *,
        owner_id: UUID,
        report_id: UUID | None,
        incident_id: UUID | None,
        evidence_ids: list[UUID],
    ) -> list[Any]:
        """Read only validated private media evidence owned by the citizen."""
        from sqlalchemy import select
        stmt = select(Evidence).where(
            Evidence.id.in_(evidence_ids),
            Evidence.owner_id == owner_id,
        )
        res = await self.db.execute(stmt)
        items = res.scalars().all()

        media_items = []
        for item in items:
            media_items.append({
                "id": str(item.id),
                "mime_type": item.mime_type,
                "storage_path": item.storage_path,
                "file_size_bytes": item.file_size_bytes,
            })
        return media_items

    async def incident_candidates(
        self,
        *,
        report_id: UUID,
        owner_id: UUID,
        category: Category,
        location: ConfirmedLocation,
    ) -> list[Any]:
        """Suggest up to 20 candidate incidents within spatial/temporal threshold."""
        candidates = await self.matcher.find_candidates(
            report_id=report_id,
            owner_id=owner_id,
            category=category,
            location=location,
            db=self.db,
        )
        return [c.to_dict() for c in candidates]

    async def authority_sources(
        self,
        *,
        report_id: UUID,
        owner_id: UUID,
        category: Category,
        location: ConfirmedLocation,
    ) -> list[Any]:
        """Return verified official authority passages."""
        sources = await OfficialSourceService.get_authority_sources(
            report_id=report_id,
            owner_id=owner_id,
            category=category,
            location=location,
            db=self.db,
        )
        return [s.to_dict() for s in sources]


class InProcessWorkflowLocks:
    """Thread/coroutine lock adapter for safe workflow serialization."""

    def __init__(self):
        self._locks: dict[UUID, asyncio.Lock] = {}
        self._guard = asyncio.Lock()

    @asynccontextmanager
    async def hold(self, workflow_id: UUID):
        async with self._guard:
            if workflow_id not in self._locks:
                self._locks[workflow_id] = asyncio.Lock()
            lock = self._locks[workflow_id]

        async with lock:
            try:
                yield
            finally:
                pass
