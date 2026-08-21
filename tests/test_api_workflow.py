from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from acquisition_launchpad.enums import BlockerState, MappingStatus, ReadinessStatus
from acquisition_launchpad.models import AuditEvent


def import_fixture(
    client: TestClient,
    fixture_payload: dict[str, Any],
    *,
    idempotency_key: str = "horizon-v1",
) -> dict[str, Any]:
    response = client.post(
        "/v1/packages",
        headers={"Idempotency-Key": idempotency_key},
        json=fixture_payload,
    )
    assert response.status_code == 201, response.text
    return response.json()  # type: ignore[no-any-return]


def approve_one_mapping(client: TestClient, package_id: str, mapping: dict[str, Any]) -> None:
    response = client.post(
        f"/v1/packages/{package_id}/mappings/{mapping['id']}/approve",
        json={
            "actor_id": "guided-demo-reviewer",
            "expected_version": mapping["row_version"],
            "note": "Reviewed account name, type, and synthetic source evidence.",
        },
    )
    assert response.status_code == 200, response.text


def approve_best_mapping_per_source(client: TestClient, package_id: str) -> None:
    response = client.get(f"/v1/packages/{package_id}/mappings")
    assert response.status_code == 200
    mappings: list[dict[str, Any]] = response.json()
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for mapping in mappings:
        key = (mapping["entity_external_id"], mapping["source_account_code"])
        current = selected.get(key)
        if current is None or mapping["confidence"] > current["confidence"]:
            selected[key] = mapping
    assert len(selected) == 18
    for mapping in selected.values():
        approve_one_mapping(client, package_id, mapping)


def test_health_and_openapi(client: TestClient) -> None:
    assert client.get("/v1/health/live").json() == {"status": "ok"}
    assert client.get("/v1/health/ready").json() == {
        "status": "ready",
        "database": "reachable",
    }
    openapi = client.get("/openapi.json")
    assert openapi.status_code == 200
    assert "/v1/packages" in openapi.json()["paths"]


def test_import_is_versioned_replay_safe_and_queryable(
    client: TestClient, fixture_payload: dict[str, Any]
) -> None:
    imported = import_fixture(client, fixture_payload)
    package_id = imported["package_id"]
    assert imported["replayed"] is False
    assert len(imported["payload_hash"]) == 64

    replay = client.post(
        "/v1/packages",
        headers={"Idempotency-Key": "horizon-v1"},
        json=fixture_payload,
    )
    assert replay.status_code == 200
    assert replay.json()["package_id"] == package_id
    assert replay.json()["replayed"] is True

    package = client.get(f"/v1/packages/{package_id}")
    assert package.status_code == 200
    assert package.json()["name"] == "Horizon Group synthetic acquisition package"
    assert [entity["external_id"] for entity in package.json()["entities"]] == [
        "HORIZON",
        "LAKEVIEW",
        "NORTHSTAR",
    ]
    assert len(client.get("/v1/packages").json()) == 1

    canonical_accounts = client.get(f"/v1/packages/{package_id}/canonical-accounts").json()
    assert len(canonical_accounts) == 6
    assert canonical_accounts[0]["code"] == "1000"
    source_accounts = client.get(f"/v1/packages/{package_id}/source-accounts").json()
    assert len(source_accounts) == 18
    assert all(account["opening_balance_as_of"] == "2026-07-31" for account in source_accounts)
    assert all(account["approved_mapping"] is None for account in source_accounts)
    horizon_entity_id = next(
        entity["id"] for entity in package.json()["entities"] if entity["external_id"] == "HORIZON"
    )
    filtered = client.get(
        f"/v1/packages/{package_id}/source-accounts",
        params={"entity_id": horizon_entity_id},
    ).json()
    assert len(filtered) == 6
    assert {account["entity_external_id"] for account in filtered} == {"HORIZON"}


