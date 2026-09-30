# Architecture and trust boundaries

## Shape

The backend is a typed Python 3.13 modular monolith: FastAPI at the edge, a deterministic service
and domain layer, SQLAlchemy 2 persistence, Alembic migrations, and PostgreSQL. This is the
smallest architecture that preserves transactionality across intake, evidence, readiness,
sequence snapshots, and audit events. There is no microservice choreography to fail halfway
through an accounting decision.

## Data model

- `acquisition_packages` identifies an immutable external package version and payload hash.
- `entities` stores an adjacency-list hierarchy validated before import.
- `canonical_accounts` and `source_accounts` keep target and source charts separate.
- `trial_balance_entries` stores one exact, single-sided opening balance per source account.
- `mapping_suggestions` records candidates and explicit human decisions with optimistic versions.
- `blockers` holds derived and human-created exceptions without conflating the two.
- `readiness_evaluations` is an append-only snapshot of every gate calculation.
- `sequence_plans` is an append-only, input-hashed dependency plan.
- `audit_events` is a per-package, SHA-256 hash chain with monotonic sequence numbers.
- `idempotency_records` makes retried intake requests replay-safe.

## Correctness boundaries

- Currency is represented in integer cents. Trial balances require exact equality.
- AI may eventually populate suggestion rationale and confidence; it cannot write approval state,
  calculate balances, clear blockers, or alter readiness rules.
- Mapping approval requires compatible broad account types and is serialized per source account;
  PostgreSQL also enforces one approved target per source with a partial unique index.
- System blockers are projections of deterministic failures. The API rejects manual resolution of
  them because that would allow the UI to lie about the source data.
- Mutation endpoints record actor, before/after state where relevant, and evidence in the audit
  chain. PostgreSQL row locks serialize event sequence assignment.
- Package intake and each decision/recalculation are committed as database transactions.

## API and deployment boundary

OpenAPI is generated from strict Pydantic request and response models; unknown input fields are
rejected. CORS is limited to local frontend origins. The included database credentials are local
Docker defaults only. Production identity, authorization, secrets management, rate limiting,
encrypted object storage, and deployment are deliberately outside Phase 1 and must
be added before any real data is considered.

The local Compose dependency graph is `postgres → migrate → api → seed → frontend`. Migration and
seed are one-shot services; the stable seed idempotency key preserves existing human decisions.
The frontend container serves static assets as an unprivileged Nginx user and proxies `/api` to the
API over the private Compose network. Only loopback host ports are published. This removes the need
for permissive browser CORS in the containerized demo while retaining direct API inspection on
port `8011`.

Both application containers run as non-root users. The static server emits a content security
policy, denies framing, disables camera/microphone/geolocation, and prevents MIME sniffing. These
are useful local hardening controls, not a substitute for the production controls explicitly
excluded above.

## Failure behavior

- Domain validation returns structured `422` responses.
- Missing resources return `404`.
- idempotency, immutable-version, and optimistic-lock conflicts return `409`.
- Database constraints independently enforce nonnegative/single-sided balances, uniqueness, and
  referential integrity.
- Audit verification recomputes every event hash and chain pointer; a modified event identifies
  the first invalid sequence.
