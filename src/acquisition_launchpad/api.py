from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response, status
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from acquisition_launchpad.db import get_session
from acquisition_launchpad.enums import MappingStatus
from acquisition_launchpad.models import AcquisitionPackage
from acquisition_launchpad.schemas import (
    AcquisitionPackageInput,
    AuditEventView,
    AuditVerificationView,
    BlockerResolution,
    BlockerView,
    CanonicalAccountView,
    ImportResult,
    ManualBlockerCreate,
    MappingCreate,
    MappingDecision,
    MappingView,
    PackageDetail,
    PackageReadinessView,
    SequencePlanView,
    SourceAccountView,
)
from acquisition_launchpad.services import (
    create_manual_blocker,
    create_mapping_suggestion,
    decide_mapping,
    get_latest_readiness,
    get_latest_sequence,
    get_package,
    import_package,
    list_audit_events,
    list_blockers,
    list_canonical_accounts,
    list_mappings,
    list_source_accounts,
    recompute_package,
    resolve_blocker,
    verify_audit_chain,
)

SessionDependency = Annotated[Session, Depends(get_session)]

router = APIRouter(prefix="/v1")


@router.get("/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ready", tags=["health"])
def readiness_probe(session: SessionDependency) -> dict[str, str]:
    session.execute(text("SELECT 1"))
    return {"status": "ready", "database": "reachable"}


@router.post(
    "/packages",
    response_model=ImportResult,
    status_code=status.HTTP_201_CREATED,
    tags=["package intake"],
)
def import_acquisition_package(
    payload: AcquisitionPackageInput,
    session: SessionDependency,
    response: Response,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=1)],
) -> ImportResult:
    result = import_package(session, payload, idempotency_key)
    if result.replayed:
        response.status_code = status.HTTP_200_OK
    return result


@router.get("/packages", response_model=list[PackageDetail], tags=["packages"])
def list_acquisition_packages(session: SessionDependency) -> list[PackageDetail]:
    package_ids = session.scalars(
        select(AcquisitionPackage.id).order_by(
            AcquisitionPackage.created_at.desc(), AcquisitionPackage.id
        )
    ).all()
    return [get_package(session, package_id) for package_id in package_ids]


@router.get("/packages/{package_id}", response_model=PackageDetail, tags=["packages"])
def retrieve_package(package_id: UUID, session: SessionDependency) -> PackageDetail:
    return get_package(session, package_id)


@router.get(
    "/packages/{package_id}/canonical-accounts",
    response_model=list[CanonicalAccountView],
    tags=["accounts"],
)
def retrieve_canonical_accounts(
    package_id: UUID, session: SessionDependency
) -> list[CanonicalAccountView]:
    return list_canonical_accounts(session, package_id)


@router.get(
    "/packages/{package_id}/source-accounts",
    response_model=list[SourceAccountView],
    tags=["accounts"],
)
def retrieve_source_accounts(
    package_id: UUID,
    session: SessionDependency,
    entity_id: UUID | None = None,
) -> list[SourceAccountView]:
    return list_source_accounts(session, package_id, entity_id)


@router.get(
    "/packages/{package_id}/mappings",
    response_model=list[MappingView],
    tags=["account mappings"],
)
def retrieve_mappings(package_id: UUID, session: SessionDependency) -> list[MappingView]:
    return list_mappings(session, package_id)


@router.post(
    "/packages/{package_id}/mappings",
    response_model=MappingView,
    status_code=status.HTTP_201_CREATED,
    tags=["account mappings"],
)
def add_mapping_suggestion(
    package_id: UUID, command: MappingCreate, session: SessionDependency
) -> MappingView:
    return create_mapping_suggestion(session, package_id, command)


@router.post(
    "/packages/{package_id}/mappings/{mapping_id}/approve",
    response_model=MappingView,
    tags=["account mappings"],
)
def approve_mapping(
    package_id: UUID,
    mapping_id: UUID,
    command: MappingDecision,
    session: SessionDependency,
) -> MappingView:
    return decide_mapping(session, package_id, mapping_id, command, MappingStatus.APPROVED)


@router.post(
    "/packages/{package_id}/mappings/{mapping_id}/reject",
    response_model=MappingView,
    tags=["account mappings"],
)
def reject_mapping(
    package_id: UUID,
    mapping_id: UUID,
    command: MappingDecision,
    session: SessionDependency,
) -> MappingView:
    return decide_mapping(session, package_id, mapping_id, command, MappingStatus.REJECTED)


@router.get(
    "/packages/{package_id}/blockers",
    response_model=list[BlockerView],
    tags=["blockers"],
)
def retrieve_blockers(package_id: UUID, session: SessionDependency) -> list[BlockerView]:
    return list_blockers(session, package_id)


@router.post(
    "/packages/{package_id}/blockers",
    response_model=BlockerView,
    status_code=status.HTTP_201_CREATED,
    tags=["blockers"],
)
def add_manual_blocker(
    package_id: UUID, command: ManualBlockerCreate, session: SessionDependency
) -> BlockerView:
    return create_manual_blocker(session, package_id, command)


@router.post(
    "/packages/{package_id}/blockers/{blocker_id}/resolve",
    response_model=BlockerView,
    tags=["blockers"],
)
def resolve_manual_blocker(
    package_id: UUID,
    blocker_id: UUID,
    command: BlockerResolution,
    session: SessionDependency,
) -> BlockerView:
    return resolve_blocker(session, package_id, blocker_id, command)


@router.get(
    "/packages/{package_id}/readiness",
    response_model=PackageReadinessView,
    tags=["readiness"],
)
def retrieve_readiness(package_id: UUID, session: SessionDependency) -> PackageReadinessView:
    return get_latest_readiness(session, package_id)


@router.post(
    "/packages/{package_id}/readiness/recompute",
    response_model=PackageReadinessView,
    tags=["readiness"],
)
def recompute_readiness(package_id: UUID, session: SessionDependency) -> PackageReadinessView:
    return recompute_package(session, package_id)


@router.get(
    "/packages/{package_id}/sequence",
    response_model=SequencePlanView,
    tags=["onboarding sequence"],
)
def retrieve_sequence(package_id: UUID, session: SessionDependency) -> SequencePlanView:
    return get_latest_sequence(session, package_id)


@router.get(
    "/packages/{package_id}/audit-events",
    response_model=list[AuditEventView],
    tags=["audit"],
)
def retrieve_audit_events(package_id: UUID, session: SessionDependency) -> list[AuditEventView]:
    return list_audit_events(session, package_id)


@router.get(
    "/packages/{package_id}/audit-events/verify",
    response_model=AuditVerificationView,
    tags=["audit"],
)
def verify_package_audit_chain(
    package_id: UUID, session: SessionDependency
) -> AuditVerificationView:
    return verify_audit_chain(session, package_id)
