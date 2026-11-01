"""SQLAlchemy database models for CivicMesh."""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from backend.app.database.models.base import Base, TimestampMixin, utc_now
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

try:
    from geoalchemy2 import Geometry
    HAS_GEOALCHEMY = True
except ImportError:
    Geometry = None
    HAS_GEOALCHEMY = False

from sqlalchemy.types import UserDefinedType


class PostGISGeometryPoint(UserDefinedType):
    """PostGIS Point(4326) geometry type for PostgreSQL with SQLite text fallback."""

    def get_col_spec(self, **kw):
        return "GEOMETRY(Point, 4326)"


# Cross-dialect column types (PostgreSQL PostGIS/JSONB in production, SQLite Text/JSON in tests)
JsonType = JSONB().with_variant(JSON, "sqlite")
PointGeometry = PostGISGeometryPoint().with_variant(Text, "sqlite")


class Profile(Base, TimestampMixin):
    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True)


class Authority(Base, TimestampMixin):
    __tablename__ = "authorities"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    jurisdiction: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    portal_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    documents: Mapped[list["SourceDocument"]] = relationship(back_populates="authority", cascade="all, delete-orphan")


class SourceDocument(Base):
    __tablename__ = "source_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    authority_id: Mapped[UUID] = mapped_column(ForeignKey("authorities.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    sha256_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    authority: Mapped["Authority"] = relationship(back_populates="documents")
    chunks: Mapped[list["SourceChunk"]] = relationship(back_populates="document", cascade="all, delete-orphan")


class SourceChunk(Base):
    __tablename__ = "source_chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    document: Mapped["SourceDocument"] = relationship(back_populates="chunks")

    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index", name="uq_source_chunk_document_index"),
    )


class Incident(Base, TimestampMixin):
    __tablename__ = "incidents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    category: Mapped[str] = mapped_column(String(50), nullable=False)  # garbage | water_leak
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    observed_condition: Mapped[str] = mapped_column(Text, nullable=False)
    authority_status: Mapped[str] = mapped_column(String(50), default="unknown", nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # PostGIS geometry column: SRID 4326. Order: ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)
    location = mapped_column(PointGeometry, nullable=True)

    reports: Mapped[list["IncidentReport"]] = relationship(back_populates="incident", cascade="all, delete-orphan")
    timeline: Mapped[list["StatusEvent"]] = relationship(back_populates="incident", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_incidents_category_public", "category", "is_public"),
    )


class Report(Base, TimestampMixin):
    __tablename__ = "reports"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    location_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    extraction_result: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)

    location = mapped_column(PointGeometry, nullable=True)

    evidence_items: Mapped[list["Evidence"]] = relationship(back_populates="report")
    jobs: Mapped[list["Job"]] = relationship(back_populates="report", cascade="all, delete-orphan")
    incident_associations: Mapped[list["IncidentReport"]] = relationship(back_populates="report", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key", name="uq_reports_owner_idempotency_key"),
        Index("idx_reports_owner", "owner_id"),
        Index("idx_reports_status", "status"),
    )


class IncidentReport(Base):
    """Reversible merge membership between incident and individual reports."""
    __tablename__ = "incident_reports"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False)
    report_id: Mapped[UUID] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=False)
    similarity_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    incident: Mapped["Incident"] = relationship(back_populates="reports")
    report: Mapped["Report"] = relationship(back_populates="incident_associations")

    __table_args__ = (
        UniqueConstraint("incident_id", "report_id", name="uq_incident_report"),
        Index("idx_incident_reports_incident", "incident_id"),
        Index("idx_incident_reports_report", "report_id"),
    )


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    report_id: Mapped[UUID | None] = mapped_column(ForeignKey("reports.id", ondelete="SET NULL"), nullable=True)
    incident_id: Mapped[UUID | None] = mapped_column(ForeignKey("incidents.id", ondelete="SET NULL"), nullable=True)
    follow_up_id: Mapped[UUID | None] = mapped_column(ForeignKey("follow_ups.id", ondelete="SET NULL"), nullable=True)
    storage_bucket: Mapped[str] = mapped_column(String(100), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    report: Mapped["Report"] = relationship(back_populates="evidence_items")

    __table_args__ = (
        Index("idx_evidence_owner", "owner_id"),
        Index("idx_evidence_report", "report_id"),
    )


class Job(Base, TimestampMixin):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    report_id: Mapped[UUID | None] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=True, unique=True)
    follow_up_id: Mapped[UUID | None] = mapped_column(ForeignKey("follow_ups.id", ondelete="CASCADE"), nullable=True, unique=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    kind: Mapped[str] = mapped_column(String(50), default="report", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failures: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    checkpoint_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pending_action: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    locked_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    report: Mapped["Report | None"] = relationship(back_populates="jobs")
    workflow_runs: Mapped[list["WorkflowRun"]] = relationship(back_populates="job", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_jobs_owner", "owner_id"),
        Index("idx_jobs_report", "report_id"),
        Index("idx_jobs_status", "status"),
    )


class WorkflowRun(Base, TimestampMixin):
    __tablename__ = "workflow_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True)
    workflow_id: Mapped[UUID] = mapped_column(unique=True, nullable=False)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False)
    state: Mapped[str] = mapped_column(String(50), nullable=False)
    result_payload: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)

    job: Mapped["Job"] = relationship(back_populates="workflow_runs")

    __table_args__ = (
        Index("idx_workflow_runs_job", "job_id"),
        Index("idx_workflow_runs_workflow", "workflow_id"),
    )


class StatusEvent(Base):
    __tablename__ = "status_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    incident_id: Mapped[UUID | None] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"), nullable=True)
    report_id: Mapped[UUID | None] = mapped_column(ForeignKey("reports.id", ondelete="CASCADE"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)  # citizen_observation, ai_assessment, authority_update
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    incident: Mapped["Incident"] = relationship(back_populates="timeline")

    __table_args__ = (
        Index("idx_status_events_incident", "incident_id"),
        Index("idx_status_events_report", "report_id"),
    )


class FollowUp(Base, TimestampMixin):
    """Private owner-scoped observation; no implicit public or authority-status writes."""
    __tablename__ = "follow_ups"
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id", ondelete="CASCADE"))
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.id", ondelete="CASCADE"))
    text: Mapped[str] = mapped_column(Text, default="")
    same_location_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    result: Mapped[dict | None] = mapped_column(JsonType, nullable=True)
    __table_args__ = (UniqueConstraint("owner_id", "idempotency_key", name="uq_follow_up_owner_key"),)


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"
    worker_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class RateWindow(Base):
    __tablename__ = "rate_windows"
    owner_id: Mapped[UUID] = mapped_column(primary_key=True)
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, default=0)
