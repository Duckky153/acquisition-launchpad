from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from acquisition_launchpad.enums import (
    AccountType,
    BlockerSeverity,
    BlockerState,
    MappingStatus,
    NormalBalance,
    ReadinessStatus,
    SequenceStepState,
    SequenceStepType,
)

NonEmpty = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Currency = Annotated[
    str, StringConstraints(strip_whitespace=True, to_upper=True, pattern=r"^[A-Z]{3}$")
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntityInput(StrictModel):
    external_id: NonEmpty
    parent_external_id: NonEmpty | None = None
    name: NonEmpty
    legal_name: NonEmpty
    currency: Currency
    source_system: NonEmpty


class CanonicalAccountInput(StrictModel):
    code: NonEmpty
    name: NonEmpty
    account_type: AccountType
    normal_balance: NormalBalance


class SourceAccountInput(StrictModel):
    entity_external_id: NonEmpty
    code: NonEmpty
    name: NonEmpty
    account_type: AccountType


class TrialBalanceInput(StrictModel):
    entity_external_id: NonEmpty
    source_account_code: NonEmpty
    debit_cents: int = Field(ge=0)
    credit_cents: int = Field(ge=0)

    @model_validator(mode="after")
    def single_sided(self) -> "TrialBalanceInput":
        if self.debit_cents > 0 and self.credit_cents > 0:
            raise ValueError("a trial-balance row cannot contain both a debit and a credit")
        return self


class MappingSuggestionInput(StrictModel):
    entity_external_id: NonEmpty
    source_account_code: NonEmpty
    canonical_account_code: NonEmpty
    confidence: float = Field(ge=0, le=1)
    rationale: NonEmpty


class AcquisitionPackageInput(StrictModel):
    schema_version: Literal["1.0"]
    external_key: NonEmpty
    package_version: int = Field(ge=1)
    name: NonEmpty
    as_of_date: date
    reporting_currency: Currency
    entities: list[EntityInput] = Field(min_length=1)
    canonical_accounts: list[CanonicalAccountInput] = Field(min_length=1)
    source_accounts: list[SourceAccountInput] = Field(min_length=1)
    trial_balance: list[TrialBalanceInput] = Field(min_length=1)
    mapping_suggestions: list[MappingSuggestionInput] = Field(default_factory=list)


class ImportResult(StrictModel):
    package_id: UUID
    external_key: str
    package_version: int
    replayed: bool
    payload_hash: str


class TieOutView(StrictModel):
    debit_cents: int
    credit_cents: int
    difference_cents: int
    is_balanced: bool
    entry_count: int
    account_count: int
    missing_account_codes: list[str]


class ReadinessCheckView(StrictModel):
    code: str
    passed: bool
    detail: str


class EntityReadinessView(StrictModel):
    entity_id: UUID
    entity_external_id: str
    entity_name: str
    status: ReadinessStatus
    checks: list[ReadinessCheckView]
    tie_out: TieOutView


class PackageReadinessView(StrictModel):
    evaluation_id: UUID
    package_id: UUID
    status: ReadinessStatus
    computed_at: datetime
    entities: list[EntityReadinessView]


class MappingView(StrictModel):
    id: UUID
    source_account_id: UUID
    canonical_account_id: UUID
    entity_external_id: str
    source_account_code: str
    source_account_name: str
    canonical_account_code: str
    canonical_account_name: str
    confidence: float
    rationale: str
    status: MappingStatus
    approved_by: str | None
    row_version: int


class CanonicalAccountView(StrictModel):
    id: UUID
    code: str
    name: str
    account_type: AccountType
    normal_balance: NormalBalance


class SourceAccountView(StrictModel):
    id: UUID
    entity_id: UUID
    entity_external_id: str
    entity_name: str
    code: str
    name: str
    account_type: AccountType
    opening_balance_as_of: date | None
    debit_cents: int | None
    credit_cents: int | None
    approved_mapping: MappingView | None
    suggestions: list[MappingView]


class MappingDecision(StrictModel):
    actor_id: NonEmpty
    expected_version: int = Field(ge=1)
    note: NonEmpty


class MappingCreate(StrictModel):
    source_account_id: UUID
    canonical_account_id: UUID
    confidence: float = Field(ge=0, le=1)
    rationale: NonEmpty
    actor_id: NonEmpty


class ManualBlockerCreate(StrictModel):
    entity_id: UUID | None = None
    source_account_id: UUID | None = None
    code: NonEmpty
    severity: BlockerSeverity
    title: NonEmpty
    detail: NonEmpty
    actor_id: NonEmpty


class BlockerResolution(StrictModel):
    actor_id: NonEmpty
    expected_version: int = Field(ge=1)
    resolution_note: NonEmpty


class BlockerView(StrictModel):
    id: UUID
    entity_id: UUID | None
    source_account_id: UUID | None
    code: str
    severity: BlockerSeverity
    state: BlockerState
    title: str
    detail: str
    system_generated: bool
    resolved_by: str | None
    resolution_note: str | None
    row_version: int


class SequenceStepView(StrictModel):
    key: str
    entity_external_id: str
    entity_name: str
    step_type: SequenceStepType
    state: SequenceStepState
    depends_on: list[str]
    blocked_by: list[str]
    order: int


class SequencePlanView(StrictModel):
    plan_id: UUID
    package_id: UUID
    version: int
    created_at: datetime
    steps: list[SequenceStepView]


class AuditEventView(StrictModel):
    id: UUID
    sequence: int
    event_type: str
    actor_type: str
    actor_id: str
    subject_type: str
    subject_id: str
    payload: dict[str, object]
    previous_hash: str | None
    event_hash: str
    created_at: datetime


class AuditVerificationView(StrictModel):
    package_id: UUID
    valid: bool
    event_count: int
    first_invalid_sequence: int | None


class EntitySummary(StrictModel):
    id: UUID
    external_id: str
    parent_id: UUID | None
    name: str
    legal_name: str
    currency: str
    source_system: str
    source_account_count: int


class PackageDetail(StrictModel):
    id: UUID
    external_key: str
    package_version: int
    name: str
    as_of_date: date
    reporting_currency: str
    payload_hash: str
    entities: list[EntitySummary]
