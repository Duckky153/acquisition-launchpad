import { flattenEntityTree, buildEntityTree } from "../lib/entities";
import { readinessLabel } from "../lib/format";
import type { EntityReadiness, PackageDetail, SourceAccount } from "../types";
import { CheckIcon, LayersIcon } from "./Icons";

interface EntityRailProps {
  packageDetail: PackageDetail;
  sourceAccounts: SourceAccount[];
  readiness: EntityReadiness[];
  selectedEntityId: string | null;
  onSelectEntity: (entityId: string | null) => void;
}

export function EntityRail({
  packageDetail,
  sourceAccounts,
  readiness,
  selectedEntityId,
  onSelectEntity,
}: EntityRailProps): React.ReactElement {
  const nodes = flattenEntityTree(buildEntityTree(packageDetail.entities));
  const mappedCount = sourceAccounts.filter((account) => account.approved_mapping !== null).length;

  return (
    <aside aria-label="Entity scope" className="entity-rail" data-demo-anchor="entities" id="entity-control">
      <div className="rail-heading">
        <div>
          <p className="eyebrow">Consolidation scope</p>
          <h2>Entity structure</h2>
        </div>
        <LayersIcon />
      </div>
      <div className="entity-list" role="list">
        <div role="listitem">
          <button
            aria-pressed={selectedEntityId === null}
            className={`entity-card entity-card--group${selectedEntityId === null ? " is-selected" : ""}`}
            onClick={() => onSelectEntity(null)}
            type="button"
          >
            <span className="entity-card__marker"><LayersIcon /></span>
            <span className="entity-card__content">
              <strong>All entities</strong>
              <small>{packageDetail.entities.length} legal entities</small>
              <span className="entity-card__progress">
                <span><i style={{ width: `${sourceAccounts.length === 0 ? 0 : (mappedCount / sourceAccounts.length) * 100}%` }} /></span>
                {mappedCount}/{sourceAccounts.length} mapped
              </span>
            </span>
          </button>
        </div>
        {nodes.map(({ entity, depth }) => {
          const entityReadiness = readiness.find((item) => item.entity_id === entity.id);
          const entityAccounts = sourceAccounts.filter((account) => account.entity_id === entity.id);
          const approved = entityAccounts.filter((account) => account.approved_mapping !== null).length;
          const ready = entityReadiness?.status === "DATA_PREPARATION_READY";
          return (
            <div key={entity.id} role="listitem">
              <button
                aria-pressed={selectedEntityId === entity.id}
                className={`entity-card${selectedEntityId === entity.id ? " is-selected" : ""}`}
                onClick={() => onSelectEntity(entity.id)}
                style={{ "--entity-depth": depth } as React.CSSProperties}
                type="button"
              >
                <span className={`entity-card__status${ready ? " is-ready" : ""}`}>
                  {ready ? <CheckIcon /> : null}
                </span>
                <span className="entity-card__content">
                  <span className="entity-card__title">
                    <strong>{entity.name}</strong>
                    <small>{entity.currency}</small>
                  </span>
                  <small>{entity.source_system}</small>
                  <span className="entity-card__progress">
                    <span><i style={{ width: `${entityAccounts.length === 0 ? 0 : (approved / entityAccounts.length) * 100}%` }} /></span>
                    {approved}/{entityAccounts.length} mapped
                  </span>
                  <small className="entity-card__readiness">{entityReadiness ? readinessLabel(entityReadiness.status) : "Awaiting evaluation"}</small>
                </span>
              </button>
            </div>
          );
        })}
      </div>
      <section className="planned-card" aria-labelledby="planned-heading">
        <p className="eyebrow">Later phases · Planned</p>
        <h3 id="planned-heading">Beyond data preparation</h3>
        <ul>
          <li><span>Integration sync</span><small>Not implemented</small></li>
          <li><span>Intercompany eliminations</span><small>Not implemented</small></li>
          <li><span>First-close simulation</span><small>Not implemented</small></li>
        </ul>
      </section>
    </aside>
  );
}
