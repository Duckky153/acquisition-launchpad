from __future__ import annotations

import pytest

from acquisition_launchpad.domain import (
    SequenceSeed,
    build_sequence,
    compute_tie_out,
    validate_entity_hierarchy,
)
from acquisition_launchpad.enums import SequenceStepState, SequenceStepType
from acquisition_launchpad.errors import ValidationError
from acquisition_launchpad.schemas import EntityInput


def entity(external_id: str, parent: str | None = None) -> EntityInput:
    return EntityInput(
        external_id=external_id,
        parent_external_id=parent,
        name=external_id,
        legal_name=f"{external_id} LLC (Synthetic)",
        currency="USD",
        source_system="Synthetic",
    )


def test_hierarchy_returns_parent_before_children() -> None:
    ordered = validate_entity_hierarchy(
        [entity("CHILD_B", "ROOT"), entity("ROOT"), entity("CHILD_A", "ROOT")]
    )
    assert ordered[0] == "ROOT"
    assert set(ordered[1:]) == {"CHILD_A", "CHILD_B"}


@pytest.mark.parametrize(
    "entities, message",
    [
        ([entity("ROOT", "ROOT")], "cannot be its own parent"),
        ([entity("CHILD", "MISSING")], "references missing parent"),
        ([entity("A", "B"), entity("B", "A")], "contains a cycle"),
        ([entity("A"), entity("A")], "duplicate entity external_id"),
    ],
)
def test_hierarchy_rejects_invalid_graphs(entities: list[EntityInput], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        validate_entity_hierarchy(entities)


def test_tie_out_requires_exact_equality_and_complete_accounts() -> None:
    tied = compute_tie_out(["1000", "2000"], [("1000", 10_001, 0), ("2000", 0, 10_001)])
    assert tied.is_balanced
    assert tied.difference_cents == 0

    one_cent_off = compute_tie_out(["1000", "2000"], [("1000", 10_001, 0), ("2000", 0, 10_000)])
    assert not one_cent_off.is_balanced
    assert one_cent_off.difference_cents == 1

    missing_but_net_zero = compute_tie_out(
        ["1000", "2000", "3000"], [("1000", 10_000, 0), ("2000", 0, 10_000)]
    )
    assert not missing_but_net_zero.is_balanced
    assert missing_but_net_zero.missing_account_codes == ["3000"]


def test_sequence_respects_parent_and_workflow_dependencies() -> None:
    steps = build_sequence(
        [
            SequenceSeed(
                entity_external_id="ROOT",
                entity_name="Root",
                parent_external_id=None,
                mapping_complete=False,
                tie_out_complete=True,
                blockers_clear=False,
                readiness_complete=False,
            ),
            SequenceSeed(
                entity_external_id="CHILD",
                entity_name="Child",
                parent_external_id="ROOT",
                mapping_complete=True,
                tie_out_complete=True,
                blockers_clear=True,
                readiness_complete=True,
            ),
        ]
    )
    by_key = {step.key: step for step in steps}
    assert by_key["ROOT:intake"].state is SequenceStepState.COMPLETE
    assert by_key["ROOT:map_accounts"].state is SequenceStepState.READY
    assert by_key["ROOT:resolve_blockers"].state is SequenceStepState.BLOCKED
    assert by_key["CHILD:map_accounts"].state is SequenceStepState.BLOCKED
    assert by_key["CHILD:map_accounts"].blocked_by == ["ROOT:map_accounts"]
    assert by_key["CHILD:data_preparation_ready"].step_type is (
        SequenceStepType.DATA_PREPARATION_READY
    )
    assert [step.order for step in steps] == list(range(1, len(steps) + 1))
