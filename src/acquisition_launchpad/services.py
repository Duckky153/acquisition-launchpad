from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from acquisition_launchpad.domain import (
    SequenceSeed,
    build_sequence,
    compute_tie_out,
    package_payload_hash,
    sequence_to_dicts,
    sha256_json,
    validate_entity_hierarchy,
    validate_package_references,
)
from acquisition_launchpad.enums import (
    AccountType,
    ActorType,
    BlockerSeverity,
    BlockerState,
    MappingStatus,
    NormalBalance,
    ReadinessStatus,
)
from acquisition_launchpad.errors import ConflictError, NotFoundError, ValidationError
from acquisition_launchpad.models import (
    AcquisitionPackage,
    AuditEvent,
    Blocker,
    CanonicalAccount,
    Entity,
    IdempotencyRecord,
    MappingSuggestion,
    ReadinessEvaluation,
    SequencePlan,
    SourceAccount,
    TrialBalanceEntry,
)
from acquisition_launchpad.schemas import (
    AcquisitionPackageInput,
    AuditEventView,
    AuditVerificationView,
    BlockerResolution,
    BlockerView,
    CanonicalAccountView,
    EntityReadinessView,
    EntitySummary,
    ImportResult,
    ManualBlockerCreate,
    MappingCreate,
    MappingDecision,
    MappingView,
    PackageDetail,
    PackageReadinessView,
    ReadinessCheckView,
    SequencePlanView,
    SequenceStepView,
    SourceAccountView,
    TieOutView,
)


def _package_or_raise(session: Session, package_id: UUID) -> AcquisitionPackage:
    package = session.get(AcquisitionPackage, package_id)
    if package is None:
        raise NotFoundError(f"acquisition package {package_id} was not found")
    return package


def _canonical_event_content(
    *,
    event_id: UUID,
    package_id: UUID,
    sequence: int,
    event_type: str,
    actor_type: str,
    actor_id: str,
    subject_type: str,
    subject_id: str,
    payload: dict[str, Any],
    previous_hash: str | None,
    created_at: datetime,
) -> dict[str, Any]:
    normalized_created_at = created_at
    if normalized_created_at.tzinfo is None:
        normalized_created_at = normalized_created_at.replace(tzinfo=UTC)
    else:
        normalized_created_at = normalized_created_at.astimezone(UTC)
    return {
        "id": str(event_id),
        "package_id": str(package_id),
        "sequence": sequence,
        "event_type": event_type,
        "actor_type": actor_type,
        "actor_id": actor_id,
        "subject_type": subject_type,
        "subject_id": subject_id,
        "payload": payload,
        "previous_hash": previous_hash,
        "created_at": normalized_created_at.isoformat(timespec="microseconds"),
    }


def append_audit_event(
    session: Session,
    *,
    package_id: UUID,
    event_type: str,
    actor_type: ActorType,
    actor_id: str,
    subject_type: str,
    subject_id: str,
    payload: dict[str, Any],
) -> AuditEvent:
    # Serialize per package in PostgreSQL so two concurrent writers cannot reuse a sequence.
    session.execute(
        select(AcquisitionPackage.id).where(AcquisitionPackage.id == package_id).with_for_update()
    ).scalar_one()
    previous = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.package_id == package_id)
        .order_by(AuditEvent.sequence.desc())
        .limit(1)
    ).first()
    sequence = 1 if previous is None else previous.sequence + 1
    previous_hash = None if previous is None else previous.event_hash
    created_at = datetime.now(UTC)
    event_id = uuid4()
    content = _canonical_event_content(
        event_id=event_id,
        package_id=package_id,
        sequence=sequence,
        event_type=event_type,
        actor_type=actor_type.value,
        actor_id=actor_id,
        subject_type=subject_type,
        subject_id=subject_id,
        payload=payload,
        previous_hash=previous_hash,
        created_at=created_at,
    )
    event = AuditEvent(
        id=event_id,
        package_id=package_id,
        sequence=sequence,
        event_type=event_type,
        actor_type=actor_type.value,
        actor_id=actor_id,
        subject_type=subject_type,
        subject_id=subject_id,
        payload=payload,
        previous_hash=previous_hash,
        event_hash=sha256_json(content),
        created_at=created_at,
    )
    session.add(event)
    session.flush()
    return event


