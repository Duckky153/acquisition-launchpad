from __future__ import annotations

from copy import deepcopy
from typing import Any

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError as PydanticValidationError

from acquisition_launchpad.domain import validate_package_references
from acquisition_launchpad.errors import ValidationError
from acquisition_launchpad.schemas import AcquisitionPackageInput, TrialBalanceInput


@pytest.mark.parametrize(
    "mutation, message",
    [
        (
            lambda payload: payload["canonical_accounts"].append(
                deepcopy(payload["canonical_accounts"][0])
            ),
            "canonical account codes must be unique",
        ),
        (
            lambda payload: payload["source_accounts"].append(
                deepcopy(payload["source_accounts"][0])
            ),
            "source account codes must be unique",
        ),
        (
            lambda payload: payload["trial_balance"].append(deepcopy(payload["trial_balance"][0])),
            "duplicate trial-balance row",
        ),
        (
            lambda payload: payload["mapping_suggestions"].append(
                deepcopy(payload["mapping_suggestions"][0])
            ),
            "duplicate mapping suggestion",
        ),
    ],
)
def test_cross_record_duplicates_are_rejected(
    fixture_payload: dict[str, Any],
    mutation: Any,
    message: str,
) -> None:
    changed = deepcopy(fixture_payload)
    mutation(changed)
    payload = AcquisitionPackageInput.model_validate(changed)
    with pytest.raises(ValidationError, match=message):
        validate_package_references(payload)


def test_references_to_missing_records_are_rejected(fixture_payload: dict[str, Any]) -> None:
    changed = deepcopy(fixture_payload)
    changed["mapping_suggestions"][0]["canonical_account_code"] = "MISSING"
    payload = AcquisitionPackageInput.model_validate(changed)
    with pytest.raises(ValidationError, match="missing canonical account"):
        validate_package_references(payload)

    changed = deepcopy(fixture_payload)
    changed["trial_balance"][0]["source_account_code"] = "MISSING"
    payload = AcquisitionPackageInput.model_validate(changed)
    with pytest.raises(ValidationError, match="missing source account"):
        validate_package_references(payload)


def test_trial_balance_row_rejects_two_sided_and_unknown_fields() -> None:
    with pytest.raises(PydanticValidationError, match="cannot contain both"):
        TrialBalanceInput(
            entity_external_id="ENTITY",
            source_account_code="1000",
            debit_cents=1,
            credit_cents=1,
        )
    with pytest.raises(PydanticValidationError, match="Extra inputs are not permitted"):
        TrialBalanceInput.model_validate(
            {
                "entity_external_id": "ENTITY",
                "source_account_code": "1000",
                "debit_cents": 1,
                "credit_cents": 0,
                "untrusted_extra": "rejected",
            }
        )


def test_structured_not_found_error(client: TestClient) -> None:
    response = client.get("/v1/packages/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"
