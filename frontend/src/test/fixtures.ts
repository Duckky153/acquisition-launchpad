import type { WorkspaceData } from "../types";

export const workspaceFixture: WorkspaceData = {
  package: {
    id: "package-1",
    external_key: "synthetic-acquisition-v1",
    package_version: 1,
    name: "Synthetic acquisition package",
    as_of_date: "2026-07-31",
    reporting_currency: "USD",
    payload_hash: "1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
    entities: [
      { id: "entity-1", external_id: "PARENT", parent_id: null, name: "Parent Holdings", legal_name: "Parent Holdings, Inc. (Synthetic)", currency: "USD", source_system: "Synthetic ERP", source_account_count: 2 },
      { id: "entity-2", external_id: "CHILD", parent_id: "entity-1", name: "Child Services", legal_name: "Child Services LLC (Synthetic)", currency: "USD", source_system: "Synthetic Export", source_account_count: 1 },
    ],
  },
  canonicalAccounts: [
    { id: "canonical-cash", code: "1000", name: "Cash", account_type: "ASSET", normal_balance: "DEBIT" },
    { id: "canonical-ar", code: "1100", name: "Accounts Receivable", account_type: "ASSET", normal_balance: "DEBIT" },
  ],
  sourceAccounts: [
    {
      id: "source-1",
      entity_id: "entity-1",
      entity_external_id: "PARENT",
      entity_name: "Parent Holdings",
      code: "P-101",
      name: "Operating Bank",
      account_type: "ASSET",
      opening_balance_as_of: "2026-07-31",
      debit_cents: 120000,
      credit_cents: 0,
      approved_mapping: null,
      suggestions: [
        { id: "mapping-1", source_account_id: "source-1", canonical_account_id: "canonical-cash", entity_external_id: "PARENT", source_account_code: "P-101", source_account_name: "Operating Bank", canonical_account_code: "1000", canonical_account_name: "Cash", confidence: 0.94, rationale: "Exact bank and cash semantic match.", status: "SUGGESTED", approved_by: null, row_version: 1 },
        { id: "mapping-2", source_account_id: "source-1", canonical_account_id: "canonical-ar", entity_external_id: "PARENT", source_account_code: "P-101", source_account_name: "Operating Bank", canonical_account_code: "1100", canonical_account_name: "Accounts Receivable", confidence: 0.3, rationale: "Lower confidence same-type alternative.", status: "SUGGESTED", approved_by: null, row_version: 1 },
      ],
    },
    {
      id: "source-2",
      entity_id: "entity-1",
      entity_external_id: "PARENT",
      entity_name: "Parent Holdings",
      code: "P-115",
      name: "Trade Receivables",
      account_type: "ASSET",
      opening_balance_as_of: "2026-07-31",
      debit_cents: 50000,
      credit_cents: 0,
      approved_mapping: { id: "mapping-3", source_account_id: "source-2", canonical_account_id: "canonical-ar", entity_external_id: "PARENT", source_account_code: "P-115", source_account_name: "Trade Receivables", canonical_account_code: "1100", canonical_account_name: "Accounts Receivable", confidence: 0.98, rationale: "Receivable semantic match.", status: "APPROVED", approved_by: "reviewer", row_version: 2 },
      suggestions: [{ id: "mapping-3", source_account_id: "source-2", canonical_account_id: "canonical-ar", entity_external_id: "PARENT", source_account_code: "P-115", source_account_name: "Trade Receivables", canonical_account_code: "1100", canonical_account_name: "Accounts Receivable", confidence: 0.98, rationale: "Receivable semantic match.", status: "APPROVED", approved_by: "reviewer", row_version: 2 }],
    },
  ],
  mappings: [],
  blockers: [
    { id: "blocker-system", entity_id: "entity-1", source_account_id: "source-1", code: "UNAPPROVED_ACCOUNT_MAPPING", severity: "BLOCKING", state: "OPEN", title: "Account mapping needs approval", detail: "P-101 has no human-approved target.", system_generated: true, resolved_by: null, resolution_note: null, row_version: 1 },
    { id: "blocker-manual", entity_id: null, source_account_id: null, code: "CONTROLLER_REVIEW", severity: "WARNING", state: "OPEN", title: "Controller review note", detail: "Confirm the synthetic source package.", system_generated: false, resolved_by: null, resolution_note: null, row_version: 1 },
    { id: "blocker-resolved", entity_id: null, source_account_id: null, code: "OLD_NOTE", severity: "WARNING", state: "RESOLVED", title: "Old note", detail: "Already addressed.", system_generated: false, resolved_by: "reviewer", resolution_note: "Confirmed.", row_version: 2 },
  ],
  readiness: {
    evaluation_id: "evaluation-1",
    package_id: "package-1",
    status: "NOT_READY",
    computed_at: "2026-08-21T01:00:00Z",
    entities: [
      { entity_id: "entity-1", entity_external_id: "PARENT", entity_name: "Parent Holdings", status: "NOT_READY", checks: [], tie_out: { debit_cents: 170000, credit_cents: 170000, difference_cents: 0, is_balanced: true, entry_count: 2, account_count: 2, missing_account_codes: [] } },
    ],
  },
  sequence: {
    plan_id: "plan-1",
    package_id: "package-1",
    version: 1,
    created_at: "2026-08-21T01:00:00Z",
    steps: [
      { key: "PARENT:INTAKE", entity_external_id: "PARENT", entity_name: "Parent Holdings", step_type: "INTAKE", state: "COMPLETE", depends_on: [], blocked_by: [], order: 1 },
      { key: "PARENT:MAP_ACCOUNTS", entity_external_id: "PARENT", entity_name: "Parent Holdings", step_type: "MAP_ACCOUNTS", state: "BLOCKED", depends_on: ["PARENT:INTAKE"], blocked_by: ["UNAPPROVED_ACCOUNT_MAPPING"], order: 2 },
    ],
  },
  auditEvents: [
    { id: "event-1", sequence: 1, event_type: "PACKAGE_IMPORTED", actor_type: "SYSTEM", actor_id: "import-service", subject_type: "PACKAGE", subject_id: "package-1", payload: {}, previous_hash: null, event_hash: "abcdef1234567890abcdef1234567890", created_at: "2026-08-21T01:00:00Z" },
  ],
  auditVerification: { package_id: "package-1", valid: true, event_count: 1, first_invalid_sequence: null },
};
