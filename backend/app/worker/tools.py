"""Authorized database/storage adapters supplied to the AI coordinator."""

from backend.app.core.errors import ForbiddenError, NotFoundError
from backend.app.database.models import Evidence, FollowUp, IncidentReport, Report
from backend.app.services.matching.incident_matcher import IncidentMatcher
from backend.app.services.routing.official_sources import OfficialSourceService
from backend.app.services.storage.media import StorageService
from civicmesh_ai.media import MediaEvidence
from sqlalchemy import select


class BackendToolsAdapter:
    def __init__(self, db, *, follow_up_id=None, settings=None):
        self.db = db
        self.follow_up_id = follow_up_id
        self.settings = settings

    async def load_evidence(self, *, owner_id, report_id, incident_id, evidence_ids):
        if report_id is not None:
            report = await self.db.get(Report, report_id)
            if report is None or report.owner_id != owner_id:
                raise NotFoundError("Report is unavailable")
        elif incident_id is not None and self.follow_up_id is not None:
            follow_up = await self.db.get(FollowUp, self.follow_up_id)
            if (
                follow_up is None
                or follow_up.owner_id != owner_id
                or follow_up.incident_id != incident_id
            ):
                raise NotFoundError("Follow-up is unavailable")
        else:
            raise ForbiddenError("Evidence context is required")
        items = (
            (
                await self.db.execute(
                    select(Evidence).where(
                        Evidence.id.in_(evidence_ids),
                        Evidence.owner_id == owner_id,
                        Evidence.verified.is_(True),
                    )
                )
            )
            .scalars()
            .all()
        )
        if len(items) != len(evidence_ids):
            raise ForbiddenError("Evidence is unavailable in this workflow")
        baseline_reports = set()
        if incident_id:
            baseline_reports = set(
                (
                    await self.db.execute(
                        select(IncidentReport.report_id).where(
                            IncidentReport.incident_id == incident_id,
                            IncidentReport.is_active.is_(True),
                        )
                    )
                ).scalars()
            )
        result = []
        for item in items:
            allowed = (report_id is not None and item.report_id == report_id) or (
                incident_id is not None
                and (item.follow_up_id == self.follow_up_id or item.report_id in baseline_reports)
            )
            if not allowed:
                raise ForbiddenError("Evidence does not belong to this workflow")
            content = await StorageService.verify_uploaded_object(item)
            result.append(
                MediaEvidence(evidence_id=item.id, mime_type=item.mime_type, content=content)
            )
        return result

    async def _authorize_report(self, report_id, owner_id):
        report = await self.db.get(Report, report_id)
        if report is None or report.owner_id != owner_id:
            raise NotFoundError("Report is unavailable")

    async def incident_candidates(self, *, report_id, owner_id, category, location):
        await self._authorize_report(report_id, owner_id)
        items = await IncidentMatcher().find_candidates(
            report_id=report_id, owner_id=owner_id, category=category, location=location, db=self.db
        )
        return [item.to_dict() for item in items]

    async def authority_sources(self, *, report_id, owner_id, category, location):
        await self._authorize_report(report_id, owner_id)
        items = await OfficialSourceService.get_authority_sources(
            report_id=report_id, owner_id=owner_id, category=category, location=location, db=self.db,
            pilot_locality_name=self.settings.PILOT_LOCALITY_NAME if self.settings else None,
            pilot_latitude=self.settings.PILOT_LATITUDE if self.settings else None,
            pilot_longitude=self.settings.PILOT_LONGITUDE if self.settings else None,
            pilot_radius_meters=self.settings.PILOT_RADIUS_METERS if self.settings else None,
        )
        sources = {}
        for item in items:
            source = item.to_dict()
            identifier = source["document_id"]
            if identifier not in sources:
                sources[identifier] = source
            else:
                passage = (
                    sources[identifier]["supporting_passage"] + "\n" + source["supporting_passage"]
                )
                sources[identifier]["supporting_passage"] = passage[:2000]
        return list(sources.values())
