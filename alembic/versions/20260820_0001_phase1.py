"""Create the Acquisition Launchpad Phase 1 control-plane schema.

Revision ID: 20260820_0001
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260820_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamps() -> list[sa.Column[object]]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "acquisition_packages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("external_key", sa.String(length=120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("reporting_currency", sa.String(length=3), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
        sa.CheckConstraint("version > 0", name=op.f("ck_acquisition_packages_positive_version")),
        sa.PrimaryKeyConstraint("id", name="pk_acquisition_packages"),
        sa.UniqueConstraint("external_key", "version", name="uq_package_external_key_version"),
    )
    op.create_table(
        "entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("external_id", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("legal_name", sa.String(length=240), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("source_system", sa.String(length=120), nullable=False),
        *_timestamps(),
        sa.CheckConstraint("length(currency) = 3", name=op.f("ck_entities_currency_length")),
        sa.ForeignKeyConstraint(["package_id"], ["acquisition_packages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["parent_id"], ["entities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_entities"),
        sa.UniqueConstraint("package_id", "external_id", name="uq_entity_package_external_id"),
    )
    op.create_index("ix_entities_package_id", "entities", ["package_id"])
    op.create_index("ix_entities_parent_id", "entities", ["parent_id"])
    op.create_table(
        "canonical_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        sa.Column("normal_balance", sa.String(length=10), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["package_id"], ["acquisition_packages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_canonical_accounts"),
        sa.UniqueConstraint("package_id", "code", name="uq_canonical_package_code"),
    )
    op.create_index("ix_canonical_accounts_package_id", "canonical_accounts", ["package_id"])
    op.create_table(
        "source_accounts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("account_type", sa.String(length=20), nullable=False),
        *_timestamps(),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_source_accounts"),
        sa.UniqueConstraint("entity_id", "code", name="uq_source_entity_code"),
    )
    op.create_index("ix_source_accounts_entity_id", "source_accounts", ["entity_id"])
    op.create_table(
        "trial_balance_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_account_id", sa.Uuid(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("debit_cents", sa.BigInteger(), nullable=False, server_default="0"),
        sa.Column("credit_cents", sa.BigInteger(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.CheckConstraint(
            "credit_cents >= 0",
            name=op.f("ck_trial_balance_entries_nonnegative_credit"),
        ),
        sa.CheckConstraint(
            "debit_cents >= 0", name=op.f("ck_trial_balance_entries_nonnegative_debit")
        ),
        sa.CheckConstraint(
            "NOT (debit_cents > 0 AND credit_cents > 0)",
            name=op.f("ck_trial_balance_entries_single_sided_balance"),
        ),
        sa.ForeignKeyConstraint(["source_account_id"], ["source_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_trial_balance_entries"),
        sa.UniqueConstraint("source_account_id", name="uq_trial_balance_source_account"),
    )
    op.create_index(
        "ix_trial_balance_entries_source_account_id",
        "trial_balance_entries",
        ["source_account_id"],
    )
    op.create_table(
        "mapping_suggestions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_account_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_account_id", sa.Uuid(), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="SUGGESTED"),
        sa.Column("approved_by", sa.String(length=160), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_by", sa.String(length=160), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
        sa.CheckConstraint(
            "confidence >= 0 AND confidence <= 1",
            name=op.f("ck_mapping_suggestions_confidence_range"),
        ),
        sa.ForeignKeyConstraint(
            ["canonical_account_id"], ["canonical_accounts.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["source_account_id"], ["source_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_mapping_suggestions"),
        sa.UniqueConstraint(
            "source_account_id",
            "canonical_account_id",
            name="uq_mapping_source_canonical",
        ),
    )
    op.create_index(
        "ix_mapping_suggestions_source_account_id",
        "mapping_suggestions",
        ["source_account_id"],
    )
    op.create_index(
        "ix_mapping_suggestions_canonical_account_id",
        "mapping_suggestions",
        ["canonical_account_id"],
    )
    op.create_index(
        "uq_mapping_one_approved_per_source",
        "mapping_suggestions",
        ["source_account_id"],
        unique=True,
        postgresql_where=sa.text("status = 'APPROVED'"),
    )
    op.create_table(
        "blockers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("source_account_id", sa.Uuid(), nullable=True),
        sa.Column("fingerprint", sa.String(length=240), nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False, server_default="OPEN"),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False),
        sa.Column("system_generated", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolved_by", sa.String(length=160), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("row_version", sa.Integer(), nullable=False, server_default="1"),
        *_timestamps(),
        sa.ForeignKeyConstraint(["package_id"], ["acquisition_packages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_account_id"], ["source_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_blockers"),
        sa.UniqueConstraint("package_id", "fingerprint", name="uq_blocker_package_fingerprint"),
    )
    op.create_index("ix_blockers_package_id", "blockers", ["package_id"])
    op.create_index("ix_blockers_entity_id", "blockers", ["entity_id"])
    op.create_table(
        "readiness_evaluations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("checks", sa.JSON(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["package_id"], ["acquisition_packages.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_readiness_evaluations"),
    )
    op.create_index("ix_readiness_evaluations_package_id", "readiness_evaluations", ["package_id"])
    op.create_index("ix_readiness_evaluations_entity_id", "readiness_evaluations", ["entity_id"])
    op.create_index(
        "ix_readiness_package_computed",
        "readiness_evaluations",
        ["package_id", "computed_at"],
    )
    op.create_table(
        "sequence_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("input_hash", sa.String(length=64), nullable=False),
        sa.Column("steps", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["package_id"], ["acquisition_packages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_sequence_plans"),
        sa.UniqueConstraint("package_id", "version", name="uq_sequence_package_version"),
    )
    op.create_index("ix_sequence_plans_package_id", "sequence_plans", ["package_id"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("package_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=False),
        sa.Column("actor_id", sa.String(length=160), nullable=False),
        sa.Column("subject_type", sa.String(length=80), nullable=False),
        sa.Column("subject_id", sa.String(length=80), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("previous_hash", sa.String(length=64), nullable=True),
        sa.Column("event_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["package_id"], ["acquisition_packages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_events"),
        sa.UniqueConstraint("event_hash", name="uq_audit_events_event_hash"),
        sa.UniqueConstraint("package_id", "sequence", name="uq_audit_package_sequence"),
    )
    op.create_index("ix_audit_events_package_id", "audit_events", ["package_id"])
    op.create_index("ix_audit_package_created", "audit_events", ["package_id", "created_at"])
    op.create_table(
        "idempotency_records",
        sa.Column("key", sa.String(length=200), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=False),
        sa.Column("response_body", sa.JSON(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["resource_id"], ["acquisition_packages.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("key", name="pk_idempotency_records"),
    )


def downgrade() -> None:
    op.drop_table("idempotency_records")
    op.drop_index("ix_audit_package_created", table_name="audit_events")
    op.drop_index("ix_audit_events_package_id", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_sequence_plans_package_id", table_name="sequence_plans")
    op.drop_table("sequence_plans")
    op.drop_index("ix_readiness_package_computed", table_name="readiness_evaluations")
    op.drop_index("ix_readiness_evaluations_entity_id", table_name="readiness_evaluations")
    op.drop_index("ix_readiness_evaluations_package_id", table_name="readiness_evaluations")
    op.drop_table("readiness_evaluations")
    op.drop_index("ix_blockers_entity_id", table_name="blockers")
    op.drop_index("ix_blockers_package_id", table_name="blockers")
    op.drop_table("blockers")
    op.drop_index("uq_mapping_one_approved_per_source", table_name="mapping_suggestions")
    op.drop_index("ix_mapping_suggestions_canonical_account_id", table_name="mapping_suggestions")
    op.drop_index("ix_mapping_suggestions_source_account_id", table_name="mapping_suggestions")
    op.drop_table("mapping_suggestions")
    op.drop_index("ix_trial_balance_entries_source_account_id", table_name="trial_balance_entries")
    op.drop_table("trial_balance_entries")
    op.drop_index("ix_source_accounts_entity_id", table_name="source_accounts")
    op.drop_table("source_accounts")
    op.drop_index("ix_canonical_accounts_package_id", table_name="canonical_accounts")
    op.drop_table("canonical_accounts")
    op.drop_index("ix_entities_parent_id", table_name="entities")
    op.drop_index("ix_entities_package_id", table_name="entities")
    op.drop_table("entities")
    op.drop_table("acquisition_packages")
