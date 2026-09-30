import { useEffect, useMemo, useState, type FormEvent } from "react";
import { formatBalance, humanizeConstant } from "../lib/format";
import { bestPendingMapping } from "../lib/mappings";
import type { CanonicalAccount, EntityReadiness, Mapping, SourceAccount } from "../types";
import { CheckIcon, ChevronIcon, PlusIcon, SearchIcon } from "./Icons";
import { StatusPill } from "./StatusPill";

type StatusFilter = "ALL" | "PENDING" | "APPROVED" | "REJECTED";
type AccountTypeFilter = "ALL" | SourceAccount["account_type"];

interface MappingLedgerProps {
  accounts: SourceAccount[];
  canonicalAccounts: CanonicalAccount[];
  readiness: EntityReadiness[];
  currency: string;
  busy: boolean;
  selectedSourceIds: Set<string>;
  onSelectionChange: (ids: Set<string>) => void;
  onRequestDecision: (mode: "approve" | "reject", mappings: Mapping[]) => void;
  onCreateMapping: (
    sourceAccountId: string,
    canonicalAccountId: string,
    actorId: string,
    rationale: string,
  ) => Promise<void>;
  guidedFocus: { sourceCode: string; requestId: number } | null;
}

function accountState(account: SourceAccount): StatusFilter {
  if (account.approved_mapping) return "APPROVED";
  if (account.suggestions.some((mapping) => mapping.status === "SUGGESTED")) return "PENDING";
  return "REJECTED";
}

export function MappingLedger({
  accounts,
  canonicalAccounts,
  readiness,
  currency,
  busy,
  selectedSourceIds,
  onSelectionChange,
  onRequestDecision,
  onCreateMapping,
  guidedFocus,
}: MappingLedgerProps): React.ReactElement {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("ALL");
  const [typeFilter, setTypeFilter] = useState<AccountTypeFilter>("ALL");
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const guidedRequestId = guidedFocus?.requestId;
  const guidedSourceCode = guidedFocus?.sourceCode;

  useEffect(() => {
    if (!guidedSourceCode || guidedRequestId === undefined) return;
    const guidedAccount = accounts.find((account) => account.code === guidedSourceCode);
    if (!guidedAccount) return;
    setQuery(guidedSourceCode);
    setStatusFilter("ALL");
    setTypeFilter("ALL");
    setExpandedId(guidedAccount.id);
  }, [accounts, guidedRequestId, guidedSourceCode]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return accounts.filter((account) => {
      const target = account.approved_mapping ?? bestPendingMapping(account);
      const matchesSearch =
        !normalized ||
        [
          account.entity_name,
          account.entity_external_id,
          account.code,
          account.name,
          target?.canonical_account_code,
          target?.canonical_account_name,
        ].some((value) => value?.toLowerCase().includes(normalized));
      const matchesStatus = statusFilter === "ALL" || accountState(account) === statusFilter;
      const matchesType = typeFilter === "ALL" || account.account_type === typeFilter;
      return matchesSearch && matchesStatus && matchesType;
    });
  }, [accounts, query, statusFilter, typeFilter]);

  const selectable = filtered.filter((account) => bestPendingMapping(account) !== null);
  const allSelected = selectable.length > 0 && selectable.every((account) => selectedSourceIds.has(account.id));

  const toggleAll = (): void => {
    const next = new Set(selectedSourceIds);
    if (allSelected) {
      for (const account of selectable) next.delete(account.id);
    } else {
      for (const account of selectable) next.add(account.id);
    }
    onSelectionChange(next);
  };

  const toggleOne = (accountId: string): void => {
    const next = new Set(selectedSourceIds);
    if (next.has(accountId)) next.delete(accountId);
    else next.add(accountId);
    onSelectionChange(next);
  };

  const approveSelected = (): void => {
    const mappings = accounts
      .filter((account) => selectedSourceIds.has(account.id))
      .map(bestPendingMapping)
      .filter((mapping): mapping is Mapping => mapping !== null);
    if (mappings.length > 0) onRequestDecision("approve", mappings);
  };

  return (
    <section aria-labelledby="mapping-ledger-heading" className="mapping-ledger" data-demo-anchor="mapping" id="mapping-control">
      <div className="section-heading mapping-ledger__heading">
        <div>
          <p className="eyebrow">Control 02 · Human decision required</p>
          <h2 id="mapping-ledger-heading">Account mapping ledger</h2>
          <p>Source accounts become canonical only after a recorded human approval.</p>
        </div>
        <button className="button button--primary" disabled={selectedSourceIds.size === 0 || busy} onClick={approveSelected} type="button">
          <CheckIcon /> Approve selected <span>{selectedSourceIds.size}</span>
        </button>
      </div>
      <div className="mapping-toolbar">
        <label className="search-field">
          <span className="sr-only">Search account mappings</span>
          <SearchIcon />
          <input onChange={(event) => setQuery(event.target.value)} placeholder="Search entity, source, or target" type="search" value={query} />
        </label>
        <label className="compact-field">
          <span>Status</span>
          <select aria-label="Filter by mapping status" onChange={(event) => setStatusFilter(event.target.value as StatusFilter)} value={statusFilter}>
            <option value="ALL">All decisions</option>
            <option value="PENDING">Needs review</option>
            <option value="APPROVED">Approved</option>
            <option value="REJECTED">No active candidate</option>
          </select>
        </label>
        <label className="compact-field">
          <span>Account type</span>
          <select aria-label="Filter by account type" onChange={(event) => setTypeFilter(event.target.value as AccountTypeFilter)} value={typeFilter}>
            <option value="ALL">All types</option>
            <option value="ASSET">Asset</option>
            <option value="LIABILITY">Liability</option>
            <option value="EQUITY">Equity</option>
            <option value="INCOME">Income</option>
            <option value="EXPENSE">Expense</option>
          </select>
        </label>
        <span className="result-count" aria-live="polite">{filtered.length} of {accounts.length}</span>
      </div>
      <div className="table-scroll">
        <table>
          <caption className="sr-only">Source-to-canonical account mapping decisions and opening balances</caption>
          <thead>
            <tr>
              <th className="check-column" scope="col">
                <input aria-label="Select all visible pending mappings" checked={allSelected} disabled={selectable.length === 0} onChange={toggleAll} type="checkbox" />
              </th>
              <th scope="col">Entity / tie-out</th>
              <th scope="col">Source account</th>
              <th scope="col">Canonical target</th>
              <th scope="col">Opening balance</th>
              <th scope="col">Decision</th>
              <th className="expand-column" scope="col"><span className="sr-only">Details</span></th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((account) => {
              const pending = bestPendingMapping(account);
              const target = account.approved_mapping ?? pending;
              const tied = readiness.find((entity) => entity.entity_id === account.entity_id)?.tie_out.is_balanced ?? false;
              const isExpanded = expandedId === account.id;
              const state = accountState(account);
              return (
                <MappingRows
                  account={account}
                  busy={busy}
                  canonicalAccounts={canonicalAccounts}
                  currency={currency}
                  expanded={isExpanded}
                  guided={guidedSourceCode === account.code}
                  key={account.id}
                  onCreateMapping={onCreateMapping}
                  onRequestDecision={onRequestDecision}
                  onToggleExpanded={() => setExpandedId(isExpanded ? null : account.id)}
                  onToggleSelected={() => toggleOne(account.id)}
                  pending={pending}
                  selected={selectedSourceIds.has(account.id)}
                  state={state}
                  target={target}
                  tied={tied}
                />
              );
            })}
            {filtered.length === 0 ? (
              <tr><td className="table-empty" colSpan={7}>No accounts match these filters.</td></tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </section>
  );
}

