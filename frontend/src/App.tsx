import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, launchpadApi } from "./api/client";
import { AuditDialog } from "./components/AuditDialog";
import { DecisionDialog, type DecisionSubmission } from "./components/DecisionDialog";
import { DemoMission, GuidedDemo, type DemoAnchor } from "./components/DemoGuide";
import { EntityRail } from "./components/EntityRail";
import { AlertIcon, CheckIcon, LayersIcon, RefreshIcon, ShieldIcon, UploadIcon } from "./components/Icons";
import { KpiStrip } from "./components/KpiStrip";
import { MappingLedger } from "./components/MappingLedger";
import { OperationsRail } from "./components/OperationsRail";
import { ResolveBlockerDialog } from "./components/ResolveBlockerDialog";
import { StatusPill } from "./components/StatusPill";
import { formatDate, formatTimestamp, readinessLabel, truncateHash } from "./lib/format";
import type { Blocker, Mapping, PackageDetail, WorkspaceData } from "./types";

interface DecisionState {
  mode: "approve" | "reject";
  mappings: Mapping[];
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) return `${error.message} (${error.code})`;
  if (error instanceof Error) return error.message;
  return "An unexpected error interrupted the control center.";
}

export default function App(): React.ReactElement {
  const [packages, setPackages] = useState<PackageDetail[]>([]);
  const [selectedPackageId, setSelectedPackageId] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState<WorkspaceData | null>(null);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [selectedSourceIds, setSelectedSourceIds] = useState<Set<string>>(new Set());
  const [decision, setDecision] = useState<DecisionState | null>(null);
  const [resolvingBlocker, setResolvingBlocker] = useState<Blocker | null>(null);
  const [showAudit, setShowAudit] = useState(false);
  const [initializing, setInitializing] = useState(true);
  const [loadingWorkspace, setLoadingWorkspace] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showDemo, setShowDemo] = useState(false);
  const [guidedFocus, setGuidedFocus] = useState<{ sourceCode: string; requestId: number } | null>(null);

  const loadPackages = useCallback(async (): Promise<void> => {
    setError(null);
    try {
      const available = await launchpadApi.listPackages();
      setPackages(available);
      setSelectedPackageId((current) => current && available.some((item) => item.id === current) ? current : available[0]?.id ?? null);
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setInitializing(false);
    }
  }, []);

  const loadSelectedWorkspace = useCallback(async (packageId: string): Promise<void> => {
    setLoadingWorkspace(true);
    setError(null);
    try {
      const data = await launchpadApi.loadWorkspace(packageId);
      setWorkspace(data);
      setSelectedSourceIds((current) => {
        const available = new Set(data.sourceAccounts.map((account) => account.id));
        return new Set([...current].filter((id) => available.has(id)));
      });
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setLoadingWorkspace(false);
    }
  }, []);

  useEffect(() => {
    void loadPackages();
  }, [loadPackages]);

  useEffect(() => {
    if (!selectedPackageId) {
      setWorkspace(null);
      return;
    }
    setSelectedEntityId(null);
    setSelectedSourceIds(new Set());
    void loadSelectedWorkspace(selectedPackageId);
  }, [loadSelectedWorkspace, selectedPackageId]);

  useEffect(() => {
    if (!notice) return;
    const timeout = window.setTimeout(() => setNotice(null), 4_500);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  const visibleAccounts = useMemo(() => {
    if (!workspace || !selectedEntityId) return workspace?.sourceAccounts ?? [];
    return workspace.sourceAccounts.filter((account) => account.entity_id === selectedEntityId);
  }, [selectedEntityId, workspace]);

  const selectedEntity = workspace?.package.entities.find((entity) => entity.id === selectedEntityId) ?? null;
  const approvedCount = workspace?.sourceAccounts.filter((account) => account.approved_mapping !== null).length ?? 0;
  const openBlockerCount = workspace?.blockers.filter((blocker) => blocker.state === "OPEN").length ?? 0;
  const isReady = workspace?.readiness.status === "DATA_PREPARATION_READY";

  const navigateDemo = useCallback((anchor: DemoAnchor, requestId: number): void => {
    if (anchor === "entities" && workspace) {
      const horizon = workspace.package.entities.find((entity) => entity.external_id === "HORIZON");
      if (horizon) setSelectedEntityId(horizon.id);
    }
    if (anchor === "mapping") {
      setGuidedFocus({ sourceCode: "HZ-115", requestId });
    } else {
      setGuidedFocus(null);
    }
    window.setTimeout(() => {
      document.querySelectorAll<HTMLElement>("[data-demo-anchor]").forEach((element) => {
        element.toggleAttribute("data-demo-highlight", element.dataset.demoAnchor === anchor);
      });
      const target = document.querySelector<HTMLElement>(`[data-demo-anchor="${anchor}"]`);
      if (target) {
        const rect = target.getBoundingClientRect();
        const viewportHeight = window.visualViewport?.height ?? window.innerHeight;
        window.scrollTo({
          behavior: "auto",
          left: 0,
          top: Math.max(0, window.scrollY + rect.top - Math.max(20, (viewportHeight - Math.min(rect.height, viewportHeight)) / 2)),
        });
      }
    }, 60);
  }, [workspace]);

  const closeDemo = (): void => {
    setShowDemo(false);
    setGuidedFocus(null);
    document.querySelectorAll<HTMLElement>("[data-demo-anchor]").forEach((element) => element.removeAttribute("data-demo-highlight"));
  };

  const refresh = async (): Promise<void> => {
    if (!selectedPackageId) return;
    await loadSelectedWorkspace(selectedPackageId);
    setNotice("Workspace refreshed from the audit-backed API.");
  };

  const submitDecision = async ({ actorId, note }: DecisionSubmission): Promise<void> => {
    if (!workspace || !decision) return;
    setBusy(true);
    setError(null);
    let completed = 0;
    try {
      for (const mapping of decision.mappings) {
        const command = { actor_id: actorId, expected_version: mapping.row_version, note };
        if (decision.mode === "approve") await launchpadApi.approveMapping(workspace.package.id, mapping.id, command);
        else await launchpadApi.rejectMapping(workspace.package.id, mapping.id, command);
        completed += 1;
      }
      setSelectedSourceIds(new Set());
      setDecision(null);
      await loadSelectedWorkspace(workspace.package.id);
      setNotice(`${completed} mapping decision${completed === 1 ? "" : "s"} recorded in the audit chain.`);
    } catch (requestError) {
      setError(`${completed > 0 ? `${completed} decision${completed === 1 ? "" : "s"} saved before the interruption. ` : ""}${errorText(requestError)}`);
      await loadSelectedWorkspace(workspace.package.id);
    } finally {
      setBusy(false);
    }
  };

  const createMapping = async (
    sourceAccountId: string,
    canonicalAccountId: string,
    actorId: string,
    rationale: string,
  ): Promise<void> => {
    if (!workspace) return;
    setBusy(true);
    setError(null);
    try {
      await launchpadApi.createMapping(workspace.package.id, {
        source_account_id: sourceAccountId,
        canonical_account_id: canonicalAccountId,
        confidence: 0.5,
        rationale,
        actor_id: actorId,
      });
      await loadSelectedWorkspace(workspace.package.id);
      setNotice("Candidate saved as suggested. A separate human approval is still required.");
    } catch (requestError) {
      setError(errorText(requestError));
      throw requestError;
    } finally {
      setBusy(false);
    }
  };

  const resolveBlocker = async ({ actorId, note }: { actorId: string; note: string }): Promise<void> => {
    if (!workspace || !resolvingBlocker) return;
    setBusy(true);
    setError(null);
    try {
      await launchpadApi.resolveBlocker(workspace.package.id, resolvingBlocker.id, {
        actor_id: actorId,
        expected_version: resolvingBlocker.row_version,
        resolution_note: note,
      });
      setResolvingBlocker(null);
      await loadSelectedWorkspace(workspace.package.id);
      setNotice("Blocker resolution recorded and readiness recalculated.");
    } catch (requestError) {
      setError(errorText(requestError));
      await loadSelectedWorkspace(workspace.package.id);
    } finally {
      setBusy(false);
    }
  };

  const recompute = async (): Promise<void> => {
    if (!workspace) return;
    setBusy(true);
    setError(null);
    try {
      await launchpadApi.recomputeReadiness(workspace.package.id);
      await loadSelectedWorkspace(workspace.package.id);
      setNotice("Readiness, blockers, and launch sequence recomputed from source evidence.");
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setBusy(false);
    }
  };

  const importFile = async (file: File): Promise<void> => {
    setBusy(true);
    setError(null);
    try {
      const payload = JSON.parse(await file.text()) as unknown;
      const result = await launchpadApi.importPackage(payload, `ui-import-${crypto.randomUUID()}`);
      await loadPackages();
      setSelectedPackageId(result.package_id);
      setNotice("Synthetic package imported. Every mapping remains unapproved until human review.");
    } catch (requestError) {
      setError(errorText(requestError));
    } finally {
      setBusy(false);
    }
  };

  if (initializing) return <LoadingScreen />;

  return (
    <div className="app-shell">
      <a className="skip-link" href="#mapping-ledger-heading">Skip to mapping ledger</a>
      <header className="app-header">
        <div className="brand-lockup">
          <span className="brand-mark"><LayersIcon /></span>
          <div><strong>Acquisition Launchpad</strong><small>Entity Control Center</small></div>
        </div>
        <div className="phase-lockup"><span>Phase 1</span><strong>In Progress</strong><small>Data preparation only</small></div>
        <div className="header-actions">
          {packages.length > 0 ? (
            <label className="package-select"><span>Acquisition package</span><select aria-label="Acquisition package" onChange={(event) => setSelectedPackageId(event.target.value)} value={selectedPackageId ?? ""}>{packages.map((item) => <option key={item.id} value={item.id}>{item.name} · v{item.package_version}</option>)}</select></label>
          ) : null}
          <span className="synthetic-badge"><ShieldIcon /> Synthetic data</span>
          <button className="button button--tour" onClick={() => setShowDemo(true)} type="button">3-minute demo</button>
          <button aria-label="Refresh workspace" className="icon-button header-refresh" disabled={loadingWorkspace || busy || !selectedPackageId} onClick={() => void refresh()} type="button"><RefreshIcon /></button>
        </div>
      </header>

      {error ? <div className="global-alert" role="alert"><AlertIcon /><span>{error}</span><button onClick={() => setError(null)} type="button">Dismiss</button></div> : null}
      {notice ? <div className="toast" role="status"><CheckIcon />{notice}</div> : null}

      {packages.length === 0 ? <EmptyWorkspace busy={busy} error={error} onImport={importFile} onRetry={() => void loadPackages()} /> : workspace ? (
        <>
          <section className="context-bar" aria-label="Package context">
            <div><span>Package</span><strong>{workspace.package.external_key}</strong></div>
            <div><span>As of</span><strong>{formatDate(workspace.package.as_of_date)}</strong></div>
            <div><span>Reporting currency</span><strong>{workspace.package.reporting_currency}</strong></div>
            <div><span>Payload evidence</span><code title={workspace.package.payload_hash}>{truncateHash(workspace.package.payload_hash)}</code></div>
            <div className="context-bar__readiness"><StatusPill value={workspace.readiness.status} /><small>Evaluated {formatTimestamp(workspace.readiness.computed_at)}</small></div>
            <button className="button button--secondary" disabled={busy || loadingWorkspace} onClick={() => void recompute()} type="button"><RefreshIcon /> Recompute controls</button>
          </section>
          <DemoMission approvedCount={approvedCount} isReady={isReady} onStart={() => setShowDemo(true)} totalCount={workspace.sourceAccounts.length} />
          <div className={`workspace-grid${loadingWorkspace ? " is-refreshing" : ""}`}>
            <EntityRail onSelectEntity={(entityId) => { setSelectedEntityId(entityId); setSelectedSourceIds(new Set()); }} packageDetail={workspace.package} readiness={workspace.readiness.entities} selectedEntityId={selectedEntityId} sourceAccounts={workspace.sourceAccounts} />
            <main className="control-main">
              <div className="scope-heading">
                <div><p className="eyebrow">Current review scope</p><h1>{selectedEntity?.name ?? "Consolidated acquisition"}</h1><p>{selectedEntity ? `${selectedEntity.legal_name} · ${selectedEntity.source_system}` : `${workspace.package.entities.length} entities · ${workspace.sourceAccounts.length} source accounts · ${readinessLabel(workspace.readiness.status)}`}</p></div>
                <div className="scope-boundary"><ShieldIcon /><span><strong>Synthetic portfolio proof</strong><small>Independent project · no company affiliation</small></span></div>
              </div>
              <KpiStrip accounts={workspace.sourceAccounts} blockers={workspace.blockers} currency={workspace.package.reporting_currency} readiness={workspace.readiness} sequence={workspace.sequence} />
              <MappingLedger accounts={visibleAccounts} busy={busy} canonicalAccounts={workspace.canonicalAccounts} currency={workspace.package.reporting_currency} guidedFocus={guidedFocus} onCreateMapping={createMapping} onRequestDecision={(mode, mappings) => setDecision({ mode, mappings })} onSelectionChange={setSelectedSourceIds} readiness={workspace.readiness.entities} selectedSourceIds={selectedSourceIds} />
            </main>
            <OperationsRail auditEvents={workspace.auditEvents} auditVerification={workspace.auditVerification} blockers={workspace.blockers} busy={busy} entities={workspace.package.entities} onResolveBlocker={setResolvingBlocker} onViewAudit={() => setShowAudit(true)} sequence={workspace.sequence} />
          </div>
        </>
      ) : (
        <div className="workspace-loading"><span className="spinner" /><strong>Loading control evidence</strong><p>Reading mappings, tie-outs, blockers, sequence, and audit chain.</p></div>
      )}

      {decision ? <DecisionDialog busy={busy} mappings={decision.mappings} mode={decision.mode} onClose={() => setDecision(null)} onSubmit={submitDecision} /> : null}
      {resolvingBlocker ? <ResolveBlockerDialog blocker={resolvingBlocker} busy={busy} onClose={() => setResolvingBlocker(null)} onSubmit={resolveBlocker} /> : null}
      {showAudit && workspace ? <AuditDialog events={workspace.auditEvents} onClose={() => setShowAudit(false)} verification={workspace.auditVerification} /> : null}
      {workspace ? <GuidedDemo approvedCount={approvedCount} isReady={isReady} onClose={closeDemo} onNavigate={navigateDemo} onOpenAudit={() => setShowAudit(true)} open={showDemo} openBlockerCount={openBlockerCount} totalCount={workspace.sourceAccounts.length} /> : null}
      <footer className="app-footer"><span>Acquisition Launchpad · Phase 1 control evidence</span><span>API: {launchpadApi.apiBase}</span></footer>
    </div>
  );
}

function LoadingScreen(): React.ReactElement {
  return <div className="loading-screen"><span className="brand-mark"><LayersIcon /></span><strong>Acquisition Launchpad</strong><div className="loading-line"><i /></div><small>Connecting to control evidence</small></div>;
}

function EmptyWorkspace({ busy, error, onImport, onRetry }: { busy: boolean; error: string | null; onImport: (file: File) => Promise<void>; onRetry: () => void }): React.ReactElement {
  return (
    <main className="empty-workspace">
      <span className="empty-workspace__icon"><UploadIcon /></span>
      <p className="eyebrow">No acquisition package</p>
      <h1>Bring in a synthetic Phase 1 package</h1>
      <p>Import a schema 1.0 JSON package to validate its entity hierarchy, tie opening balances, review account mappings, and generate a dependency sequence.</p>
      <label className={`button button--primary file-button${busy ? " is-disabled" : ""}`}>Choose synthetic JSON<input accept="application/json,.json" disabled={busy} onChange={(event) => { const file = event.target.files?.[0]; if (file) void onImport(file); }} type="file" /></label>
      <small>Customer data is not accepted for this portfolio demonstration.</small>
      {error ? <button className="text-button" onClick={onRetry} type="button">Retry API connection</button> : null}
    </main>
  );
}
