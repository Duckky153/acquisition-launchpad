export type AccountType = "ASSET" | "LIABILITY" | "EQUITY" | "INCOME" | "EXPENSE";
export type NormalBalance = "DEBIT" | "CREDIT";
export type MappingStatus = "SUGGESTED" | "APPROVED" | "REJECTED";
export type BlockerSeverity = "BLOCKING" | "WARNING";
export type BlockerState = "OPEN" | "RESOLVED";
export type ReadinessStatus = "DATA_PREPARATION_READY" | "NOT_READY";
export type SequenceStepState = "COMPLETE" | "READY" | "BLOCKED";
export type SequenceStepType =
  | "INTAKE"
  | "MAP_ACCOUNTS"
  | "TIE_OUT"
  | "RESOLVE_BLOCKERS"
  | "DATA_PREPARATION_READY";

export interface EntitySummary {
  id: string;
  external_id: string;
  parent_id: string | null;
  name: string;
  legal_name: string;
  currency: string;
  source_system: string;
  source_account_count: number;
}

export interface PackageDetail {
  id: string;
  external_key: string;
  package_version: number;
  name: string;
  as_of_date: string;
  reporting_currency: string;
  payload_hash: string;
  entities: EntitySummary[];
}

export interface CanonicalAccount {
  id: string;
  code: string;
  name: string;
  account_type: AccountType;
  normal_balance: NormalBalance;
}

export interface Mapping {
  id: string;
  source_account_id: string;
  canonical_account_id: string;
  entity_external_id: string;
  source_account_code: string;
  source_account_name: string;
  canonical_account_code: string;
  canonical_account_name: string;
  confidence: number;
  rationale: string;
  status: MappingStatus;
  approved_by: string | null;
  row_version: number;
}

export interface SourceAccount {
  id: string;
  entity_id: string;
  entity_external_id: string;
  entity_name: string;
  code: string;
  name: string;
  account_type: AccountType;
  opening_balance_as_of: string | null;
  debit_cents: number | null;
  credit_cents: number | null;
  approved_mapping: Mapping | null;
  suggestions: Mapping[];
}

export interface TieOut {
  debit_cents: number;
  credit_cents: number;
  difference_cents: number;
  is_balanced: boolean;
  entry_count: number;
  account_count: number;
  missing_account_codes: string[];
}

export interface ReadinessCheck {
  code: string;
  passed: boolean;
  detail: string;
}

export interface EntityReadiness {
  entity_id: string;
  entity_external_id: string;
  entity_name: string;
  status: ReadinessStatus;
  checks: ReadinessCheck[];
  tie_out: TieOut;
}

export interface PackageReadiness {
  evaluation_id: string;
  package_id: string;
  status: ReadinessStatus;
  computed_at: string;
  entities: EntityReadiness[];
}

export interface Blocker {
  id: string;
  entity_id: string | null;
  source_account_id: string | null;
  code: string;
  severity: BlockerSeverity;
  state: BlockerState;
  title: string;
  detail: string;
  system_generated: boolean;
  resolved_by: string | null;
  resolution_note: string | null;
  row_version: number;
}

export interface SequenceStep {
  key: string;
  entity_external_id: string;
  entity_name: string;
  step_type: SequenceStepType;
  state: SequenceStepState;
  depends_on: string[];
  blocked_by: string[];
  order: number;
}

export interface SequencePlan {
  plan_id: string;
  package_id: string;
  version: number;
  created_at: string;
  steps: SequenceStep[];
}

export interface AuditEvent {
  id: string;
  sequence: number;
  event_type: string;
  actor_type: string;
  actor_id: string;
  subject_type: string;
  subject_id: string;
  payload: Record<string, unknown>;
  previous_hash: string | null;
  event_hash: string;
  created_at: string;
}

export interface AuditVerification {
  package_id: string;
  valid: boolean;
  event_count: number;
  first_invalid_sequence: number | null;
}

export interface WorkspaceData {
  package: PackageDetail;
  canonicalAccounts: CanonicalAccount[];
  sourceAccounts: SourceAccount[];
  mappings: Mapping[];
  blockers: Blocker[];
  readiness: PackageReadiness;
  sequence: SequencePlan;
  auditEvents: AuditEvent[];
  auditVerification: AuditVerification;
}

export interface DecisionCommand {
  actor_id: string;
  expected_version: number;
  note: string;
}

export interface MappingCreateCommand {
  source_account_id: string;
  canonical_account_id: string;
  confidence: number;
  rationale: string;
  actor_id: string;
}

export interface BlockerResolutionCommand {
  actor_id: string;
  expected_version: number;
  resolution_note: string;
}