def test_idempotency_and_immutable_package_version_conflicts(
    client: TestClient, fixture_payload: dict[str, Any]
) -> None:
    import_fixture(client, fixture_payload)
    changed = deepcopy(fixture_payload)
    changed["name"] = "Changed content"
    reused_key = client.post(
        "/v1/packages",
        headers={"Idempotency-Key": "horizon-v1"},
        json=changed,
    )
    assert reused_key.status_code == 409
    assert reused_key.json()["error"]["code"] == "CONFLICT"

    changed_same_version = client.post(
        "/v1/packages",
        headers={"Idempotency-Key": "different-request-key"},
        json=changed,
    )
    assert changed_same_version.status_code == 409
    assert "different content" in changed_same_version.json()["error"]["message"]


def test_invalid_hierarchy_is_rejected_without_partial_import(
    client: TestClient, fixture_payload: dict[str, Any]
) -> None:
    invalid = deepcopy(fixture_payload)
    invalid["entities"][0]["parent_external_id"] = "NORTHSTAR"
    response = client.post(
        "/v1/packages",
        headers={"Idempotency-Key": "invalid-cycle"},
        json=invalid,
    )
    assert response.status_code == 422
    assert "cycle" in response.json()["error"]["message"]
    assert client.get("/v1/packages").json() == []


def test_readiness_requires_human_mapping_approval_and_exact_tie_out(
    client: TestClient, fixture_payload: dict[str, Any]
) -> None:
    package_id = import_fixture(client, fixture_payload)["package_id"]
    initial = client.get(f"/v1/packages/{package_id}/readiness")
    assert initial.status_code == 200
    assert initial.json()["status"] == ReadinessStatus.NOT_READY.value
    for entity in initial.json()["entities"]:
        assert entity["tie_out"]["is_balanced"] is True
        checks = {item["code"]: item["passed"] for item in entity["checks"]}
        assert checks["TRIAL_BALANCE_TIED"] is True
        assert checks["ACCOUNT_MAPPINGS_APPROVED"] is False

    blockers = client.get(f"/v1/packages/{package_id}/blockers").json()
    assert len([item for item in blockers if item["state"] == BlockerState.OPEN.value]) == 18
    assert {item["code"] for item in blockers} == {"UNAPPROVED_ACCOUNT_MAPPING"}

    approve_best_mapping_per_source(client, package_id)
    ready = client.get(f"/v1/packages/{package_id}/readiness")
    assert ready.json()["status"] == ReadinessStatus.DATA_PREPARATION_READY.value
    assert all(
        entity["status"] == ReadinessStatus.DATA_PREPARATION_READY.value
        for entity in ready.json()["entities"]
    )
    sequence = client.get(f"/v1/packages/{package_id}/sequence").json()
    assert len(sequence["steps"]) == 15
    assert {step["state"] for step in sequence["steps"]} == {"COMPLETE"}