def import_package(
    session: Session, payload: AcquisitionPackageInput, idempotency_key: str
) -> ImportResult:
    if not idempotency_key.strip():
        raise ValidationError("Idempotency-Key must be a non-empty string")
    request_hash = package_payload_hash(payload)
    prior_idempotency = session.get(IdempotencyRecord, idempotency_key)
    if prior_idempotency is not None:
        if prior_idempotency.request_hash != request_hash:
            raise ConflictError("Idempotency-Key was already used for a different payload")
        stored = prior_idempotency.response_body
        return ImportResult(
            package_id=UUID(str(stored["package_id"])),
            external_key=str(stored["external_key"]),
            package_version=int(stored["package_version"]),
            replayed=True,
            payload_hash=str(stored["payload_hash"]),
        )

    validate_package_references(payload)
    entity_order = validate_entity_hierarchy(payload.entities)
    existing = session.scalars(
        select(AcquisitionPackage).where(
            AcquisitionPackage.external_key == payload.external_key,
            AcquisitionPackage.version == payload.package_version,
        )
    ).one_or_none()
    if existing is not None:
        if existing.payload_hash != request_hash:
            raise ConflictError(
                "package external_key and version already exist with different content"
            )
        result = ImportResult(
            package_id=existing.id,
            external_key=existing.external_key,
            package_version=existing.version,
            replayed=True,
            payload_hash=existing.payload_hash,
        )
        _record_idempotency(session, idempotency_key, request_hash, result)
        session.commit()
        return result

    package = AcquisitionPackage(
        external_key=payload.external_key,
        version=payload.package_version,
        name=payload.name,
        as_of_date=payload.as_of_date,
        reporting_currency=payload.reporting_currency,
        payload_hash=request_hash,
    )
    session.add(package)
    session.flush()

    canonical_by_code: dict[str, CanonicalAccount] = {}
    for canonical_input in payload.canonical_accounts:
        account = CanonicalAccount(
            package_id=package.id,
            code=canonical_input.code,
            name=canonical_input.name,
            account_type=canonical_input.account_type.value,
            normal_balance=canonical_input.normal_balance.value,
        )
        session.add(account)
        canonical_by_code[canonical_input.code] = account
    session.flush()

    entity_input_by_id = {item.external_id: item for item in payload.entities}
    entity_by_external_id: dict[str, Entity] = {}
    for external_id in entity_order:
        item = entity_input_by_id[external_id]
        parent = (
            entity_by_external_id[item.parent_external_id]
            if item.parent_external_id is not None
            else None
        )
        entity = Entity(
            package_id=package.id,
            parent_id=None if parent is None else parent.id,
            external_id=item.external_id,
            name=item.name,
            legal_name=item.legal_name,
            currency=item.currency,
            source_system=item.source_system,
        )
        session.add(entity)
        session.flush()
        entity_by_external_id[item.external_id] = entity

    source_by_key: dict[tuple[str, str], SourceAccount] = {}
    for source_input in payload.source_accounts:
        source = SourceAccount(
            entity_id=entity_by_external_id[source_input.entity_external_id].id,
            code=source_input.code,
            name=source_input.name,
            account_type=source_input.account_type.value,
        )
        session.add(source)
        source_by_key[(source_input.entity_external_id, source_input.code)] = source
    session.flush()

    for balance_input in payload.trial_balance:
        source = source_by_key[
            (balance_input.entity_external_id, balance_input.source_account_code)
        ]
        session.add(
            TrialBalanceEntry(
                source_account_id=source.id,
                as_of_date=payload.as_of_date,
                debit_cents=balance_input.debit_cents,
                credit_cents=balance_input.credit_cents,
            )
        )

    for suggestion_input in payload.mapping_suggestions:
        source = source_by_key[
            (suggestion_input.entity_external_id, suggestion_input.source_account_code)
        ]
        canonical = canonical_by_code[suggestion_input.canonical_account_code]
        session.add(
            MappingSuggestion(
                source_account_id=source.id,
                canonical_account_id=canonical.id,
                confidence=Decimal(str(suggestion_input.confidence)),
                rationale=suggestion_input.rationale,
                status=MappingStatus.SUGGESTED.value,
            )
        )
    session.flush()

    append_audit_event(
        session,
        package_id=package.id,
        event_type="PACKAGE_IMPORTED",
        actor_type=ActorType.SYSTEM,
        actor_id="package-importer",
        subject_type="acquisition_package",
        subject_id=str(package.id),
        payload={
            "external_key": package.external_key,
            "package_version": package.version,
            "payload_hash": request_hash,
            "entity_count": len(payload.entities),
            "canonical_account_count": len(payload.canonical_accounts),
            "source_account_count": len(payload.source_accounts),
            "trial_balance_entry_count": len(payload.trial_balance),
            "mapping_suggestion_count": len(payload.mapping_suggestions),
        },
    )
    _recalculate_package(session, package.id, reason="PACKAGE_IMPORTED")
    result = ImportResult(
        package_id=package.id,
        external_key=package.external_key,
        package_version=package.version,
        replayed=False,
        payload_hash=request_hash,
    )
    _record_idempotency(session, idempotency_key, request_hash, result)
    session.commit()
    return result


def _record_idempotency(
    session: Session, key: str, request_hash: str, result: ImportResult
) -> None:
    body = {
        "package_id": str(result.package_id),
        "external_key": result.external_key,
        "package_version": result.package_version,
        "replayed": False,
        "payload_hash": result.payload_hash,
    }
    session.add(
        IdempotencyRecord(
            key=key,
            request_hash=request_hash,
            resource_id=result.package_id,
            response_status=201,
            response_body=body,
        )
    )


def get_package(session: Session, package_id: UUID) -> PackageDetail:
    package = session.scalars(
        select(AcquisitionPackage)
        .where(AcquisitionPackage.id == package_id)
        .options(selectinload(AcquisitionPackage.entities).selectinload(Entity.source_accounts))
    ).one_or_none()
    if package is None:
        raise NotFoundError(f"acquisition package {package_id} was not found")
    entities = [
        EntitySummary(
            id=entity.id,
            external_id=entity.external_id,
            parent_id=entity.parent_id,
            name=entity.name,
            legal_name=entity.legal_name,
            currency=entity.currency,
            source_system=entity.source_system,
            source_account_count=len(entity.source_accounts),
        )
        for entity in sorted(package.entities, key=lambda value: value.external_id)
    ]
    return PackageDetail(
        id=package.id,
        external_key=package.external_key,
        package_version=package.version,
        name=package.name,
        as_of_date=package.as_of_date,
        reporting_currency=package.reporting_currency,
        payload_hash=package.payload_hash,
        entities=entities,
    )


