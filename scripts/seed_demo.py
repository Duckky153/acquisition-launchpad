#!/usr/bin/env python3
"""Replay-safe loader and preparer for the guided synthetic acquisition demo."""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from pydantic import ValidationError as PydanticValidationError

from acquisition_launchpad.demo_seed import (
    DEMO_EXPECTED_SOURCE_COUNT,
    DEMO_FINAL_SOURCE_CODE,
    DEMO_SEED_ACTOR,
    DEMO_SEED_NOTE,
    plan_demo_seed,
)
from acquisition_launchpad.errors import ValidationError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-base", default="http://127.0.0.1:8011")
    parser.add_argument(
        "--fixture",
        type=Path,
        default=Path("fixtures/horizon_acquisition_v1.json"),
    )
    parser.add_argument("--attempts", type=int, default=30)
    return parser.parse_args()


def _request_json(
    url: str,
    *,
    method: str = "GET",
    payload: bytes | None = None,
    headers: dict[str, str] | None = None,
    attempts: int = 1,
) -> Any:
    request = urllib.request.Request(
        url,
        data=payload,
        headers=headers or {},
        method=method,
    )
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=8) as response:
                if response.status < 200 or response.status >= 300:
                    raise RuntimeError(f"unexpected response: HTTP {response.status}")
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"request rejected: HTTP {error.code}: {detail}") from error
        except urllib.error.URLError:
            if attempt == attempts:
                raise
            time.sleep(1)
    raise RuntimeError("unreachable request retry state")


def _get_list(api_base: str, path: str) -> list[dict[str, Any]]:
    raw = _request_json(f"{api_base}{path}")
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise RuntimeError(f"{path} did not return a JSON object list")
    return raw


def _get_object(api_base: str, path: str) -> dict[str, Any]:
    raw = _request_json(f"{api_base}{path}")
    if not isinstance(raw, dict):
        raise RuntimeError(f"{path} did not return a JSON object")
    return raw


def _post_object(api_base: str, path: str, body: dict[str, object]) -> dict[str, Any]:
    raw = _request_json(
        f"{api_base}{path}",
        method="POST",
        payload=json.dumps(body, separators=(",", ":")).encode(),
        headers={"Content-Type": "application/json"},
    )
    if not isinstance(raw, dict):
        raise RuntimeError(f"{path} did not return a JSON object")
    return raw


def _prepare_one_decision_left(api_base: str, package_id: str) -> dict[str, object]:
    mappings_path = f"/v1/packages/{package_id}/mappings"
    plan = plan_demo_seed(_get_list(api_base, mappings_path))

    for mapping in plan.approvals:
        _post_object(
            api_base,
            f"/v1/packages/{package_id}/mappings/{mapping.id}/approve",
            {
                "actor_id": DEMO_SEED_ACTOR,
                "expected_version": mapping.row_version,
                "note": DEMO_SEED_NOTE,
            },
        )

    final_plan = plan_demo_seed(_get_list(api_base, mappings_path))
    blockers = _get_list(api_base, f"/v1/packages/{package_id}/blockers")
    readiness = _get_object(api_base, f"/v1/packages/{package_id}/readiness")
    sequence = _get_object(api_base, f"/v1/packages/{package_id}/sequence")
    audit = _get_object(api_base, f"/v1/packages/{package_id}/audit-events/verify")

    approved_count = final_plan.approved_source_count
    open_blockers = [item for item in blockers if item.get("state") == "OPEN"]
    sequence_steps = sequence.get("steps")
    if not isinstance(sequence_steps, list) or len(sequence_steps) != 15:
        raise RuntimeError("guided demo sequence did not contain the expected 15 steps")
    sequence_state_counts = {
        state: sum(
            1 for step in sequence_steps if isinstance(step, dict) and step.get("state") == state
        )
        for state in ("COMPLETE", "READY", "BLOCKED")
    }
    if audit.get("valid") is not True:
        raise RuntimeError("guided demo audit chain did not verify")

    if final_plan.final_decision_already_complete:
        if approved_count != DEMO_EXPECTED_SOURCE_COUNT:
            raise RuntimeError("completed demo does not contain 18 approved source accounts")
        if readiness.get("status") != "DATA_PREPARATION_READY" or open_blockers:
            raise RuntimeError("completed demo state is inconsistent with deterministic readiness")
        if sequence_state_counts != {"COMPLETE": 15, "READY": 0, "BLOCKED": 0}:
            raise RuntimeError(
                "completed demo sequence is inconsistent with deterministic readiness"
            )
        return {
            "demo_state": "completed",
            "approved_source_count": approved_count,
            "open_blocker_count": len(open_blockers),
            "final_source_code": DEMO_FINAL_SOURCE_CODE,
        }

    if final_plan.approvals:
        raise RuntimeError("guided demo preparation did not finish all historical decisions")
    if approved_count != DEMO_EXPECTED_SOURCE_COUNT - 1:
        raise RuntimeError("guided demo must have exactly 17 approved source accounts")
    if readiness.get("status") != "NOT_READY":
        raise RuntimeError("guided demo must remain NOT_READY before the final human decision")
    if len(open_blockers) != 1:
        raise RuntimeError("guided demo must have exactly one open blocker")
    if open_blockers[0].get("source_account_id") != final_plan.final_mapping.source_account_id:
        raise RuntimeError("the remaining blocker is not tied to the guided HZ-115 decision")
    if sequence_state_counts != {"COMPLETE": 6, "READY": 1, "BLOCKED": 8}:
        raise RuntimeError(
            "one-decision-left sequence is inconsistent with deterministic readiness"
        )

    return {
        "demo_state": "one-decision-left",
        "approved_source_count": approved_count,
        "open_blocker_count": len(open_blockers),
        "final_source_code": DEMO_FINAL_SOURCE_CODE,
    }


def load(api_base: str, fixture: Path, attempts: int) -> dict[str, object]:
    normalized_base = api_base.rstrip("/")
    raw_result = _request_json(
        f"{normalized_base}/v1/packages",
        method="POST",
        payload=fixture.read_bytes(),
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": "horizon-demo-v1",
        },
        attempts=attempts,
    )
    if not isinstance(raw_result, dict) or not isinstance(raw_result.get("package_id"), str):
        raise RuntimeError("seed response did not contain a string package_id")

    result: dict[str, object] = dict(raw_result)
    result.update(_prepare_one_decision_left(normalized_base, raw_result["package_id"]))
    return result


def main() -> int:
    args = parse_args()
    try:
        result = load(args.api_base, args.fixture, args.attempts)
    except (
        OSError,
        RuntimeError,
        urllib.error.URLError,
        ValidationError,
        PydanticValidationError,
    ) as error:
        print(f"Synthetic demo seed failed: {error}", file=sys.stderr)
        return 1

    replayed = bool(result.get("replayed", False))
    print(f"Synthetic demo package {'replayed' if replayed else 'created'}: {result['package_id']}")
    if result["demo_state"] == "one-decision-left":
        print(
            "Guided demo ready: 17/18 mappings approved, one HZ-115 decision and "
            "one matching blocker remain."
        )
    else:
        print(
            "Guided demo was previously completed and was preserved. Run the documented "
            "demo reset to restore the one-decision-left starting state."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
