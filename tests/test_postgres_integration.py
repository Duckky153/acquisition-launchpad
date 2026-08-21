from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from acquisition_launchpad.enums import MappingStatus, ReadinessStatus
from acquisition_launchpad.schemas import AcquisitionPackageInput, MappingDecision, MappingView
from acquisition_launchpad.services import (
    decide_mapping,
    get_latest_readiness,
    import_package,
    list_mappings,
    verify_audit_chain,
)

ROOT = Path(__file__).resolve().parents[1]


def _postgres_url() -> str:
    url = os.environ.get("LAUNCHPAD_TEST_POSTGRES_URL")
    if url is None:
        pytest.skip("set LAUNCHPAD_TEST_POSTGRES_URL to run PostgreSQL integration tests")
    return url


@pytest.mark.postgres
def test_real_postgres_full_readiness_workflow() -> None:
    engine = create_engine(_postgres_url(), pool_pre_ping=True)
    run_id = uuid4().hex
    raw: dict[str, Any] = json.loads(
        (ROOT / "fixtures" / "horizon_acquisition_v1.json").read_text(encoding="utf-8")
    )
    payload_data = deepcopy(raw)
    payload_data["external_key"] = f"postgres-integration-{run_id}"
    payload = AcquisitionPackageInput.model_validate(payload_data)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with factory() as session:
            assert isinstance(session, Session)
            imported = import_package(session, payload, f"postgres-import-{run_id}")
            assert imported.replayed is False
            assert get_latest_readiness(session, imported.package_id).status is (
                ReadinessStatus.NOT_READY
            )

            selected: dict[tuple[str, str], MappingView] = {}
            for mapping in list_mappings(session, imported.package_id):
                key = (mapping.entity_external_id, mapping.source_account_code)
                current = selected.get(key)
                if current is None or mapping.confidence > current.confidence:
                    selected[key] = mapping
            assert len(selected) == 18
            for mapping in selected.values():
                decide_mapping(
                    session,
                    imported.package_id,
                    mapping.id,
                    MappingDecision(
                        actor_id="postgres-integration-reviewer",
                        expected_version=mapping.row_version,
                        note="Verified in the real PostgreSQL integration workflow.",
                    ),
                    MappingStatus.APPROVED,
                )

            assert get_latest_readiness(session, imported.package_id).status is (
                ReadinessStatus.DATA_PREPARATION_READY
            )
            verification = verify_audit_chain(session, imported.package_id)
            assert verification.valid
            assert verification.event_count >= 5 + (18 * 5)
    finally:
        with engine.begin() as connection:
            connection.execute(
                text("DELETE FROM acquisition_packages WHERE external_key = :external_key"),
                {"external_key": f"postgres-integration-{run_id}"},
            )
            connection.execute(
                text("DELETE FROM idempotency_records WHERE key = :key"),
                {"key": f"postgres-import-{run_id}"},
            )
        engine.dispose()
