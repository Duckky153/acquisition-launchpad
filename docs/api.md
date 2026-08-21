# Phase 1 API contract

The generated OpenAPI document at `/openapi.json` is authoritative for request and response
shapes. This page explains the intended workflow and mutation boundaries.

## Health and package intake

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/health/live` | Process liveness; does not imply database readiness. |
| `GET` | `/v1/health/ready` | Executes `SELECT 1` against the configured database. |
| `POST` | `/v1/packages` | Atomically validate and import schema `1.0`; requires `Idempotency-Key`. |
| `GET` | `/v1/packages` | List imported package versions. |
| `GET` | `/v1/packages/{package_id}` | Package and entity summary. |

An initial import returns `201`; an exact idempotent replay returns `200` with `replayed: true`.
A changed request using the same key, or changed content using an existing external key/version,
returns `409`.

## Account evidence and decisions

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/packages/{package_id}/canonical-accounts` | Complete canonical chart. |
| `GET` | `/v1/packages/{package_id}/source-accounts` | All source accounts, balances, suggestions, and approved target; optional `entity_id`. |
| `GET` | `/v1/packages/{package_id}/mappings` | Flat mapping-decision queue. |
| `POST` | `/v1/packages/{package_id}/mappings` | Add a suggestion; cannot approve it. |
| `POST` | `/v1/packages/{package_id}/mappings/{mapping_id}/approve` | Human approval with `expected_version` and note. |
| `POST` | `/v1/packages/{package_id}/mappings/{mapping_id}/reject` | Human rejection with `expected_version` and note. |

Approval requires matching broad account types. At most one suggestion per source account can be
approved. A replacement approval explicitly rejects the prior choice and records both IDs in the
audit event.

## Exceptions, readiness, and sequence

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/packages/{package_id}/blockers` | Derived and human-created exceptions, including resolved history. |
| `POST` | `/v1/packages/{package_id}/blockers` | Create a manual warning or blocker. |
| `POST` | `/v1/packages/{package_id}/blockers/{blocker_id}/resolve` | Resolve only a human-created blocker with version and note. |
| `GET` | `/v1/packages/{package_id}/readiness` | Latest persisted readiness evidence; read-only. |
| `POST` | `/v1/packages/{package_id}/readiness/recompute` | Recompute blockers, readiness, sequence, and audit evidence. |
| `GET` | `/v1/packages/{package_id}/sequence` | Latest immutable dependency plan. |

Every state-changing endpoint recalculates affected control state before commit. System blockers
cannot be manually resolved; the underlying balance or mapping condition must change in a new
package version or approved decision.

## Audit

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/v1/packages/{package_id}/audit-events` | Ordered event evidence. |
| `GET` | `/v1/packages/{package_id}/audit-events/verify` | Recompute sequence, previous-hash pointers, and SHA-256 event hashes. |

## Error envelope

Expected domain failures return one stable shape:

```json
{
  "error": {
    "code": "CONFLICT",
    "message": "mapping version conflict: expected 1, current 2"
  }
}
```

`NOT_FOUND` maps to `404`, `CONFLICT` to `409`, and cross-record validation to `422`. FastAPI's
standard field-level `422` response remains in place for malformed request bodies. Every HTTP
response receives `X-Request-Id`; a caller-provided value is preserved.
