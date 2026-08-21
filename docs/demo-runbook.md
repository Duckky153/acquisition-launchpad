# Local synthetic demo runbook

## Boundary

This walkthrough uses only `fixtures/horizon_acquisition_v1.json`. Every entity, account, amount,
and mapping rationale is fictional. Acquisition Launchpad is independent and not affiliated with
Entry Inc. or DualEntry. Do not import real customer, employer, or private finance data.

The product remains **Phase 1 · In Progress**. A successful data-preparation gate does not mean a
company has been migrated, integrated, eliminated, closed, or made production-ready.

## Start

From the repository root:

```bash
make demo-up
```

Expected output ends with:

```text
Entity Control Center: http://127.0.0.1:3011
API documentation: http://127.0.0.1:8011/docs
```

No username or password is required. That is an explicit non-production boundary, not a demo
credential omission. The local build must never be exposed to an untrusted network.

`make demo-up` performs these dependency-ordered operations:

1. starts PostgreSQL on loopback port `5441`;
2. applies the current Alembic migration in a one-shot container;
3. starts the non-root API on loopback port `8011` and waits for database-backed health;
4. imports or idempotently replays the Horizon synthetic package;
5. records 17 fictional historical mapping decisions through the normal decision endpoint while
   deliberately leaving HZ-115 untouched;
6. verifies the one-decision-left state, sequence shape, and audit chain;
7. starts the non-root frontend on loopback port `3011` and checks `/healthz`.

## Fresh-state evidence

A genuinely fresh, fully seeded project volume contains:

- 3 entities;
- 18 source accounts;
- 19 suggestions;
- 17 approved source-account mappings, each explicitly labeled as synthetic demo history;
- HZ-115 as the only unapproved source account;
- 1 open `UNAPPROVED_ACCOUNT_MAPPING` blocker tied to HZ-115;
- 3 of 3 exactly tied trial balances;
- package readiness `NOT_READY`;
- 15 dependency steps in a versioned sequence plan;
- a valid audit chain containing import, pre-recorded mapping, blocker, readiness, and sequence
  evidence.

The named volume intentionally preserves decisions. On a reused volume, the counts can differ.
That persistence is visible through reviewer IDs, notes, blocker history, sequence versions, and
the audit ledger; the replay-safe seed never silently resets it.

## Three-minute demonstration

1. Read the top boundary: `Phase 1`, `In Progress`, `Synthetic data`.
2. Read the visible problem/user/outcome card, confirm `17/18 approved`, and click
   `Start guided demo`.
3. Use `Next` (or Right Arrow) to visit the entity hierarchy. Confirm three entities and three exact
   tie-outs.
4. Continue to the mapping step. HZ-115 is automatically filtered and its evidence expanded:
   `Trade Receivables → 1100 · Accounts Receivable`, 98% suggestion confidence, asset-to-asset.
5. Select `Review & approve`. Enter a truthful local reviewer label and exactly what you inspected.
6. Confirm the top story changes to `The acquisition package is ready` and `18/18 approved`.
7. Jump to the blocker step: the source-derived exception is gone. Continue to sequence: all 15
   dependency steps are complete.
8. Open the audit ledger from the last guide step. Confirm the chain verifies and inspect the
   reviewer, note, payload, prior hash, and event hash.
9. Close the ledger and refresh the workspace. The approval and ready state persist.

The `Recompute controls` button is intentionally deterministic. It cannot override a failed check.
System blocker cards intentionally say `Resolve through source correction`; only human-created
blockers receive a resolve action.

## Verification commands

```bash
make verify
make security
npm --prefix frontend exec -- playwright install chromium
make verify-browser
```

The mutation test uses actor `guided-demo-browser-reviewer` and a test-only evidence note. It
executes against the final HZ-115 decision and skips the mutation if the preserved database is
already ready.

## Stop and inspect

```bash
make demo-status
make demo-down
```

`make demo-down` preserves the named database volume. To intentionally return to the exact
one-decision-left state, run this project-scoped reset from this exact repository:

```bash
make demo-reset
```

The target runs `docker compose down --volumes --remove-orphans` and then `make demo-up`. It deletes
only this Compose project's local PostgreSQL volume, then recreates and reseeds it. The deleted
local decisions cannot be recovered. Do not run it when durable local review evidence should be
kept.

## Troubleshooting

- Port conflict: ports `3011`, `8011`, and `5441` must be free on `127.0.0.1`.
- Docker health: run `docker compose ps` and `docker compose logs api frontend seed migrate`.
- API data: `curl --fail http://127.0.0.1:8011/v1/packages`.
- Proxy data: `curl --fail http://127.0.0.1:3011/api/v1/packages`.
- Migration drift: `uv run alembic check`.
- The seed failing with `409` means the immutable external key/version no longer matches the
  checked-in fixture. Investigate; do not bypass the conflict.
