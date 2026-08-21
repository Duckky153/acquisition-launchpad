from __future__ import annotations

from typing import Any

import pytest

from acquisition_launchpad.demo_seed import (
    DEMO_FINAL_SOURCE_CODE,
    plan_demo_seed,
)
from acquisition_launchpad.errors import ValidationError


def _api_mappings(fixture_payload: dict[str, Any]) -> list[dict[str, object]]:
    source_ids = {
        (item["entity_external_id"], item["code"]): (
            f"source-{item['entity_external_id']}-{item['code']}"
        )
        for item in fixture_payload["source_accounts"]
    }
    return [
        {
            "id": f"mapping-{index}",
            "source_account_id": source_ids[
                (item["entity_external_id"], item["source_account_code"])
            ],
            "source_account_code": item["source_account_code"],
            "confidence": item["confidence"],
            "status": "SUGGESTED",
            "row_version": 1,
        }
        for index, item in enumerate(fixture_payload["mapping_suggestions"], start=1)
    ]


def test_demo_seed_plans_seventeen_historical_approvals_and_leaves_hz_115(
    fixture_payload: dict[str, Any],
) -> None:
    mappings = _api_mappings(fixture_payload)

    plan = plan_demo_seed(mappings)

    assert len(plan.approvals) == 17
    assert {item.source_account_code for item in plan.approvals} == {
        item["code"]
        for item in fixture_payload["source_accounts"]
        if item["code"] != DEMO_FINAL_SOURCE_CODE
    }
    assert plan.final_mapping.source_account_code == DEMO_FINAL_SOURCE_CODE
    assert plan.final_mapping.confidence == 0.98
    assert plan.approved_source_count == 0
    assert plan.final_decision_already_complete is False


def test_demo_seed_is_replay_safe_before_and_after_final_decision(
    fixture_payload: dict[str, Any],
) -> None:
    mappings = _api_mappings(fixture_payload)
    initial = plan_demo_seed(mappings)
    approved_ids = {item.id for item in initial.approvals}
    for mapping in mappings:
        if mapping["id"] in approved_ids:
            mapping["status"] = "APPROVED"
            mapping["row_version"] = 2

    prepared = plan_demo_seed(mappings)
    assert prepared.approvals == ()
    assert prepared.approved_source_count == 17
    assert prepared.final_decision_already_complete is False

    target_id = prepared.final_mapping.id
    next(item for item in mappings if item["id"] == target_id)["status"] = "APPROVED"
    completed = plan_demo_seed(mappings)
    assert completed.approvals == ()
    assert completed.approved_source_count == 18
    assert completed.final_decision_already_complete is True


def test_demo_seed_rejects_drifted_or_non_replayable_fixture(
    fixture_payload: dict[str, Any],
) -> None:
    mappings = _api_mappings(fixture_payload)
    without_one_source = [item for item in mappings if item["source_account_code"] != "LV-50"]
    with pytest.raises(ValidationError, match="expected 18 source accounts"):
        plan_demo_seed(without_one_source)

    for mapping in mappings:
        if mapping["source_account_code"] == DEMO_FINAL_SOURCE_CODE:
            mapping["status"] = "REJECTED"
    with pytest.raises(ValidationError, match="has no approvable candidate"):
        plan_demo_seed(mappings)
