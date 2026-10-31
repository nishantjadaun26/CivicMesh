"""SQLAlchemy models. SQL migration is the deployment authority, not create_all."""

from datetime import datetime
from uuid import UUID

from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData()


# Supabase owns this table. Exclude it from generated application DDL.
Table("users", Base.metadata, Column("id", Uuid, primary_key=True), schema="auth")


class Record:
    id: Mapped[UUID] = mapped_column(
        Uuid, primary_key=True, server_default=text("gen_random_uuid()")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )


class Profile(Record, Base):
    __tablename__ = "profiles"
    id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("auth.users.id"), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(100))


class Report(Record, Base):
    __tablename__ = "reports"
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"), index=True)
    category: Mapped[str] = mapped_column(String(20))
    text: Mapped[str] = mapped_column(Text)
    location = Column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    location_confirmed: Mapped[bool] = mapped_column(Boolean)
    extraction = Column(JSONB, nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    __table_args__ = (
        UniqueConstraint("owner_id", "idempotency_key"),
        CheckConstraint("category IN ('garbage','water_leak')"),
        CheckConstraint("location_confirmed = true"),
    )


class Authority(Record, Base):
    __tablename__ = "authorities"
    name: Mapped[str] = mapped_column(Text)
    jurisdiction: Mapped[str] = mapped_column(Text)
    official_url: Mapped[str] = mapped_column(Text)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_evidence: Mapped[str | None] = mapped_column(Text)


class SourceDocument(Record, Base):
    __tablename__ = "source_documents"
    authority_id: Mapped[UUID] = mapped_column(ForeignKey("authorities.id"), index=True)
    url: Mapped[str] = mapped_column(Text)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    content_sha256: Mapped[str] = mapped_column(String(64))
    supporting_text: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("url", "content_sha256"),)


