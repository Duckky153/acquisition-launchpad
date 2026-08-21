from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from acquisition_launchpad.db import Base


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AcquisitionPackage(TimestampMixin, Base):
    __tablename__ = "acquisition_packages"
    __table_args__ = (
        UniqueConstraint("external_key", "version", name="uq_package_external_key_version"),
        CheckConstraint("version > 0", name="positive_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    external_key: Mapped[str] = mapped_column(String(120), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    reporting_currency: Mapped[str] = mapped_column(String(3), nullable=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    entities: Mapped[list[Entity]] = relationship(
        back_populates="package", cascade="all, delete-orphan"
    )
    canonical_accounts: Mapped[list[CanonicalAccount]] = relationship(
        back_populates="package", cascade="all, delete-orphan"
    )


class Entity(TimestampMixin, Base):
    __tablename__ = "entities"
    __table_args__ = (
        UniqueConstraint("package_id", "external_id", name="uq_entity_package_external_id"),
        CheckConstraint("length(currency) = 3", name="currency_length"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("acquisition_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("entities.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    external_id: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    legal_name: Mapped[str] = mapped_column(String(240), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    source_system: Mapped[str] = mapped_column(String(120), nullable=False)

    package: Mapped[AcquisitionPackage] = relationship(back_populates="entities")
    parent: Mapped[Entity | None] = relationship(remote_side="Entity.id", back_populates="children")
    children: Mapped[list[Entity]] = relationship(back_populates="parent")
    source_accounts: Mapped[list[SourceAccount]] = relationship(
        back_populates="entity", cascade="all, delete-orphan"
    )


class CanonicalAccount(TimestampMixin, Base):
    __tablename__ = "canonical_accounts"
    __table_args__ = (UniqueConstraint("package_id", "code", name="uq_canonical_package_code"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("acquisition_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)
    normal_balance: Mapped[str] = mapped_column(String(10), nullable=False)

    package: Mapped[AcquisitionPackage] = relationship(back_populates="canonical_accounts")


class SourceAccount(TimestampMixin, Base):
    __tablename__ = "source_accounts"
    __table_args__ = (UniqueConstraint("entity_id", "code", name="uq_source_entity_code"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    entity_id: Mapped[UUID] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    account_type: Mapped[str] = mapped_column(String(20), nullable=False)

    entity: Mapped[Entity] = relationship(back_populates="source_accounts")
    opening_balance: Mapped[TrialBalanceEntry | None] = relationship(
        back_populates="source_account", cascade="all, delete-orphan", uselist=False
    )
    mapping_suggestions: Mapped[list[MappingSuggestion]] = relationship(
        back_populates="source_account", cascade="all, delete-orphan"
    )


class TrialBalanceEntry(TimestampMixin, Base):
    __tablename__ = "trial_balance_entries"
    __table_args__ = (
        UniqueConstraint("source_account_id", name="uq_trial_balance_source_account"),
        CheckConstraint("debit_cents >= 0", name="nonnegative_debit"),
        CheckConstraint("credit_cents >= 0", name="nonnegative_credit"),
        CheckConstraint("NOT (debit_cents > 0 AND credit_cents > 0)", name="single_sided_balance"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    as_of_date: Mapped[date] = mapped_column(Date, nullable=False)
    debit_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    credit_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    source_account: Mapped[SourceAccount] = relationship(back_populates="opening_balance")


class MappingSuggestion(TimestampMixin, Base):
    __tablename__ = "mapping_suggestions"
    __table_args__ = (
        UniqueConstraint(
            "source_account_id", "canonical_account_id", name="uq_mapping_source_canonical"
        ),
        CheckConstraint("confidence >= 0 AND confidence <= 1", name="confidence_range"),
        Index(
            "uq_mapping_one_approved_per_source",
            "source_account_id",
            unique=True,
            postgresql_where=text("status = 'APPROVED'"),
            sqlite_where=text("status = 'APPROVED'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    source_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("source_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    canonical_account_id: Mapped[UUID] = mapped_column(
        ForeignKey("canonical_accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="SUGGESTED")
    approved_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    source_account: Mapped[SourceAccount] = relationship(back_populates="mapping_suggestions")
    canonical_account: Mapped[CanonicalAccount] = relationship()


class Blocker(TimestampMixin, Base):
    __tablename__ = "blockers"
    __table_args__ = (
        UniqueConstraint("package_id", "fingerprint", name="uq_blocker_package_fingerprint"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("acquisition_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    source_account_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("source_accounts.id", ondelete="CASCADE"), nullable=True
    )
    fingerprint: Mapped[str] = mapped_column(String(240), nullable=False)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="OPEN")
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    system_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_by: Mapped[str | None] = mapped_column(String(160), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)


class ReadinessEvaluation(Base):
    __tablename__ = "readiness_evaluations"
    __table_args__ = (Index("ix_readiness_package_computed", "package_id", "computed_at"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("acquisition_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("entities.id", ondelete="CASCADE"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False)
    checks: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class SequencePlan(Base):
    __tablename__ = "sequence_plans"
    __table_args__ = (
        UniqueConstraint("package_id", "version", name="uq_sequence_package_version"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("acquisition_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        UniqueConstraint("package_id", "sequence", name="uq_audit_package_sequence"),
        Index("ix_audit_package_created", "package_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    package_id: Mapped[UUID] = mapped_column(
        ForeignKey("acquisition_packages.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_type: Mapped[str] = mapped_column(String(20), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(160), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(80), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    previous_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"

    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[UUID] = mapped_column(
        ForeignKey("acquisition_packages.id", ondelete="CASCADE"), nullable=False
    )
    response_status: Mapped[int] = mapped_column(Integer, nullable=False)
    response_body: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
