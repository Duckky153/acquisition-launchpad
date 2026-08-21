from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Any

from acquisition_launchpad.enums import SequenceStepState, SequenceStepType
from acquisition_launchpad.errors import ValidationError
from acquisition_launchpad.schemas import AcquisitionPackageInput, EntityInput


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def sha256_json(value: object) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def package_payload_hash(payload: AcquisitionPackageInput) -> str:
    return sha256_json(payload.model_dump(mode="json"))


def validate_entity_hierarchy(entities: list[EntityInput]) -> list[str]:
    """Validate references/cycles and return stable parent-before-child external IDs."""
    by_id: dict[str, EntityInput] = {}
    for entity in entities:
        if entity.external_id in by_id:
            raise ValidationError(f"duplicate entity external_id: {entity.external_id}")
        by_id[entity.external_id] = entity

    for entity in entities:
        parent_id = entity.parent_external_id
        if parent_id == entity.external_id:
            raise ValidationError(f"entity {entity.external_id} cannot be its own parent")
        if parent_id is not None and parent_id not in by_id:
            raise ValidationError(
                f"entity {entity.external_id} references missing parent {parent_id}"
            )

    visiting: set[str] = set()
    visited: set[str] = set()
    ordered: list[str] = []

    def visit(external_id: str) -> None:
        if external_id in visited:
            return
        if external_id in visiting:
            raise ValidationError(f"entity hierarchy contains a cycle at {external_id}")
        visiting.add(external_id)
        parent_id = by_id[external_id].parent_external_id
        if parent_id is not None:
            visit(parent_id)
        visiting.remove(external_id)
        visited.add(external_id)
        ordered.append(external_id)

    for entity_id in sorted(by_id):
        visit(entity_id)
    return ordered


def validate_package_references(payload: AcquisitionPackageInput) -> None:
    entity_ids = {entity.external_id for entity in payload.entities}
    if len(entity_ids) != len(payload.entities):
        raise ValidationError("entity external IDs must be unique")

    canonical_codes = [account.code for account in payload.canonical_accounts]
    if len(set(canonical_codes)) != len(canonical_codes):
        raise ValidationError("canonical account codes must be unique")

    source_keys = [
        (account.entity_external_id, account.code) for account in payload.source_accounts
    ]
    if len(set(source_keys)) != len(source_keys):
        raise ValidationError("source account codes must be unique within each entity")

    for account in payload.source_accounts:
        if account.entity_external_id not in entity_ids:
            raise ValidationError(
                f"source account {account.code} references missing entity "
                f"{account.entity_external_id}"
            )

    balance_keys: set[tuple[str, str]] = set()
    source_key_set = set(source_keys)
    for entry in payload.trial_balance:
        key = (entry.entity_external_id, entry.source_account_code)
        if key not in source_key_set:
            raise ValidationError(
                f"trial balance references missing source account {key[0]}/{key[1]}"
            )
        if key in balance_keys:
            raise ValidationError(f"duplicate trial-balance row for {key[0]}/{key[1]}")
        balance_keys.add(key)

    suggestion_keys: set[tuple[str, str, str]] = set()
    canonical_set = set(canonical_codes)
    for suggestion in payload.mapping_suggestions:
        source_key = (suggestion.entity_external_id, suggestion.source_account_code)
        if source_key not in source_key_set:
            raise ValidationError(
                "mapping suggestion references missing source account "
                f"{source_key[0]}/{source_key[1]}"
            )
        if suggestion.canonical_account_code not in canonical_set:
            raise ValidationError(
                "mapping suggestion references missing canonical account "
                f"{suggestion.canonical_account_code}"
            )
        suggestion_key = (*source_key, suggestion.canonical_account_code)
        if suggestion_key in suggestion_keys:
            raise ValidationError(
                "duplicate mapping suggestion for "
                f"{source_key[0]}/{source_key[1]} -> {suggestion.canonical_account_code}"
            )
        suggestion_keys.add(suggestion_key)


@dataclass(frozen=True)
class TieOut:
    debit_cents: int
    credit_cents: int
    difference_cents: int
    is_balanced: bool
    entry_count: int
    account_count: int
    missing_account_codes: list[str]


def compute_tie_out(account_codes: list[str], entries: list[tuple[str, int, int]]) -> TieOut:
    debit_cents = 0
    credit_cents = 0
    seen: set[str] = set()
    for account_code, debit, credit in entries:
        if debit < 0 or credit < 0:
            raise ValidationError("trial-balance values cannot be negative")
        if debit > 0 and credit > 0:
            raise ValidationError(
                f"trial-balance account {account_code} cannot have both debit and credit"
            )
        if account_code in seen:
            raise ValidationError(f"duplicate trial-balance account: {account_code}")
        seen.add(account_code)
        debit_cents += debit
        credit_cents += credit

    missing = sorted(set(account_codes) - seen)
    difference = debit_cents - credit_cents
    return TieOut(
        debit_cents=debit_cents,
        credit_cents=credit_cents,
        difference_cents=difference,
        is_balanced=(difference == 0 and not missing),
        entry_count=len(entries),
        account_count=len(account_codes),
        missing_account_codes=missing,
    )


