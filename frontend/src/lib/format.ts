import type { ReadinessStatus, SequenceStepType, SourceAccount } from "../types";

const dollars = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  maximumFractionDigits: 0,
});

const dates = new Intl.DateTimeFormat("en-US", {
  month: "short",
  day: "numeric",
  year: "numeric",
});

export function formatCents(cents: number, currency = "USD"): string {
  if (currency === "USD") {
    return dollars.format(cents / 100);
  }
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(cents / 100);
}

export function formatBalance(account: SourceAccount, currency = "USD"): string {
  if (account.debit_cents === null || account.credit_cents === null) return "Missing";
  if (account.debit_cents > 0) return `${formatCents(account.debit_cents, currency)} Dr`;
  if (account.credit_cents > 0) return `${formatCents(account.credit_cents, currency)} Cr`;
  return formatCents(0, currency);
}

export function formatDate(value: string): string {
  const parsed = new Date(value.includes("T") ? value : `${value}T00:00:00`);
  return dates.format(parsed);
}

export function formatTimestamp(value: string): string {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

export function humanizeConstant(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((part) => `${part.charAt(0).toUpperCase()}${part.slice(1)}`)
    .join(" ");
}

export function readinessLabel(status: ReadinessStatus): string {
  return status === "DATA_PREPARATION_READY" ? "Data prep ready" : "Not ready";
}

export const sequenceStepLabels: Record<SequenceStepType, string> = {
  INTAKE: "Entity intake",
  MAP_ACCOUNTS: "Map accounts",
  TIE_OUT: "Tie opening balance",
  RESOLVE_BLOCKERS: "Resolve blockers",
  DATA_PREPARATION_READY: "Data preparation ready",
};

export function truncateHash(hash: string): string {
  return `${hash.slice(0, 8)}…${hash.slice(-6)}`;
}