def list_canonical_accounts(session: Session, package_id: UUID) -> list[CanonicalAccountView]:
    _package_or_raise(session, package_id)
    accounts = session.scalars(
        select(CanonicalAccount)
        .where(CanonicalAccount.package_id == package_id)
        .order_by(CanonicalAccount.code)
    ).all()
    return [
        CanonicalAccountView(
            id=account.id,
            code=account.code,
            name=account.name,
            account_type=AccountType(account.account_type),
            normal_balance=NormalBalance(account.normal_balance),
        )
        for account in accounts
    ]


def list_source_accounts(
    session: Session, package_id: UUID, entity_id: UUID | None = None
) -> list[SourceAccountView]:
    _package_or_raise(session, package_id)
    query = (
        select(SourceAccount)
        .join(SourceAccount.entity)
        .where(Entity.package_id == package_id)
        .options(
            selectinload(SourceAccount.entity),
            selectinload(SourceAccount.opening_balance),
            selectinload(SourceAccount.mapping_suggestions).selectinload(
                MappingSuggestion.canonical_account
            ),
        )
        .order_by(Entity.external_id, SourceAccount.code)
    )
    if entity_id is not None:
        query = query.where(SourceAccount.entity_id == entity_id)
    accounts = session.scalars(query).all()
    if entity_id is not None and not accounts:
        entity = session.get(Entity, entity_id)
        if entity is None or entity.package_id != package_id:
            raise NotFoundError(f"entity {entity_id} was not found in this package")
    output: list[SourceAccountView] = []
    for account in accounts:
        suggestions = sorted(
            (_mapping_view(mapping) for mapping in account.mapping_suggestions),
            key=lambda mapping: (-mapping.confidence, mapping.canonical_account_code),
        )
        approved = next(
            (mapping for mapping in suggestions if mapping.status is MappingStatus.APPROVED),
            None,
        )
        balance = account.opening_balance
        output.append(
            SourceAccountView(
                id=account.id,
                entity_id=account.entity_id,
                entity_external_id=account.entity.external_id,
                entity_name=account.entity.name,
                code=account.code,
                name=account.name,
                account_type=AccountType(account.account_type),
                opening_balance_as_of=None if balance is None else balance.as_of_date,
                debit_cents=None if balance is None else balance.debit_cents,
                credit_cents=None if balance is None else balance.credit_cents,
                approved_mapping=approved,
                suggestions=suggestions,
            )
        )
    return output


def list_mappings(session: Session, package_id: UUID) -> list[MappingView]:
    _package_or_raise(session, package_id)
    rows = session.scalars(
        select(MappingSuggestion)
        .join(MappingSuggestion.source_account)
        .join(SourceAccount.entity)
        .where(Entity.package_id == package_id)
        .options(
            selectinload(MappingSuggestion.source_account).selectinload(SourceAccount.entity),
            selectinload(MappingSuggestion.canonical_account),
        )
        .order_by(Entity.external_id, SourceAccount.code, MappingSuggestion.confidence.desc())
    ).all()
    return [_mapping_view(row) for row in rows]


def _mapping_view(row: MappingSuggestion) -> MappingView:
    return MappingView(
        id=row.id,
        source_account_id=row.source_account_id,
        canonical_account_id=row.canonical_account_id,
        entity_external_id=row.source_account.entity.external_id,
        source_account_code=row.source_account.code,
        source_account_name=row.source_account.name,
        canonical_account_code=row.canonical_account.code,
        canonical_account_name=row.canonical_account.name,
        confidence=float(row.confidence),
        rationale=row.rationale,
        status=MappingStatus(row.status),
        approved_by=row.approved_by,
        row_version=row.row_version,
    )


def create_mapping_suggestion(
    session: Session, package_id: UUID, command: MappingCreate
) -> MappingView:
    _package_or_raise(session, package_id)
    source = session.scalars(
        select(SourceAccount)
        .join(SourceAccount.entity)
        .where(SourceAccount.id == command.source_account_id, Entity.package_id == package_id)
        .options(selectinload(SourceAccount.entity))
    ).one_or_none()
    canonical = session.scalars(
        select(CanonicalAccount).where(
            CanonicalAccount.id == command.canonical_account_id,
            CanonicalAccount.package_id == package_id,
        )
    ).one_or_none()
    if source is None or canonical is None:
        raise ValidationError("source and canonical accounts must belong to the package")
    existing = session.scalars(
        select(MappingSuggestion).where(
            MappingSuggestion.source_account_id == source.id,
            MappingSuggestion.canonical_account_id == canonical.id,
        )
    ).one_or_none()
    if existing is not None:
        raise ConflictError("that mapping suggestion already exists")
    suggestion = MappingSuggestion(
        source_account_id=source.id,
        canonical_account_id=canonical.id,
        confidence=Decimal(str(command.confidence)),
        rationale=command.rationale,
        status=MappingStatus.SUGGESTED.value,
    )
    suggestion.source_account = source
    suggestion.canonical_account = canonical
    session.add(suggestion)
    session.flush()
    append_audit_event(
        session,
        package_id=package_id,
        event_type="MAPPING_SUGGESTED",
        actor_type=ActorType.HUMAN,
        actor_id=command.actor_id,
        subject_type="mapping_suggestion",
        subject_id=str(suggestion.id),
        payload={
            "source_account_id": str(source.id),
            "canonical_account_id": str(canonical.id),
            "confidence": command.confidence,
            "rationale": command.rationale,
            "status": MappingStatus.SUGGESTED.value,
        },
    )
    session.commit()
    return _mapping_view(suggestion)