@dataclass(frozen=True)
class SequenceSeed:
    entity_external_id: str
    entity_name: str
    parent_external_id: str | None
    mapping_complete: bool
    tie_out_complete: bool
    blockers_clear: bool
    readiness_complete: bool


@dataclass(frozen=True)
class SequenceStep:
    key: str
    entity_external_id: str
    entity_name: str
    step_type: SequenceStepType
    state: SequenceStepState
    depends_on: list[str]
    blocked_by: list[str]
    order: int


def _step_key(entity_id: str, step_type: SequenceStepType) -> str:
    return f"{entity_id}:{step_type.value.lower()}"


def build_sequence(seeds: list[SequenceSeed]) -> list[SequenceStep]:
    """Build and topologically order an onboarding plan from explicit dependencies."""
    if not seeds:
        return []
    seed_by_id = {seed.entity_external_id: seed for seed in seeds}
    if len(seed_by_id) != len(seeds):
        raise ValidationError("sequence seed entity IDs must be unique")

    raw: dict[str, dict[str, Any]] = {}
    for seed in seeds:
        parent = seed.parent_external_id
        if parent is not None and parent not in seed_by_id:
            raise ValidationError(f"sequence references missing parent {parent}")

        intake_key = _step_key(seed.entity_external_id, SequenceStepType.INTAKE)
        mapping_key = _step_key(seed.entity_external_id, SequenceStepType.MAP_ACCOUNTS)
        tie_out_key = _step_key(seed.entity_external_id, SequenceStepType.TIE_OUT)
        blockers_key = _step_key(seed.entity_external_id, SequenceStepType.RESOLVE_BLOCKERS)
        readiness_key = _step_key(seed.entity_external_id, SequenceStepType.DATA_PREPARATION_READY)
        intake_dependencies = (
            [_step_key(parent, SequenceStepType.INTAKE)] if parent is not None else []
        )
        mapping_dependencies = [intake_key]
        if parent is not None:
            mapping_dependencies.append(_step_key(parent, SequenceStepType.MAP_ACCOUNTS))

        specifications = [
            (intake_key, SequenceStepType.INTAKE, True, intake_dependencies),
            (
                mapping_key,
                SequenceStepType.MAP_ACCOUNTS,
                seed.mapping_complete,
                mapping_dependencies,
            ),
            (tie_out_key, SequenceStepType.TIE_OUT, seed.tie_out_complete, [intake_key]),
            (
                blockers_key,
                SequenceStepType.RESOLVE_BLOCKERS,
                seed.blockers_clear,
                [mapping_key, tie_out_key],
            ),
            (
                readiness_key,
                SequenceStepType.DATA_PREPARATION_READY,
                seed.readiness_complete,
                [blockers_key],
            ),
        ]
        for key, step_type, intrinsically_complete, dependencies in specifications:
            raw[key] = {
                "key": key,
                "entity_external_id": seed.entity_external_id,
                "entity_name": seed.entity_name,
                "step_type": step_type,
                "intrinsically_complete": intrinsically_complete,
                "depends_on": dependencies,
            }

    ordered_keys: list[str] = []
    temporary: set[str] = set()
    permanent: set[str] = set()

    def visit(key: str) -> None:
        if key in permanent:
            return
        if key in temporary:
            raise ValidationError(f"onboarding sequence contains a cycle at {key}")
        if key not in raw:
            raise ValidationError(f"onboarding sequence references unknown step {key}")
        temporary.add(key)
        for dependency in raw[key]["depends_on"]:
            visit(str(dependency))
        temporary.remove(key)
        permanent.add(key)
        ordered_keys.append(key)

    for key in sorted(raw):
        visit(key)

    states: dict[str, SequenceStepState] = {}
    output: list[SequenceStep] = []
    for order, key in enumerate(ordered_keys, start=1):
        item = raw[key]
        dependencies = [str(value) for value in item["depends_on"]]
        blocked_by = [dep for dep in dependencies if states[dep] != SequenceStepState.COMPLETE]
        if blocked_by:
            state = SequenceStepState.BLOCKED
        elif bool(item["intrinsically_complete"]):
            state = SequenceStepState.COMPLETE
        else:
            state = SequenceStepState.READY
        states[key] = state
        output.append(
            SequenceStep(
                key=key,
                entity_external_id=str(item["entity_external_id"]),
                entity_name=str(item["entity_name"]),
                step_type=SequenceStepType(item["step_type"]),
                state=state,
                depends_on=dependencies,
                blocked_by=blocked_by,
                order=order,
            )
        )
    return output


def sequence_to_dicts(steps: list[SequenceStep]) -> list[dict[str, Any]]:
    return [
        {
            **asdict(step),
            "step_type": step.step_type.value,
            "state": step.state.value,
        }
        for step in steps
    ]
