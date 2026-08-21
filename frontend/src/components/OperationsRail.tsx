import { useState } from "react";
import { formatTimestamp, humanizeConstant, sequenceStepLabels, truncateHash } from "../lib/format";
import type { AuditEvent, AuditVerification, Blocker, EntitySummary, SequencePlan } from "../types";
import { AlertIcon, CheckIcon, ChevronIcon, ShieldIcon } from "./Icons";
import { StatusPill } from "./StatusPill";

interface OperationsRailProps {
  blockers: Blocker[];
  entities: EntitySummary[];
  sequence: SequencePlan;
  auditEvents: AuditEvent[];
  auditVerification: AuditVerification;
  busy: boolean;
  onResolveBlocker: (blocker: Blocker) => void;
  onViewAudit: () => void;
}

export function OperationsRail({
  blockers,
  entities,
  sequence,
  auditEvents,
  auditVerification,
  busy,
  onResolveBlocker,
  onViewAudit,
}: OperationsRailProps): React.ReactElement {
  const [showResolved, setShowResolved] = useState(false);
  const visibleBlockers = blockers.filter((blocker) => showResolved || blocker.state === "OPEN");
  const openBlockers = blockers.filter((blocker) => blocker.state === "OPEN");
  const latestEvents = [...auditEvents].sort((left, right) => right.sequence - left.sequence).slice(0, 3);

  return (
    <aside aria-label="Launch controls" className="operations-rail">
      <section className="ops-card blockers-card" aria-labelledby="blockers-heading" data-demo-anchor="blockers" id="blocker-control">
        <div className="ops-card__heading">
          <div><p className="eyebrow">Exception queue</p><h2 id="blockers-heading">Blockers <span>{openBlockers.length}</span></h2></div>
          <AlertIcon />
        </div>
        <label className="toggle-label"><input checked={showResolved} onChange={(event) => setShowResolved(event.target.checked)} type="checkbox" />Show resolved history</label>
        <div aria-label="Blocker queue" className="blocker-list" tabIndex={0}>
          {visibleBlockers.slice(0, 8).map((blocker) => {
            const entity = entities.find((candidate) => candidate.id === blocker.entity_id);
            return (
              <article className={`blocker-item blocker-item--${blocker.severity.toLowerCase()}${blocker.state === "RESOLVED" ? " is-resolved" : ""}`} key={blocker.id}>
                <div className="blocker-item__top">
                  <StatusPill compact value={blocker.severity} />
                  <small>{entity?.name ?? "All entities"}</small>
                </div>
                <h3>{blocker.title}</h3>
                <p>{blocker.detail}</p>
                <div className="blocker-item__footer">
                  <span>{blocker.system_generated ? "System-derived" : "Human-created"}</span>
                  {blocker.state === "RESOLVED" ? <span className="resolved-label"><CheckIcon /> Resolved</span> : blocker.system_generated ? <small>Resolve through source correction</small> : <button className="text-button" disabled={busy} onClick={() => onResolveBlocker(blocker)} type="button">Resolve with note</button>}
                </div>
                {blocker.state === "RESOLVED" && (blocker.resolved_by || blocker.resolution_note) ? (
                  <dl className="resolution-evidence">
                    {blocker.resolved_by ? <div><dt>Resolved by</dt><dd>{blocker.resolved_by}</dd></div> : null}
                    {blocker.resolution_note ? <div><dt>Resolution note</dt><dd>{blocker.resolution_note}</dd></div> : null}
                  </dl>
                ) : null}
              </article>
            );
          })}
          {visibleBlockers.length === 0 ? <div className="ops-empty"><CheckIcon /><strong>No open exceptions</strong><span>Deterministic controls are clear.</span></div> : null}
          {visibleBlockers.length > 8 ? <p className="list-overflow-note">Showing 8 of {visibleBlockers.length}; resolve source mappings to reduce the queue.</p> : null}
        </div>
      </section>

      <section className="ops-card sequence-card" aria-labelledby="sequence-heading" data-demo-anchor="sequence" id="sequence-control">
        <div className="ops-card__heading">
          <div><p className="eyebrow">Dependency plan · v{sequence.version}</p><h2 id="sequence-heading">Launch sequence</h2></div>
          <span className="plan-count">{sequence.steps.filter((step) => step.state === "COMPLETE").length}/{sequence.steps.length}</span>
        </div>
        <ol aria-label="Dependency-ordered launch steps" className="sequence-list" tabIndex={0}>
          {[...sequence.steps].sort((left, right) => left.order - right.order).map((step) => (
            <li className={`sequence-step sequence-step--${step.state.toLowerCase()}`} key={step.key}>
              <span className="sequence-step__marker">{step.state === "COMPLETE" ? <CheckIcon /> : step.order}</span>
              <div>
                <small>{step.entity_name}</small>
                <strong>{sequenceStepLabels[step.step_type]}</strong>
                {step.blocked_by.length > 0 ? <span>Blocked by {step.blocked_by.map(humanizeConstant).join(", ")}</span> : step.depends_on.length > 0 ? <span>{step.depends_on.length} prerequisite{step.depends_on.length === 1 ? "" : "s"}</span> : <span>No prerequisites</span>}
              </div>
              <StatusPill compact value={step.state} />
            </li>
          ))}
        </ol>
      </section>

      <section className="ops-card audit-card" aria-labelledby="audit-heading" data-demo-anchor="audit" id="audit-control">
        <div className="ops-card__heading">
          <div><p className="eyebrow">Tamper evidence</p><h2 id="audit-heading">Audit trail</h2></div>
          <ShieldIcon />
        </div>
        <div className={`audit-verification${auditVerification.valid ? " is-valid" : " is-invalid"}`}>
          <span>{auditVerification.valid ? <CheckIcon /> : <AlertIcon />}</span>
          <div><strong>{auditVerification.valid ? "Hash chain verified" : "Integrity check failed"}</strong><small>{auditVerification.event_count} recorded events</small></div>
        </div>
        <div className="audit-preview">
          {latestEvents.map((event) => (
            <div key={event.id}>
              <span>{event.sequence}</span>
              <p><strong>{humanizeConstant(event.event_type)}</strong><small>{event.actor_type.toLowerCase()} · {formatTimestamp(event.created_at)}</small></p>
              <code>{truncateHash(event.event_hash)}</code>
            </div>
          ))}
        </div>
        <button className="button button--quiet button--full" onClick={onViewAudit} type="button">Open evidence ledger <ChevronIcon /></button>
      </section>
    </aside>
  );
}
