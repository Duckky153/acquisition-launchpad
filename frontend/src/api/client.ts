import type {
  AuditEvent,
  AuditVerification,
  Blocker,
  BlockerResolutionCommand,
  CanonicalAccount,
  DecisionCommand,
  Mapping,
  MappingCreateCommand,
  PackageDetail,
  PackageReadiness,
  SequencePlan,
  SourceAccount,
  WorkspaceData,
} from "../types";

const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, "") ??
  "http://127.0.0.1:8011";

interface ErrorEnvelope {
  error?: {
    code?: string;
    message?: string;
  };
  detail?: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code = "REQUEST_FAILED") {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    let body: ErrorEnvelope = {};
    try {
      body = (await response.json()) as ErrorEnvelope;
    } catch {
      // A stable fallback keeps HTML proxy errors out of the operator UI.
    }
    const detail = typeof body.detail === "string" ? body.detail : undefined;
    throw new ApiError(
      body.error?.message ?? detail ?? `The API returned ${response.status}.`,
      response.status,
      body.error?.code,
    );
  }

  return (await response.json()) as T;
}

async function loadWorkspace(packageId: string): Promise<WorkspaceData> {
  const prefix = `/v1/packages/${packageId}`;
  const [
    packageDetail,
    canonicalAccounts,
    sourceAccounts,
    mappings,
    blockers,
    readiness,
    sequence,
    auditEvents,
    auditVerification,
  ] = await Promise.all([
    request<PackageDetail>(prefix),
    request<CanonicalAccount[]>(`${prefix}/canonical-accounts`),
    request<SourceAccount[]>(`${prefix}/source-accounts`),
    request<Mapping[]>(`${prefix}/mappings`),
    request<Blocker[]>(`${prefix}/blockers`),
    request<PackageReadiness>(`${prefix}/readiness`),
    request<SequencePlan>(`${prefix}/sequence`),
    request<AuditEvent[]>(`${prefix}/audit-events`),
    request<AuditVerification>(`${prefix}/audit-events/verify`),
  ]);
  return {
    package: packageDetail,
    canonicalAccounts,
    sourceAccounts,
    mappings,
    blockers,
    readiness,
    sequence,
    auditEvents,
    auditVerification,
  };
}

export const launchpadApi = {
  apiBase: API_BASE,
  listPackages: (): Promise<PackageDetail[]> => request<PackageDetail[]>("/v1/packages"),
  loadWorkspace,
  importPackage: (payload: unknown, idempotencyKey: string): Promise<{ package_id: string }> =>
    request<{ package_id: string }>("/v1/packages", {
      method: "POST",
      body: JSON.stringify(payload),
      headers: { "Idempotency-Key": idempotencyKey },
    }),
  approveMapping: (
    packageId: string,
    mappingId: string,
    command: DecisionCommand,
  ): Promise<Mapping> =>
    request<Mapping>(`/v1/packages/${packageId}/mappings/${mappingId}/approve`, {
      method: "POST",
      body: JSON.stringify(command),
    }),
  rejectMapping: (
    packageId: string,
    mappingId: string,
    command: DecisionCommand,
  ): Promise<Mapping> =>
    request<Mapping>(`/v1/packages/${packageId}/mappings/${mappingId}/reject`, {
      method: "POST",
      body: JSON.stringify(command),
    }),
  createMapping: (packageId: string, command: MappingCreateCommand): Promise<Mapping> =>
    request<Mapping>(`/v1/packages/${packageId}/mappings`, {
      method: "POST",
      body: JSON.stringify(command),
    }),
  resolveBlocker: (
    packageId: string,
    blockerId: string,
    command: BlockerResolutionCommand,
  ): Promise<Blocker> =>
    request<Blocker>(`/v1/packages/${packageId}/blockers/${blockerId}/resolve`, {
      method: "POST",
      body: JSON.stringify(command),
    }),
  recomputeReadiness: (packageId: string): Promise<PackageReadiness> =>
    request<PackageReadiness>(`/v1/packages/${packageId}/readiness/recompute`, {
      method: "POST",
    }),
};
