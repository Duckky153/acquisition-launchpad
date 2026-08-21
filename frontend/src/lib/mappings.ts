import type { Mapping, SourceAccount } from "../types";

export function bestPendingMapping(account: SourceAccount): Mapping | null {
  if (account.approved_mapping) return null;
  const pending = account.suggestions.filter((mapping) => mapping.status === "SUGGESTED");
  return pending.sort((left, right) => right.confidence - left.confidence)[0] ?? null;
}
