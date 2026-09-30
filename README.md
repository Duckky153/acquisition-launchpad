# Acquisition Launchpad

Acquisition Launchpad helps a finance implementation specialist or controller get the books of
newly acquired companies ready to join the parent company's accounting. It maps each company's
accounts to one standard chart, checks that opening balances tie, sends every account match to a
person for approval, and keeps a tamper-evident audit trail.

There is no live site. The app runs locally with Docker; see [Run the demo](#run-the-demo).

![Acquisition Launchpad guided demo with one mapping decision remaining](docs/assets/acquisition-launchpad-guided-demo.png)

- **Status: Phase 1 · In Progress.** Phase 1 works: entity intake, account mapping review,
  trial-balance tie-outs, blockers, readiness, sequencing, and the audit trail. Later modules
  (intercompany eliminations, live integrations, first-close simulation, the full migration
  packet, and production sign-in) are planned and not built.
- **Sample data, not a real company.** The checked-in package has 3 fictional companies (one
  parent and the two it acquired), 18 source accounts, 6 standard accounts, and 19 account-match
  suggestions. Money is stored in integer cents, and debits must equal credits exactly.
- **The account-match suggestions come pre-written in the sample file**, each with a confidence
  score and a reason. The tool does not generate them. What it does is control human review:
  nothing is applied until a person approves it, and confidence never approves anything.
- **Tests:** 30 backend tests (one needs PostgreSQL), 31 frontend unit tests, and 5 Playwright
  browser tests that run on desktop and mobile.

Built with AI assistance (Claude Code and Codex).

## The demo story

The in-app guide tells one story from start to finish:

> Horizon acquired two businesses. Their legacy systems call equivalent accounts by different
> names. An implementation specialist reviews the final proposed mapping, which clears the last
> evidence-backed blocker, makes the Phase 1 package ready, completes its dependency sequence, and
> leaves a verifiable audit record.

A demo card at the top explains the **problem, user, and outcome** before the operator touches the
ledger. It has two buttons:

- `Review final decision` opens the guide directly on the HZ-115 mapping decision.
- `Start full tour` walks through the entity structure, HZ-115 mapping evidence, remaining blocker,
  dependency sequence, and audit ledger.

The guide supports keyboard Left/Right navigation, Escape to close, mobile layouts, and a restart.
Restarting the guide does not change any data; `make demo-reset` restores the database demo state.

## Run the demo

Prerequisites for the one-command path:

- a running Docker Desktop or compatible Docker Engine with Compose;
- GNU Make or BSD Make (`make`);
- `curl` on `PATH` for the two final health assertions.

```bash
make demo-up
```

On Windows or another environment without Make, the direct Compose equivalent is:

```bash
docker compose up --build --detach --wait
```

Compose waits for PostgreSQL, migration, API, seed, and frontend health in dependency order. Then
open `http://127.0.0.1:3011`. Optional PowerShell health assertions are
`Invoke-WebRequest http://127.0.0.1:8011/v1/health/ready` and
`Invoke-WebRequest http://127.0.0.1:3011/healthz`.

That command builds both images, starts PostgreSQL, applies Alembic migrations, waits for the API,
replay-safely imports the checked-in synthetic package, materializes its fictional pre-reviewed
history through the same explicit decision endpoint, starts the same-origin frontend proxy, and
checks both health endpoints.

- Entity Control Center: `http://127.0.0.1:3011`
- OpenAPI: `http://127.0.0.1:8011/docs`
- API readiness: `http://127.0.0.1:8011/v1/health/ready`

There are **no demo credentials** because Phase 1 does not include production sign-in. The UI
opens directly and states that it uses sample data and runs locally. Never load customer or private
finance data into this build.

The named PostgreSQL volume preserves review decisions between launches. The seed uses a stable
idempotency key: a repeat launch reuses the original package without resetting decisions or
duplicating data. If the final demonstration was already completed, startup preserves that result
and tells the operator to use `make demo-reset` when a clean replay is intentionally required.

```bash
make demo-status
make demo-down
```

`demo-down` stops containers but preserves the local database volume. See
[docs/demo-runbook.md](docs/demo-runbook.md) for the exact walkthrough, fresh-state expectations,
and explicit reset command.

## Sample data details

The raw `fixtures/horizon_acquisition_v1.json` contains:

- 3 fictional legal entities: one parent and two child companies;
- 6 canonical accounts;
- 18 source accounts and 18 integer-cent opening-balance rows;
- 19 pre-written mapping suggestions;
- balanced trial balances for all three entities.

On import, every suggestion starts unapproved. The local demo seed then replays 17 explicitly
labeled **fictional historical decisions** through the normal approve endpoint and leaves
`HZ-115 · Trade Receivables → 1100 · Accounts Receivable` untouched. The user therefore starts
with 17 of 18 source accounts approved, exactly one source-derived blocker, tied balances, and
overall `NOT_READY`. The final live approval changes the package to `DATA_PREPARATION_READY`,
resolves the blocker, and completes all 15 dependency steps.

The pre-recorded synthetic history is convenience data, not a claim that AI, confidence, or a real
customer approved anything. Confidence never approves a mapping in the application. Every state
change still passes through the explicit decision endpoint with a reviewer label, note, optimistic
version, recalculation, and audit event.

## Walkthrough

1. Read the problem, user, and outcome card, then click `Start full tour`. (`Review final
   decision` skips straight to step 3.)
2. Follow the guide to the entity hierarchy and confirm three exact trial-balance tie-outs.
3. Continue to `HZ-115`, where the source, proposed target, confidence, and rationale are expanded.
4. Select `Review & approve`; enter a reviewer ID and a note on what you inspected.
5. Follow the guide to see the last blocker disappear and all 15 dependency steps complete.
6. Open the audit ledger and inspect the human decision plus recalculated control events.
7. Refresh the browser to prove the decision persists.

Every visible enabled control performs its stated operation. Later-phase modules are labels marked
`Planned` / `Not implemented`, not nonfunctional buttons.

## Development

Local development and `make verify` additionally require Python 3.13, `uv`, Node.js 22, and npm.
These host runtimes are not needed for the container-only demo path above.

```bash
docker compose up -d postgres
uv sync --python 3.13
uv run alembic upgrade head
uv run uvicorn acquisition_launchpad.main:app --reload --port 8011
```

In another terminal:

```bash
npm --prefix frontend ci
npm --prefix frontend run dev
```

The Vite UI opens at `http://127.0.0.1:3000` and calls the API at
`http://127.0.0.1:8011`. The containerized UI instead calls `/api` through its same-origin Nginx
proxy, so it does not rely on permissive CORS.

## Verification

Backend plus frontend checks:

```bash
make verify
```

`make verify` is self-contained after the prerequisites are installed: it starts the scoped
PostgreSQL service, applies the current migrations, runs strict backend gates plus the Alembic drift
check, installs the locked frontend dependencies, and runs TypeScript, ESLint, unit, and production
build gates. It does not reset the named demo volume.

Real PostgreSQL and browser proof:

```bash
LAUNCHPAD_TEST_POSTGRES_URL='postgresql+psycopg://launchpad:launchpad@127.0.0.1:5441/launchpad' \
  uv run pytest -m postgres
npm --prefix frontend exec -- playwright install chromium
make verify-browser
```

Dependency audit:

```bash
make security
```

`make security` audits Python and npm dependencies and runs the repository secret scan. It expects
`gitleaks` on `PATH`; CI runs the same default ruleset through the official Gitleaks action.

The browser suite uses the live seeded API on desktop and mobile, scans for serious/critical
accessibility violations, checks console/page errors and contained table overflow, drives the
guided HZ-115 decision from `NOT_READY` to `DATA_PREPARATION_READY`, verifies zero blockers, all 15
complete sequence steps, audit evidence, and refresh persistence. It discovers the seeded package
dynamically; it does not rely on a machine-specific database UUID.

CI runs strict Ruff formatting/lint, strict mypy, Alembic drift detection, backend coverage,
frontend TypeScript/ESLint/unit/build checks, dependency audits, container builds, and the real
full-stack browser workflow.

## Architecture and boundaries

- Python 3.13, FastAPI, SQLAlchemy 2, Alembic, and PostgreSQL.
- React 19, strict TypeScript, Vite, Vitest, Playwright, and axe.
- Integer cents for money; exact debit/credit equality.
- Immutable package versions and replay-safe intake.
- Human-only mapping approval with optimistic concurrency.
- Derived blockers that cannot be manually bypassed.
- Append-only readiness and sequence snapshots.
- SHA-256 chained audit events with verification endpoint.
- Non-root API and frontend containers, loopback-only host ports, same-origin API proxy, CSP, and
  baseline browser security headers.

This is a local demo, not a production finance system. It contains no customer data and gives no
accounting advice. Production identity and authorization, secrets management, encrypted storage,
backup/restore, rate limiting, monitoring, and live source integrations remain outside Phase 1.

Further contracts:

- [Phase 1 product contract](docs/phase-1-contract.md)
- [API workflow](docs/api.md)
- [Architecture and trust boundaries](docs/architecture.md)
- [Planned scope](docs/planned-scope.md)
- [Frontend operator contract](frontend/README.md)