def decide_mapping(
    session: Session,
    package_id: UUID,
    mapping_id: UUID,
    command: MappingDecision,
    decision: MappingStatus,
) -> MappingView:
    if decision not in {MappingStatus.APPROVED, MappingStatus.REJECTED}:
        raise ValidationError("mapping decision must be APPROVED or REJECTED")
    suggestion = session.scalars(
        select(MappingSuggestion)
        .where(MappingSuggestion.id == mapping_id)
        .options(
            selectinload(MappingSuggestion.source_account).selectinload(SourceAccount.entity),
            selectinload(MappingSuggestion.canonical_account),
        )
        .with_for_update()
    ).one_or_none()
    if suggestion is None or suggestion.source_account.entity.package_id != package_id:
        raise NotFoundError(f"mapping suggestion {mapping_id} was not found in this package")
    if suggestion.row_version != command.expected_version:
        raise ConflictError(
            f"mapping version conflict: expected {command.expected_version}, "
            f"current {suggestion.row_version}"
        )
    session.execute(
        select(SourceAccount.id)
        .where(SourceAccount.id == suggestion.source_account_id)
        .with_for_update()
    ).scalar_one()
    if suggestion.status == decision.value:
        return _mapping_view(suggestion)

    now = datetime.now(UTC)
    displaced: list[str] = []
    if decision is MappingStatus.APPROVED:
        if suggestion.source_account.account_type != suggestion.canonical_account.account_type:
            raise ValidationError(
                "source and canonical account types must match before approval; "
                "create a compatible suggestion instead"
            )
        currently_approved = session.scalars(
            select(MappingSuggestion)
            .where(
                MappingSuggestion.source_account_id == suggestion.source_account_id,
                MappingSuggestion.status == MappingStatus.APPROVED.value,
                MappingSuggestion.id != suggestion.id,
            )
            .with_for_update()
        ).all()
        for other in currently_approved:
            other.status = MappingStatus.REJECTED.value
            other.rejected_by = command.actor_id
            other.rejected_at = now
            other.row_version += 1
            displaced.append(str(other.id))
        if currently_approved:
            # Clear the partial unique index before approving the replacement. SQLAlchemy does
            # not otherwise guarantee update order for two rows in the same flush.
            session.flush()
        suggestion.status = MappingStatus.APPROVED.value
        suggestion.approved_by = command.actor_id
        suggestion.approved_at = now
        suggestion.rejected_by = None
        suggestion.rejected_at = None
    else:
        suggestion.status = MappingStatus.REJECTED.value
        suggestion.rejected_by = command.actor_id
        suggestion.rejected_at = now
        suggestion.approved_by = None
        suggestion.approved_at = None
    suggestion.row_version += 1
    session.flush()
    append_audit_event(
        session,
        package_id=package_id,
        event_type=f"MAPPING_{decision.value}",
        actor_type=ActorType.HUMAN,
        actor_id=command.actor_id,
        subject_type="mapping_suggestion",
        subject_id=str(suggestion.id),
        payload={
            "source_account_id": str(suggestion.source_account_id),
            "canonical_account_id": str(suggestion.canonical_account_id),
            "decision": decision.value,
            "decision_note": command.note,
            "row_version": suggestion.row_version,
            "displaced_approved_mapping_ids": displaced,
        },
    )
    _recalculate_package(session, package_id, reason=f"MAPPING_{decision.value}")
    session.commit()
    return _mapping_view(suggestion)


def _blocker_view(blocker: Blocker) -> BlockerView:
    return BlockerView(
        id=blocker.id,
        entity_id=blocker.entity_id,
        source_account_id=blocker.source_account_id,
        code=blocker.code,
        severity=BlockerSeverity(blocker.severity),
        state=BlockerState(blocker.state),
        title=blocker.title,
        detail=blocker.detail,
        system_generated=blocker.system_generated,
        resolved_by=blocker.resolved_by,
        resolution_note=blocker.resolution_note,
        row_version=blocker.row_version,
    )


def list_blockers(session: Session, package_id: UUID) -> list[BlockerView]:
    _package_or_raise(session, package_id)
    rows = session.scalars(
        select(Blocker)
        .where(Blocker.package_id == package_id)
        .order_by(Blocker.state, Blocker.severity, Blocker.code, Blocker.created_at)
    ).all()
    return [_blocker_view(row) for row in rows]


def create_manual_blocker(
    session: Session, package_id: UUID, command: ManualBlockerCreate
) -> BlockerView:
    _package_or_raise(session, package_id)
    if command.entity_id is not None:
        entity = session.get(Entity, command.entity_id)
        if entity is None or entity.package_id != package_id:
            raise ValidationError("entity_id must belong to the package")
    if command.source_account_id is not None:
        source = session.scalars(
            select(SourceAccount)
            .join(SourceAccount.entity)
            .where(SourceAccount.id == command.source_account_id, Entity.package_id == package_id)
        ).one_or_none()
        if source is None:
            raise ValidationError("source_account_id must belong to the package")
        if command.entity_id is not None and source.entity_id != command.entity_id:
            raise ValidationError("source_account_id must belong to entity_id")
    blocker = Blocker(
        package_id=package_id,
        entity_id=command.entity_id,
        source_account_id=command.source_account_id,
        fingerprint=f"manual:{command.code}:{uuid4()}",
        code=command.code,
        severity=command.severity.value,
        state=BlockerState.OPEN.value,
        title=command.title,
        detail=command.detail,
        system_generated=False,
    )
    session.add(blocker)
    session.flush()
    append_audit_event(
        session,
        package_id=package_id,
        event_type="BLOCKER_CREATED",
        actor_type=ActorType.HUMAN,
        actor_id=command.actor_id,
        subject_type="blocker",
        subject_id=str(blocker.id),
        payload={
            "code": blocker.code,
            "severity": blocker.severity,
            "entity_id": None if blocker.entity_id is None else str(blocker.entity_id),
            "source_account_id": (
                None if blocker.source_account_id is None else str(blocker.source_account_id)
            ),
            "title": blocker.title,
            "detail": blocker.detail,
        },
    )
    _recalculate_package(session, package_id, reason="BLOCKER_CREATED")
    session.commit()
    return _blocker_view(blocker)


