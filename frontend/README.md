# Entity Control Center frontend

This is the interactive Phase 1 control surface for Acquisition Launchpad. It uses sample data,
not a real company, and contains no customer record or customer result.

The frontend deliberately labels the overall product **In Progress**. Working Phase 1 covers
entity scope, account mapping decisions, exact opening-balance tie-outs, blocker handling,
readiness evidence, dependency sequencing, and audit verification. Integration synchronization,
intercompany eliminations, first-close simulation, and a full migration packet remain visibly
marked `Planned` / `Not implemented`.

## Run locally

The containerized backend is expected at `http://127.0.0.1:8011`.

```bash
npm ci
npm run dev
```

Open `http://127.0.0.1:3000`. To use a different backend, copy `.env.example` to `.env.local`
and change `VITE_API_BASE_URL`.

For the complete containerized stack, run `make demo-up` from the repository root and open
`http://127.0.0.1:3011`. The container build calls the API through same-origin `/api`; Nginx proxies
that path over the private Compose network.

There are no demo login credentials. Authentication is explicitly outside Phase 1, so the UI must
stay loopback-only and accept synthetic data only.

If the database has no package, the empty state accepts a schema `1.0` synthetic JSON file. It
does not silently seed or approve data. The repository fixture is
`../fixtures/horizon_acquisition_v1.json`.

## Working controls

- Always-visible problem/user/outcome demo card with `Review final decision` and `Start full tour`.
- Six-step guided walkthrough with entity, HZ-115 evidence, blocker, sequence, and audit navigation.
- Dismiss/restart controls, Left/Right/Escape keyboard support, and a mobile bottom-sheet layout.
- Package switcher and API refresh.
- Entity-tree scope over the central ledger.
- Search, status, and account-type filters.
- Pending-row selection and explicit bulk human approval.
- Candidate evidence expansion, approval, rejection, and same-type candidate creation.
- Exact debit/credit opening-balance display and per-entity tie-out state.
- Manual blocker resolution with reviewer identity, optimistic version, and evidence note.
- Deterministic readiness recomputation.
- Dependency-ordered launch sequence with prerequisites and blocker reasons.
- Hash-chain status plus the complete audit evidence ledger.

Confidence is shown only as suggestion evidence. Every approval requires a human reviewer ID and
note and calls the backend decision endpoint with its current `row_version`. System-generated
blockers are never given a fake resolve action; their UI explains that the source condition must
change.

## API contract

`src/api/client.ts` consumes these live endpoints:

- `GET /v1/packages` and `GET /v1/packages/{id}`
- `GET /v1/packages/{id}/canonical-accounts`
- `GET /v1/packages/{id}/source-accounts`
- `GET /v1/packages/{id}/mappings`
- `POST /v1/packages/{id}/mappings`
- `POST /v1/packages/{id}/mappings/{mapping_id}/approve|reject`
- `GET /v1/packages/{id}/blockers`
- `POST /v1/packages/{id}/blockers/{blocker_id}/resolve`
- `GET|POST /v1/packages/{id}/readiness[/recompute]`
- `GET /v1/packages/{id}/sequence`
- `GET /v1/packages/{id}/audit-events[/verify]`

The backend OpenAPI document remains authoritative. Domain errors are rendered from its stable
`error.code` and `error.message` envelope.

## Verification

```bash
npm run typecheck
npm run lint
npm test
npm run build
npm run test:e2e
```

Unit and component tests cover guided navigation and keyboard controls, entity hierarchy,
integer-cent formatting, pending-candidate selection, filters, human decision routing, candidate
creation, blocker boundaries, launch order, audit access, and API request/error contracts.
Playwright checks the real seeded backend on desktop and mobile, runs serious/critical
accessibility scans, verifies contained data-table overflow, checks browser console/page errors,
and drives HZ-115 from the one-decision-left state through persisted readiness and audit proof. The
suite discovers the Horizon fixture by external key and version rather than relying on a
machine-specific package UUID.
