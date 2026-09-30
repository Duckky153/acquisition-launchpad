"""Deterministic preparation of the public synthetic demonstration state.

The production domain never auto-approves a mapping. This module only plans which
explicit approval commands the local seed script must replay to materialize a
fictional, pre-reviewed demo history. The final HZ-115 decision is intentionally
left to the person running the demonstration.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from acquisition_launchpad.enums import MappingStatus
from acquisition_launchpad.errors import ValidationError

DEMO_FINAL_SOURCE_CODE = "HZ-115"
DEMO_EXPECTED_SOURCE_COUNT = 18
DEMO_SEED_ACTOR = "synthetic-demo-preparer"
DEMO_SEED_NOTE = (
    "Synthetic fixture history: source name, account type, and canonical target "
    "were pre-reviewed for the guided demo."
)


class DemoMapping(BaseModel):
    """The bounded mapping fields consumed from the public API."""

    model_config = ConfigDict(extra="ignore")

    id: str = Field(min_length=1)
    source_account_id: str = Field(min_length=1)
    source_account_code: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    status: MappingStatus
    row_version: int = Field(ge=1)


@dataclass(frozen=True)
class DemoSeedPlan:
    """Approval commands needed to reach the one-decision-left state."""

    approvals: tuple[DemoMapping, ...]
    final_mapping: DemoMapping
    approved_source_count: int
    final_decision_already_complete: bool


_mapping_list_adapter = TypeAdapter(list[DemoMapping])


def plan_demo_seed(raw_mappings: Any) -> DemoSeedPlan:
    """Validate API mappings and plan replay-safe demo preparation.

    Existing approved decisions are preserved. Every source other than HZ-115
    receives its highest-confidence still-suggested candidate. HZ-115 is never
    approved here: it remains the meaningful action performed by the demonstrator.
    """

    mappings = _mapping_list_adapter.validate_python(raw_mappings)
    by_source: dict[str, list[DemoMapping]] = {}
    for mapping in mappings:
        by_source.setdefault(mapping.source_account_id, []).append(mapping)

    if len(by_source) != DEMO_EXPECTED_SOURCE_COUNT:
        raise ValidationError(
            f"synthetic demo expected {DEMO_EXPECTED_SOURCE_COUNT} source accounts; "
            f"received {len(by_source)}"
        )

    final_groups = [
        candidates
        for candidates in by_source.values()
        if candidates[0].source_account_code == DEMO_FINAL_SOURCE_CODE
    ]
    if len(final_groups) != 1:
        raise ValidationError(
            f"synthetic demo requires exactly one {DEMO_FINAL_SOURCE_CODE} source account"
        )

    approvals: list[DemoMapping] = []
    approved_source_count = 0
    final_mapping: DemoMapping | None = None
    final_complete = False

    for candidates in by_source.values():
        source_code = candidates[0].source_account_code
        approved = [item for item in candidates if item.status is MappingStatus.APPROVED]
        if len(approved) > 1:
            raise ValidationError(f"source account {source_code} has multiple approved mappings")

        suggested = sorted(
            (item for item in candidates if item.status is MappingStatus.SUGGESTED),
            key=lambda item: (-item.confidence, item.id),
        )

        if source_code == DEMO_FINAL_SOURCE_CODE:
            if approved:
                final_mapping = approved[0]
                final_complete = True
                approved_source_count += 1
            elif suggested:
                final_mapping = suggested[0]
            else:
                raise ValidationError(
                    f"{DEMO_FINAL_SOURCE_CODE} has no approvable candidate; reset the demo volume"
                )
            continue

        if approved:
            approved_source_count += 1
            continue
        if not suggested:
            raise ValidationError(
                f"source account {source_code} has no approvable candidate; reset the demo volume"
            )
        approvals.append(suggested[0])

    if final_mapping is None:  # Defensive: final_groups above establishes this invariant.
        raise ValidationError(f"{DEMO_FINAL_SOURCE_CODE} demo mapping was not found")

    return DemoSeedPlan(
        approvals=tuple(sorted(approvals, key=lambda item: (item.source_account_code, item.id))),
        final_mapping=final_mapping,
        approved_source_count=approved_source_count,
        final_decision_already_complete=final_complete,
    )