def resolve_blocker(
    session: Session, package_id: UUID, blocker_id: UUID, command: BlockerResolution
) -> BlockerView:
    blocker = session.scalars(
        select(Blocker).where(Blocker.id == blocker_id).with_for_update()
    ).one_or_none()
    if blocker is None or blocker.package_id != package_id:
        raise NotFoundError(f"blocker {blocker_id} was not found in this package")
    if blocker.system_generated:
        raise ConflictError(
            "system-generated blockers are derived from source data and cannot be manually resolved"
        )
    if blocker.row_version != command.expected_version:
        raise ConflictError(
            f"blocker version conflict: expected {command.expected_version}, "
            f"current {blocker.row_version}"
        )
    if blocker.state == BlockerState.RESOLVED.value:
        return _blocker_view(blocker)
    blocker.state = BlockerState.RESOLVED.value
    blocker.resolved_by = command.actor_id
    blocker.resolved_at = datetime.now(UTC)
    blocker.resolution_note = command.resolution_note
    blocker.row_version += 1
    session.flush()
    append_audit_event(
        session,
        package_id=package_id,
        event_type="BLOCKER_RESOLVED",
        actor_type=ActorType.HUMAN,
        actor_id=command.actor_id,
        subject_type="blocker",
        subject_id=str(blocker.id),
        payload={
            "resolution_note": command.resolution_note,
            "row_version": blocker.row_version,
        },
    )
    _recalculate_package(session, package_id, reason="BLOCKER_RESOLVED")
    session.commit()
    return _blocker_view(blocker)


def _desired_system_blockers(session: Session, package_id: UUID) -> dict[str, dict[str, Any]]:
    entities = session.scalars(
        select(Entity).where(Entity.package_id == package_id).order_by(Entity.external_id)
    ).all()
    accounts = session.scalars(
        select(SourceAccount)
        .join(SourceAccount.entity)
        .where(Entity.package_id == package_id)
        .options(selectinload(SourceAccount.opening_balance))
        .order_by(SourceAccount.code)
    ).all()
    accounts_by_entity: dict[UUID, list[SourceAccount]] = defaultdict(list)
    for account in accounts:
        accounts_by_entity[account.entity_id].append(account)
    approved_source_ids = set(
        session.scalars(
            select(MappingSuggestion.source_account_id)
            .join(MappingSuggestion.source_account)
            .join(SourceAccount.entity)
            .where(
                Entity.package_id == package_id,
                MappingSuggestion.status == MappingStatus.APPROVED.value,
            )
        ).all()
    )
    desired: dict[str, dict[str, Any]] = {}
    for entity in entities:
        entity_accounts = accounts_by_entity[entity.id]
        if not entity_accounts:
            fingerprint = f"system:{entity.external_id}:no-source-accounts"
            desired[fingerprint] = {
                "entity_id": entity.id,
                "source_account_id": None,
                "code": "NO_SOURCE_ACCOUNTS",
                "title": "No source accounts imported",
                "detail": f"{entity.name} has no source chart of accounts.",
            }
            continue
        for account in entity_accounts:
            if account.opening_balance is None:
                fingerprint = f"system:{entity.external_id}:missing-balance:{account.code}"
                desired[fingerprint] = {
                    "entity_id": entity.id,
                    "source_account_id": account.id,
                    "code": "MISSING_OPENING_BALANCE",
                    "title": "Opening balance is missing",
                    "detail": f"Source account {account.code} has no opening balance.",
                }
            if account.id not in approved_source_ids:
                fingerprint = f"system:{entity.external_id}:unapproved-mapping:{account.code}"
                desired[fingerprint] = {
                    "entity_id": entity.id,
                    "source_account_id": account.id,
                    "code": "UNAPPROVED_ACCOUNT_MAPPING",
                    "title": "Account mapping requires human approval",
                    "detail": (
                        f"Source account {account.code} has no human-approved canonical mapping."
                    ),
                }
        tie_out = compute_tie_out(
            [account.code for account in entity_accounts],
            [
                (
                    account.code,
                    account.opening_balance.debit_cents,
                    account.opening_balance.credit_cents,
                )
                for account in entity_accounts
                if account.opening_balance is not None
            ],
        )
        if tie_out.difference_cents != 0:
            fingerprint = f"system:{entity.external_id}:trial-balance-difference"
            desired[fingerprint] = {
                "entity_id": entity.id,
                "source_account_id": None,
                "code": "UNBALANCED_TRIAL_BALANCE",
                "title": "Opening trial balance does not tie",
                "detail": (
                    f"Debits and credits differ by {tie_out.difference_cents} cents "
                    f"for {entity.name}."
                ),
            }
    return desired