interface MappingRowsProps {
  account: SourceAccount;
  canonicalAccounts: CanonicalAccount[];
  currency: string;
  pending: Mapping | null;
  target: Mapping | null;
  state: StatusFilter;
  tied: boolean;
  selected: boolean;
  expanded: boolean;
  guided: boolean;
  busy: boolean;
  onToggleSelected: () => void;
  onToggleExpanded: () => void;
  onRequestDecision: (mode: "approve" | "reject", mappings: Mapping[]) => void;
  onCreateMapping: MappingLedgerProps["onCreateMapping"];
}

function MappingRows({
  account,
  canonicalAccounts,
  currency,
  pending,
  target,
  state,
  tied,
  selected,
  expanded,
  guided,
  busy,
  onToggleSelected,
  onToggleExpanded,
  onRequestDecision,
  onCreateMapping,
}: MappingRowsProps): React.ReactElement {
  return (
    <>
      <tr className={`${expanded ? "is-expanded" : ""}${guided ? " is-guided-row" : ""}`.trim() || undefined}>
        <td className="check-column">
          <input aria-label={`Select ${account.code}`} checked={selected} disabled={!pending} onChange={onToggleSelected} type="checkbox" />
        </td>
        <td>
          <strong className="table-primary">{account.entity_name}</strong>
          <span className={`tie-indicator${tied ? " is-tied" : ""}`}><i />{tied ? "Tied" : "Out of balance"}</span>
        </td>
        <td>
          <span className="account-code">{account.code}</span>
          <strong className="table-primary">{account.name}</strong>
          <small>{humanizeConstant(account.account_type)}</small>
        </td>
        <td>
          {target ? (
            <>
              <span className="account-code account-code--target">{target.canonical_account_code}</span>
              <strong className="table-primary">{target.canonical_account_name}</strong>
              {state === "PENDING" ? (
                <span className="confidence"><i style={{ width: `${Math.round(target.confidence * 100)}%` }} />{Math.round(target.confidence * 100)}% suggested</span>
              ) : null}
            </>
          ) : <span className="muted">No active candidate</span>}
        </td>
        <td><strong className="numeric">{formatBalance(account, currency)}</strong><small>{account.opening_balance_as_of ?? "No as-of date"}</small></td>
        <td>
          {state === "APPROVED" ? <StatusPill compact value="APPROVED" /> : state === "PENDING" ? <StatusPill compact value="SUGGESTED" /> : <StatusPill compact value="REJECTED" />}
          {account.approved_mapping?.approved_by ? <small>by {account.approved_mapping.approved_by}</small> : null}
        </td>
        <td className="expand-column">
          <button aria-expanded={expanded} aria-label={`${expanded ? "Hide" : "Show"} mapping evidence for ${account.code}`} className={`icon-button expand-button${expanded ? " is-open" : ""}`} onClick={onToggleExpanded} type="button"><ChevronIcon /></button>
        </td>
      </tr>
      {expanded ? (
        <tr className="mapping-detail-row">
          <td colSpan={7}>
            <MappingDetail account={account} busy={busy} canonicalAccounts={canonicalAccounts} onCreateMapping={onCreateMapping} onRequestDecision={onRequestDecision} />
          </td>
        </tr>
      ) : null}
    </>
  );
}