def test_mapping_decision_enforces_type_version_and_single_approval(
    client: TestClient, fixture_payload: dict[str, Any]
) -> None:
    package_id = import_fixture(client, fixture_payload)["package_id"]
    mappings = client.get(f"/v1/packages/{package_id}/mappings").json()
    revenue_options = [
        item
        for item in mappings
        if item["entity_external_id"] == "HORIZON" and item["source_account_code"] == "HZ-410"
    ]
    assert len(revenue_options) == 2
    best = max(revenue_options, key=lambda item: item["confidence"])
    alternative = min(revenue_options, key=lambda item: item["confidence"])
    approve_one_mapping(client, package_id, best)

    stale = client.post(
        f"/v1/packages/{package_id}/mappings/{best['id']}/reject",
        json={"actor_id": "reviewer", "expected_version": 1, "note": "Stale view."},
    )
    assert stale.status_code == 409
    assert "version conflict" in stale.json()["error"]["message"]

    incompatible = client.post(
        f"/v1/packages/{package_id}/mappings/{alternative['id']}/approve",
        json={
            "actor_id": "reviewer",
            "expected_version": alternative["row_version"],
            "note": "This deliberately incompatible candidate must be rejected.",
        },
    )
    assert incompatible.status_code == 422
    assert "account types must match" in incompatible.json()["error"]["message"]

    cash_mapping = next(
        item
        for item in mappings
        if item["entity_external_id"] == "HORIZON" and item["source_account_code"] == "HZ-101"
    )
    receivable_mapping = next(
        item
        for item in mappings
        if item["entity_external_id"] == "HORIZON" and item["source_account_code"] == "HZ-115"
    )
    created = client.post(
        f"/v1/packages/{package_id}/mappings",
        json={
            "source_account_id": cash_mapping["source_account_id"],
            "canonical_account_id": receivable_mapping["canonical_account_id"],
            "confidence": 0.25,
            "rationale": "Synthetic same-type alternative for the decision-control test.",
            "actor_id": "reviewer",
        },
    )
    assert created.status_code == 201
    alternative_asset = created.json()
    approve_one_mapping(client, package_id, cash_mapping)
    approve_one_mapping(client, package_id, alternative_asset)
    refreshed = client.get(f"/v1/packages/{package_id}/mappings").json()
    by_id = {item["id"]: item for item in refreshed}
    assert by_id[cash_mapping["id"]]["status"] == MappingStatus.REJECTED.value
    assert by_id[alternative_asset["id"]]["status"] == MappingStatus.APPROVED.value


def test_unbalanced_and_missing_data_create_derived_blockers(
    client: TestClient, fixture_payload: dict[str, Any]
) -> None:
    unbalanced = deepcopy(fixture_payload)
    unbalanced["external_key"] = "unbalanced-package"
    unbalanced["trial_balance"][0]["debit_cents"] += 1
    unbalanced_package = import_fixture(client, unbalanced, idempotency_key="unbalanced-package")[
        "package_id"
    ]
    readiness = client.get(f"/v1/packages/{unbalanced_package}/readiness").json()
    horizon = next(
        item for item in readiness["entities"] if item["entity_external_id"] == "HORIZON"
    )
    assert horizon["tie_out"]["difference_cents"] == 1
    assert horizon["tie_out"]["is_balanced"] is False
    blockers = client.get(f"/v1/packages/{unbalanced_package}/blockers").json()
    assert "UNBALANCED_TRIAL_BALANCE" in {item["code"] for item in blockers}

    missing = deepcopy(fixture_payload)
    missing["external_key"] = "missing-balance-package"
    missing["trial_balance"] = missing["trial_balance"][1:]
    missing_package = import_fixture(client, missing, idempotency_key="missing-balance-package")[
        "package_id"
    ]
    blockers = client.get(f"/v1/packages/{missing_package}/blockers").json()
    missing_balance = [item for item in blockers if item["code"] == "MISSING_OPENING_BALANCE"]
    assert len(missing_balance) == 1
    assert "HZ-101" in missing_balance[0]["detail"]


def test_warning_blocker_does_not_override_deterministic_ready_gate(
    client: TestClient, fixture_payload: dict[str, Any]
) -> None:
    package_id = import_fixture(client, fixture_payload)["package_id"]
    approve_best_mapping_per_source(client, package_id)
    warning = client.post(
        f"/v1/packages/{package_id}/blockers",
        json={
            "entity_id": None,
            "source_account_id": None,
            "code": "OPTIONAL_REVIEW_NOTE",
            "severity": "WARNING",
            "title": "Optional review note",
            "detail": "Warnings are visible but do not masquerade as blocking conditions.",
            "actor_id": "reviewer",
        },
    )
    assert warning.status_code == 201
    readiness = client.get(f"/v1/packages/{package_id}/readiness").json()
    assert readiness["status"] == ReadinessStatus.DATA_PREPARATION_READY.value