def refresh_system_blockers(session: Session, package_id: UUID) -> list[str]:
    desired = _desired_system_blockers(session, package_id)
    existing = {
        row.fingerprint: row
        for row in session.scalars(
            select(Blocker).where(
                Blocker.package_id == package_id, Blocker.system_generated.is_(True)
            )
        ).all()
    }
    changes: list[str] = []
    for fingerprint, specification in desired.items():
        blocker = existing.get(fingerprint)
        if blocker is None:
            blocker = Blocker(
                package_id=package_id,
                fingerprint=fingerprint,
                code=str(specification["code"]),
                severity=BlockerSeverity.BLOCKING.value,
                state=BlockerState.OPEN.value,
                title=str(specification["title"]),
                detail=str(specification["detail"]),
                system_generated=True,
                entity_id=specification["entity_id"],
                source_account_id=specification["source_account_id"],
            )
            session.add(blocker)
            changes.append(f"OPENED:{fingerprint}")
        else:
            blocker.title = str(specification["title"])
            blocker.detail = str(specification["detail"])
            if blocker.state != BlockerState.OPEN.value:
                blocker.state = BlockerState.OPEN.value
                blocker.resolved_by = None
                blocker.resolved_at = None
                blocker.resolution_note = None
                blocker.row_version += 1
                changes.append(f"REOPENED:{fingerprint}")
    for fingerprint, blocker in existing.items():
        if fingerprint not in desired and blocker.state == BlockerState.OPEN.value:
            blocker.state = BlockerState.RESOLVED.value
            blocker.resolved_by = "readiness-engine"
            blocker.resolved_at = datetime.now(UTC)
            blocker.resolution_note = "Underlying deterministic readiness condition now passes."
            blocker.row_version += 1
            changes.append(f"RESOLVED:{fingerprint}")
    session.flush()
    if changes:
        append_audit_event(
            session,
            package_id=package_id,
            event_type="SYSTEM_BLOCKERS_REFRESHED",
            actor_type=ActorType.SYSTEM,
            actor_id="readiness-engine",
            subject_type="acquisition_package",
            subject_id=str(package_id),
            payload={"changes": changes},
        )
    return changes


def _hierarchy_is_valid(entities: list[Entity]) -> bool:
    ids = {entity.id for entity in entities}
    parent_by_id = {entity.id: entity.parent_id for entity in entities}
    if any(parent is not None and parent not in ids for parent in parent_by_id.values()):
        return False
    for entity_id in ids:
        seen: set[UUID] = set()
        current: UUID | None = entity_id
        while current is not None:
            if current in seen:
                return False
            seen.add(current)
            current = parent_by_id[current]
    return True


def _readiness_snapshot(
    session: Session, package_id: UUID
) -> tuple[list[EntityReadinessView], str]:
    entities = session.scalars(
        select(Entity).where(Entity.package_id == package_id).order_by(Entity.external_id)
    ).all()
    hierarchy_valid = _hierarchy_is_valid(list(entities))
    accounts = session.scalars(
        select(SourceAccount)
        .join(SourceAccount.entity)
        .where(Entity.package_id == package_id)
        .options(selectinload(SourceAccount.opening_balance))
        .order_by(SourceAccount.code)
    ).all()
    accounts_by_entity: dict[UUID, list[SourceAccount]] = defaultdict(list)
    for account in accounts:
        accounts_by_entity[account.entity_id].append(account)
    approved_source_ids = set(
        session.scalars(
            select(MappingSuggestion.source_account_id)
            .join(MappingSuggestion.source_account)
            .join(SourceAccount.entity)
            .where(
                Entity.package_id == package_id,
                MappingSuggestion.status == MappingStatus.APPROVED.value,
            )
        ).all()
    )
    open_blockers = session.scalars(
        select(Blocker).where(
            Blocker.package_id == package_id,
            Blocker.state == BlockerState.OPEN.value,
            Blocker.severity == BlockerSeverity.BLOCKING.value,
        )
    ).all()
    package_blockers = [blocker for blocker in open_blockers if blocker.entity_id is None]
    blockers_by_entity: dict[UUID, list[Blocker]] = defaultdict(list)
    for blocker in open_blockers:
        if blocker.entity_id is not None:
            blockers_by_entity[blocker.entity_id].append(blocker)

    output: list[EntityReadinessView] = []
    hash_material: list[dict[str, Any]] = []
    for entity in entities:
        entity_accounts = accounts_by_entity[entity.id]
        entries = [
            (
                account.code,
                account.opening_balance.debit_cents,
                account.opening_balance.credit_cents,
            )
            for account in entity_accounts
            if account.opening_balance is not None
        ]
        tie = compute_tie_out([account.code for account in entity_accounts], entries)
        mapping_complete = bool(entity_accounts) and all(
            account.id in approved_source_ids for account in entity_accounts
        )
        blockers = [*package_blockers, *blockers_by_entity[entity.id]]
        checks = [
            ReadinessCheckView(
                code="HIERARCHY_VALIDATED",
                passed=hierarchy_valid,
                detail=(
                    "Entity hierarchy references are valid and acyclic."
                    if hierarchy_valid
                    else "Entity hierarchy has a missing reference or cycle."
                ),
            ),
            ReadinessCheckView(
                code="SOURCE_ACCOUNTS_PRESENT",
                passed=bool(entity_accounts),
                detail=f"{len(entity_accounts)} source accounts imported.",
            ),
            ReadinessCheckView(
                code="OPENING_BALANCES_COMPLETE",
                passed=not tie.missing_account_codes and bool(entity_accounts),
                detail=(
                    "Every source account has an opening balance."
                    if not tie.missing_account_codes and entity_accounts
                    else "Missing opening balances: " + ", ".join(tie.missing_account_codes)
                ),
            ),
            ReadinessCheckView(
                code="TRIAL_BALANCE_TIED",
                passed=tie.is_balanced and bool(entity_accounts),
                detail=(
                    f"Debits and credits tie exactly at {tie.debit_cents} cents."
                    if tie.is_balanced and entity_accounts
                    else f"Debit-minus-credit difference is {tie.difference_cents} cents."
                ),
            ),
            ReadinessCheckView(
                code="ACCOUNT_MAPPINGS_APPROVED",
                passed=mapping_complete,
                detail=(
                    "Every source account has one human-approved canonical mapping."
                    if mapping_complete
                    else "At least one source account still needs human mapping approval."
                ),
            ),
            ReadinessCheckView(
                code="NO_BLOCKING_BLOCKERS",
                passed=not blockers,
                detail=(
                    "No open blocking exceptions remain."
                    if not blockers
                    else f"{len(blockers)} blocking exceptions remain open."
                ),
            ),
        ]
        status = (
            ReadinessStatus.DATA_PREPARATION_READY
            if all(check.passed for check in checks)
            else ReadinessStatus.NOT_READY
        )
        tie_view = TieOutView(
            debit_cents=tie.debit_cents,
            credit_cents=tie.credit_cents,
            difference_cents=tie.difference_cents,
            is_balanced=tie.is_balanced,
            entry_count=tie.entry_count,
            account_count=tie.account_count,
            missing_account_codes=tie.missing_account_codes,
        )
        view = EntityReadinessView(
            entity_id=entity.id,
            entity_external_id=entity.external_id,
            entity_name=entity.name,
            status=status,
            checks=checks,
            tie_out=tie_view,
        )
        output.append(view)
        hash_material.append(view.model_dump(mode="json"))
    return output, sha256_json(hash_material)