class SourceChunk(Record, Base):
    __tablename__ = "source_chunks"
    document_id: Mapped[UUID] = mapped_column(ForeignKey("source_documents.id"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    page_number: Mapped[int | None] = mapped_column(Integer)
    embedding = Column(Vector(768), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal"),
        CheckConstraint("(embedding IS NULL) = (embedding_model IS NULL)"),
        Index(
            "ix_chunks_embedding",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )


class Incident(Record, Base):
    __tablename__ = "incidents"
    category: Mapped[str] = mapped_column(String(20))
    location = Column(Geography(geometry_type="POINT", srid=4326), nullable=False)
    public_summary: Mapped[str | None] = mapped_column(Text)
    public_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    authority_status: Mapped[str] = mapped_column(String(30), server_default="unknown")
    authority_response_reference: Mapped[str | None] = mapped_column(Text)
    authority_response_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    observed_condition: Mapped[str | None] = mapped_column(String(30))
    observation_attribution: Mapped[str | None] = mapped_column(Text)
    observation_evidence_reference: Mapped[str | None] = mapped_column(Text)
    __table_args__ = (
        CheckConstraint("category IN ('garbage','water_leak')"),
        CheckConstraint("authority_status IN ('unknown','acknowledged','in_progress','resolved')"),
        CheckConstraint(
            "authority_status = 'unknown' OR (authority_response_reference IS NOT NULL AND authority_response_received_at IS NOT NULL)"
        ),
        CheckConstraint(
            "observed_condition IS NULL OR observed_condition IN ('appears_resolved','partly_resolved','persists','insufficient_evidence')"
        ),
        CheckConstraint(
            "observed_condition IS NULL OR (observation_attribution IS NOT NULL AND observation_evidence_reference IS NOT NULL)"
        ),
        CheckConstraint("public_approved_at IS NULL OR public_summary IS NOT NULL"),
        Index(
            "ix_incidents_public_page",
            "created_at",
            "id",
            postgresql_where=text("public_approved_at IS NOT NULL"),
        ),
    )


class IncidentReport(Record, Base):
    __tablename__ = "incident_reports"
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    report_id: Mapped[UUID] = mapped_column(ForeignKey("reports.id"), index=True)
    linked_by: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"), index=True)
    unlinked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    unlinked_by: Mapped[UUID | None] = mapped_column(ForeignKey("profiles.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    __table_args__ = (
        Index(
            "uq_report_active_membership",
            "report_id",
            unique=True,
            postgresql_where=text("unlinked_at IS NULL"),
        ),
        CheckConstraint("(unlinked_at IS NULL) = (unlinked_by IS NULL)"),
    )


class Evidence(Record, Base):
    __tablename__ = "evidence"
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"), index=True)
    report_id: Mapped[UUID | None] = mapped_column(ForeignKey("reports.id"), index=True)
    incident_id: Mapped[UUID | None] = mapped_column(ForeignKey("incidents.id"), index=True)
    object_path: Mapped[str] = mapped_column(Text, unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    uploaded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sha256: Mapped[str | None] = mapped_column(String(64))
    __table_args__ = (
        CheckConstraint(
            "mime_type IN ('image/jpeg','image/png','image/webp','audio/webm','audio/ogg','audio/mp4','audio/mpeg','audio/wav')"
        ),
        CheckConstraint(
            "size_bytes > 0 AND size_bytes <= CASE WHEN mime_type LIKE 'image/%' THEN 10485760 ELSE 20971520 END"
        ),
        CheckConstraint("report_id IS NULL OR incident_id IS NULL"),
    )


class Job(Record, Base):
    __tablename__ = "jobs"
    owner_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"), index=True)
    report_id: Mapped[UUID | None] = mapped_column(ForeignKey("reports.id"), index=True)
    incident_id: Mapped[UUID | None] = mapped_column(ForeignKey("incidents.id"), index=True)
    kind: Mapped[str] = mapped_column(String(60))
    status: Mapped[str] = mapped_column(String(30), server_default="queued")
    attempts: Mapped[int] = mapped_column(Integer, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, server_default="3")
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()")
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_token: Mapped[UUID | None] = mapped_column(Uuid)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_message: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(128))
    __table_args__ = (
        UniqueConstraint("owner_id", "kind", "idempotency_key"),
        CheckConstraint(
            "status IN ('queued','running','waiting_for_input','succeeded','failed','cancelled')"
        ),
        CheckConstraint(
            "attempts >= 0 AND max_attempts BETWEEN 1 AND 10 AND attempts <= max_attempts"
        ),
        CheckConstraint(
            "status <> 'running' OR (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL)"
        ),
        Index("ix_jobs_claim", "status", "available_at"),
    )


class WorkflowRun(Record, Base):
    __tablename__ = "workflow_runs"
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"), unique=True)
    thread_id: Mapped[str] = mapped_column(String(100), unique=True)
    checkpoint_reference: Mapped[str | None] = mapped_column(Text)
    graph_version: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), server_default="queued")


class StatusEvent(Record, Base):
    __tablename__ = "status_events"
    incident_id: Mapped[UUID] = mapped_column(ForeignKey("incidents.id"), index=True)
    actor_id: Mapped[UUID | None] = mapped_column(ForeignKey("profiles.id"), index=True)
    kind: Mapped[str] = mapped_column(String(30))
    authority_status: Mapped[str | None] = mapped_column(String(30))
    observed_condition: Mapped[str | None] = mapped_column(String(30))
    authority_response_reference: Mapped[str | None] = mapped_column(Text)
    authority_response_received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_id: Mapped[UUID | None] = mapped_column(ForeignKey("evidence.id"), index=True)
    attribution: Mapped[str] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint("kind IN ('authority_update','citizen_observation','ai_assessment')"),
        CheckConstraint(
            "(kind = 'authority_update' AND authority_status IS NOT NULL AND authority_status IN ('acknowledged','in_progress','resolved') AND authority_response_reference IS NOT NULL AND authority_response_received_at IS NOT NULL AND observed_condition IS NULL) OR (kind IN ('citizen_observation','ai_assessment') AND authority_status IS NULL AND observed_condition IS NOT NULL AND evidence_id IS NOT NULL)"
        ),
        CheckConstraint(
            "observed_condition IS NULL OR observed_condition IN ('appears_resolved','partly_resolved','persists','insufficient_evidence')"
        ),
    )