interface MappingDetailProps {
  account: SourceAccount;
  canonicalAccounts: CanonicalAccount[];
  busy: boolean;
  onRequestDecision: MappingLedgerProps["onRequestDecision"];
  onCreateMapping: MappingLedgerProps["onCreateMapping"];
}

function MappingDetail({ account, canonicalAccounts, busy, onRequestDecision, onCreateMapping }: MappingDetailProps): React.ReactElement {
  const compatible = canonicalAccounts.filter((canonical) => canonical.account_type === account.account_type);
  const [showCreate, setShowCreate] = useState(false);
  const [canonicalId, setCanonicalId] = useState(compatible[0]?.id ?? "");
  const [actorId, setActorId] = useState("demo-reviewer");
  const [rationale, setRationale] = useState("");

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    if (!canonicalId || !actorId.trim() || !rationale.trim()) return;
    void onCreateMapping(account.id, canonicalId, actorId.trim(), rationale.trim()).then(() => {
      setShowCreate(false);
      setRationale("");
    });
  };

  const suggestions = [...account.suggestions].sort((left, right) => {
    const rank = { APPROVED: 0, SUGGESTED: 1, REJECTED: 2 } as const;
    return rank[left.status] - rank[right.status] || right.confidence - left.confidence;
  });

  return (
    <div className="mapping-detail">
      <div className="mapping-detail__header">
        <div>
          <p className="eyebrow">Decision evidence</p>
          <h3>{account.code} · {account.name}</h3>
        </div>
        <button className="button button--quiet" disabled={busy} onClick={() => setShowCreate((current) => !current)} type="button"><PlusIcon /> Add candidate</button>
      </div>
      {showCreate ? (
        <form className="candidate-form" onSubmit={submit}>
          <label className="field"><span>Compatible canonical account</span><select onChange={(event) => setCanonicalId(event.target.value)} required value={canonicalId}>{compatible.map((canonical) => <option key={canonical.id} value={canonical.id}>{canonical.code} · {canonical.name}</option>)}</select></label>
          <label className="field"><span>Reviewer ID</span><input onChange={(event) => setActorId(event.target.value)} required value={actorId} /></label>
          <label className="field field--grow"><span>Why should this be considered?</span><input onChange={(event) => setRationale(event.target.value)} placeholder="Document the source evidence; this creates a suggestion only." required value={rationale} /></label>
          <button className="button button--secondary" disabled={busy || !canonicalId || !actorId.trim() || !rationale.trim()} type="submit">Save candidate</button>
        </form>
      ) : null}
      <div className="candidate-grid">
        {suggestions.map((mapping) => (
          <article className={`candidate-card candidate-card--${mapping.status.toLowerCase()}`} key={mapping.id}>
            <div className="candidate-card__top">
              <div><span className="account-code account-code--target">{mapping.canonical_account_code}</span><h4>{mapping.canonical_account_name}</h4></div>
              <StatusPill compact value={mapping.status} />
            </div>
            <p>{mapping.rationale}</p>
            <div className="candidate-card__confidence"><span><i style={{ width: `${Math.round(mapping.confidence * 100)}%` }} /></span><strong>{Math.round(mapping.confidence * 100)}%</strong><small>suggestion confidence</small></div>
            {mapping.status === "SUGGESTED" ? (
              <div className="candidate-card__actions">
                <button className="button button--quiet button--small" disabled={busy} onClick={() => onRequestDecision("reject", [mapping])} type="button">Reject</button>
                <button className="button button--primary button--small" disabled={busy} onClick={() => onRequestDecision("approve", [mapping])} type="button">Review & approve</button>
              </div>
            ) : mapping.approved_by ? <small className="decision-by">Approved by {mapping.approved_by}</small> : null}
          </article>
        ))}
        {suggestions.length === 0 ? <div className="inline-empty">No candidates remain. Add a compatible candidate for human review.</div> : null}
      </div>
    </div>
  );
}