def evaluate_readiness(
    session: Session, package_id: UUID, *, refresh_blockers: bool = True
) -> PackageReadinessView:
    _package_or_raise(session, package_id)
    if refresh_blockers:
        refresh_system_blockers(session, package_id)
    entities, input_hash = _readiness_snapshot(session, package_id)
    computed_at = datetime.now(UTC)
    for entity in entities:
        session.add(
            ReadinessEvaluation(
                package_id=package_id,
                entity_id=entity.entity_id,
                status=entity.status.value,
                checks=[check.model_dump(mode="json") for check in entity.checks],
                input_hash=input_hash,
                computed_at=computed_at,
            )
        )
    package_status = (
        ReadinessStatus.DATA_PREPARATION_READY
        if entities
        and all(entity.status is ReadinessStatus.DATA_PREPARATION_READY for entity in entities)
        else ReadinessStatus.NOT_READY
    )
    package_evaluation = ReadinessEvaluation(
        package_id=package_id,
        entity_id=None,
        status=package_status.value,
        checks=[
            {
                "entities": [entity.model_dump(mode="json") for entity in entities],
            }
        ],
        input_hash=input_hash,
        computed_at=computed_at,
    )
    session.add(package_evaluation)
    session.flush()
    append_audit_event(
        session,
        package_id=package_id,
        event_type="READINESS_EVALUATED",
        actor_type=ActorType.SYSTEM,
        actor_id="readiness-engine",
        subject_type="readiness_evaluation",
        subject_id=str(package_evaluation.id),
        payload={
            "input_hash": input_hash,
            "status": package_status.value,
            "entities": [
                {
                    "entity_id": str(entity.entity_id),
                    "entity_external_id": entity.entity_external_id,
                    "status": entity.status.value,
                    "failed_checks": [check.code for check in entity.checks if not check.passed],
                }
                for entity in entities
            ],
        },
    )
    return PackageReadinessView(
        evaluation_id=package_evaluation.id,
        package_id=package_id,
        status=package_status,
        computed_at=computed_at,
        entities=entities,
    )


def get_latest_readiness(session: Session, package_id: UUID) -> PackageReadinessView:
    _package_or_raise(session, package_id)
    evaluation = session.scalars(
        select(ReadinessEvaluation)
        .where(
            ReadinessEvaluation.package_id == package_id,
            ReadinessEvaluation.entity_id.is_(None),
        )
        .order_by(ReadinessEvaluation.computed_at.desc(), ReadinessEvaluation.id.desc())
        .limit(1)
    ).one_or_none()
    if evaluation is None:
        raise NotFoundError("no readiness evaluation exists for this package")
    raw_entities = evaluation.checks[0].get("entities", []) if evaluation.checks else []
    entities = [EntityReadinessView.model_validate(value) for value in raw_entities]
    return PackageReadinessView(
        evaluation_id=evaluation.id,
        package_id=package_id,
        status=ReadinessStatus(evaluation.status),
        computed_at=evaluation.computed_at,
        entities=entities,
    )