def test_reject_mapping_and_explicit_recompute_are_audited(
    client: TestClient, fixture_payload: dict[str, Any]
) -> None:
    package_id = import_fixture(client, fixture_payload)["package_id"]
    mapping = client.get(f"/v1/packages/{package_id}/mappings").json()[0]
    rejected = client.post(
        f"/v1/packages/{package_id}/mappings/{mapping['id']}/reject",
        json={
            "actor_id": "reviewer",
            "expected_version": mapping["row_version"],
            "note": "Rejected after reviewing the synthetic evidence.",
        },
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == MappingStatus.REJECTED.value
    recomputed = client.post(f"/v1/packages/{package_id}/readiness/recompute")
    assert recomputed.status_code == 200
    event_types = {
        event["event_type"]
        for event in client.get(f"/v1/packages/{package_id}/audit-events").json()
    }
    assert "MAPPING_REJECTED" in event_types
    assert "READINESS_EVALUATED" in event_types


def test_manual_blocker_regresses_and_restores_readiness(
    client: TestClient, fixture_payload: dict[str, Any]
) -> None:
    package_id = import_fixture(client, fixture_payload)["package_id"]
    approve_best_mapping_per_source(client, package_id)
    assert client.get(f"/v1/packages/{package_id}/readiness").json()["status"] == (
        ReadinessStatus.DATA_PREPARATION_READY.value
    )

    created = client.post(
        f"/v1/packages/{package_id}/blockers",
        json={
            "entity_id": None,
            "source_account_id": None,
            "code": "CONTROLLER_REVIEW_REQUIRED",
            "severity": "BLOCKING",
            "title": "Controller review remains open",
            "detail": "Synthetic demonstration of a package-level human blocker.",
            "actor_id": "guided-demo-reviewer",
        },
    )
    assert created.status_code == 201
    blocker = created.json()
    assert client.get(f"/v1/packages/{package_id}/readiness").json()["status"] == (
        ReadinessStatus.NOT_READY.value
    )

    resolved = client.post(
        f"/v1/packages/{package_id}/blockers/{blocker['id']}/resolve",
        json={
            "actor_id": "guided-demo-reviewer",
            "expected_version": blocker["row_version"],
            "resolution_note": "Controller reviewed the synthetic evidence packet.",
        },
    )
    assert resolved.status_code == 200
    assert resolved.json()["state"] == BlockerState.RESOLVED.value
    assert client.get(f"/v1/packages/{package_id}/readiness").json()["status"] == (
        ReadinessStatus.DATA_PREPARATION_READY.value
    )


def test_system_blocker_cannot_be_manually_cleared(
    client: TestClient, fixture_payload: dict[str, Any]
) -> None:
    package_id = import_fixture(client, fixture_payload)["package_id"]
    blocker = client.get(f"/v1/packages/{package_id}/blockers").json()[0]
    response = client.post(
        f"/v1/packages/{package_id}/blockers/{blocker['id']}/resolve",
        json={
            "actor_id": "reviewer",
            "expected_version": blocker["row_version"],
            "resolution_note": "Attempt to bypass source evidence.",
        },
    )
    assert response.status_code == 409
    assert "derived from source data" in response.json()["error"]["message"]


def test_audit_chain_detects_tampering(
    client: TestClient,
    session: Session,
    fixture_payload: dict[str, Any],
) -> None:
    package_id = import_fixture(client, fixture_payload)["package_id"]
    verified = client.get(f"/v1/packages/{package_id}/audit-events/verify")
    assert verified.status_code == 200
    assert verified.json()["valid"] is True
    assert verified.json()["event_count"] >= 5

    first = session.scalars(
        select(AuditEvent)
        .where(AuditEvent.package_id == UUID(package_id))
        .order_by(AuditEvent.sequence)
        .limit(1)
    ).one()
    first.payload = {"tampered": True}
    session.commit()
    invalid = client.get(f"/v1/packages/{package_id}/audit-events/verify")
    assert invalid.json()["valid"] is False
    assert invalid.json()["first_invalid_sequence"] == 1
