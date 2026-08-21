import type { Blocker, PackageReadiness, SequencePlan, SourceAccount } from "../types";
import { formatCents } from "../lib/format";

interface KpiStripProps {
  accounts: SourceAccount[];
  blockers: Blocker[];
  readiness: PackageReadiness;
  sequence: SequencePlan;
  currency: string;
}

export function KpiStrip({ accounts, blockers, readiness, sequence, currency }: KpiStripProps): React.ReactElement {
  const mapped = accounts.filter((account) => account.approved_mapping !== null).length;
  const balance = accounts.reduce((sum, account) => sum + (account.debit_cents ?? 0) - (account.credit_cents ?? 0), 0);
  const balanced = readiness.entities.filter((entity) => entity.tie_out.is_balanced).length;
  const openBlocking = blockers.filter((blocker) => blocker.state === "OPEN" && blocker.severity === "BLOCKING").length;
  const completeSteps = sequence.steps.filter((step) => step.state === "COMPLETE").length;
  return (
    <section aria-label="Control summary" className="kpi-strip">
      <article>
        <p>Mappings approved</p>
        <strong>{mapped}<span> / {accounts.length}</span></strong>
        <small>{accounts.length - mapped === 0 ? "Human review complete" : `${accounts.length - mapped} decisions remain`}</small>
      </article>
      <article>
        <p>Trial balances</p>
        <strong>{balanced}<span> / {readiness.entities.length}</span></strong>
        <small>{balance === 0 ? "Portfolio nets to zero" : `${formatCents(Math.abs(balance), currency)} difference`}</small>
      </article>
      <article>
        <p>Open blockers</p>
        <strong>{openBlocking}</strong>
        <small>{openBlocking === 0 ? "No blocking exceptions" : "Requires source or human action"}</small>
      </article>
      <article>
        <p>Sequence progress</p>
        <strong>{completeSteps}<span> / {sequence.steps.length}</span></strong>
        <small>Dependency-ordered controls</small>
      </article>
    </section>
  );
}