def generate_sequence(
    session: Session, package_id: UUID, readiness: PackageReadinessView | None = None
) -> SequencePlanView:
    _package_or_raise(session, package_id)
    if readiness is None:
        readiness = get_latest_readiness(session, package_id)
    entities = session.scalars(
        select(Entity).where(Entity.package_id == package_id).order_by(Entity.external_id)
    ).all()
    readiness_by_entity = {item.entity_id: item for item in readiness.entities}
    blockers = session.scalars(
        select(Blocker).where(
            Blocker.package_id == package_id,
            Blocker.state == BlockerState.OPEN.value,
            Blocker.severity == BlockerSeverity.BLOCKING.value,
        )
    ).all()
    blocking_entity_ids = {blocker.entity_id for blocker in blockers if blocker.entity_id}
    package_blocked = any(blocker.entity_id is None for blocker in blockers)
    seeds: list[SequenceSeed] = []
    by_id = {entity.id: entity for entity in entities}
    for entity in entities:
        entity_readiness = readiness_by_entity[entity.id]
        checks = {check.code: check.passed for check in entity_readiness.checks}
        parent_external_id = (
            None if entity.parent_id is None else by_id[entity.parent_id].external_id
        )
        seeds.append(
            SequenceSeed(
                entity_external_id=entity.external_id,
                entity_name=entity.name,
                parent_external_id=parent_external_id,
                mapping_complete=checks["ACCOUNT_MAPPINGS_APPROVED"],
                tie_out_complete=(
                    checks["OPENING_BALANCES_COMPLETE"] and checks["TRIAL_BALANCE_TIED"]
                ),
                blockers_clear=(not package_blocked and entity.id not in blocking_entity_ids),
                readiness_complete=(
                    entity_readiness.status is ReadinessStatus.DATA_PREPARATION_READY
                ),
            )
        )
    steps = build_sequence(seeds)
    serialized_steps = sequence_to_dicts(steps)
    latest_version = session.scalar(
        select(func.max(SequencePlan.version)).where(SequencePlan.package_id == package_id)
    )
    version = int(latest_version or 0) + 1
    input_hash = sha256_json(
        {
            "readiness_evaluation_id": str(readiness.evaluation_id),
            "steps": serialized_steps,
        }
    )
    plan = SequencePlan(
        package_id=package_id,
        version=version,
        input_hash=input_hash,
        steps=serialized_steps,
        created_at=datetime.now(UTC),
    )
    session.add(plan)
    session.flush()
    append_audit_event(
        session,
        package_id=package_id,
        event_type="ONBOARDING_SEQUENCE_GENERATED",
        actor_type=ActorType.SYSTEM,
        actor_id="sequence-engine",
        subject_type="sequence_plan",
        subject_id=str(plan.id),
        payload={
            "version": version,
            "input_hash": input_hash,
            "readiness_evaluation_id": str(readiness.evaluation_id),
            "step_count": len(serialized_steps),
            "blocked_step_count": sum(1 for step in serialized_steps if step["state"] == "BLOCKED"),
        },
    )
    return SequencePlanView(
        plan_id=plan.id,
        package_id=package_id,
        version=plan.version,
        created_at=plan.created_at,
        steps=[SequenceStepView.model_validate(step) for step in serialized_steps],
    )


def get_latest_sequence(session: Session, package_id: UUID) -> SequencePlanView:
    _package_or_raise(session, package_id)
    plan = session.scalars(
        select(SequencePlan)
        .where(SequencePlan.package_id == package_id)
        .order_by(SequencePlan.version.desc())
        .limit(1)
    ).one_or_none()
    if plan is None:
        raise NotFoundError("no onboarding sequence exists for this package")
    return SequencePlanView(
        plan_id=plan.id,
        package_id=package_id,
        version=plan.version,
        created_at=plan.created_at,
        steps=[SequenceStepView.model_validate(step) for step in plan.steps],
    )


def recompute_package(session: Session, package_id: UUID) -> PackageReadinessView:
    readiness = evaluate_readiness(session, package_id)
    generate_sequence(session, package_id, readiness)
    session.commit()
    return readiness


def _recalculate_package(session: Session, package_id: UUID, *, reason: str) -> None:
    refresh_system_blockers(session, package_id)
    readiness = evaluate_readiness(session, package_id, refresh_blockers=False)
    plan = generate_sequence(session, package_id, readiness)
    append_audit_event(
        session,
        package_id=package_id,
        event_type="PACKAGE_CONTROL_STATE_RECALCULATED",
        actor_type=ActorType.SYSTEM,
        actor_id="control-plane",
        subject_type="acquisition_package",
        subject_id=str(package_id),
        payload={
            "reason": reason,
            "readiness_evaluation_id": str(readiness.evaluation_id),
            "sequence_plan_id": str(plan.plan_id),
            "sequence_plan_version": plan.version,
        },
    )


def list_audit_events(session: Session, package_id: UUID) -> list[AuditEventView]:
    _package_or_raise(session, package_id)
    events = session.scalars(
        select(AuditEvent).where(AuditEvent.package_id == package_id).order_by(AuditEvent.sequence)
    ).all()
    return [
        AuditEventView(
            id=event.id,
            sequence=event.sequence,
            event_type=event.event_type,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            subject_type=event.subject_type,
            subject_id=event.subject_id,
            payload=event.payload,
            previous_hash=event.previous_hash,
            event_hash=event.event_hash,
            created_at=event.created_at,
        )
        for event in events
    ]


def verify_audit_chain(session: Session, package_id: UUID) -> AuditVerificationView:
    events = list_audit_events(session, package_id)
    previous_hash: str | None = None
    first_invalid: int | None = None
    expected_sequence = 1
    for event in events:
        content = _canonical_event_content(
            event_id=event.id,
            package_id=package_id,
            sequence=event.sequence,
            event_type=event.event_type,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            subject_type=event.subject_type,
            subject_id=event.subject_id,
            payload=dict(event.payload),
            previous_hash=event.previous_hash,
            created_at=event.created_at,
        )
        valid = (
            event.sequence == expected_sequence
            and event.previous_hash == previous_hash
            and event.event_hash == sha256_json(content)
        )
        if not valid:
            first_invalid = event.sequence
            break
        previous_hash = event.event_hash
        expected_sequence += 1
    return AuditVerificationView(
        package_id=package_id,
        valid=first_invalid is None,
        event_count=len(events),
        first_invalid_sequence=first_invalid,
    )
