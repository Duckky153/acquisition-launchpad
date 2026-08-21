import { formatTimestamp, humanizeConstant, truncateHash } from "../lib/format";
import type { AuditEvent, AuditVerification } from "../types";
import { AlertIcon, CheckIcon } from "./Icons";
import { Modal } from "./Modal";

interface AuditDialogProps {
  events: AuditEvent[];
  verification: AuditVerification;
  onClose: () => void;
}

function eventNote(event: AuditEvent): string | null {
  for (const key of ["decision_note", "resolution_note", "note", "rationale"]) {
    const value = event.payload[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return null;
}

export function AuditDialog({ events, verification, onClose }: AuditDialogProps): React.ReactElement {
  return (
    <Modal description="Every import, mapping decision, blocker transition, readiness result, and sequence plan is linked by SHA-256 hashes." onClose={onClose} title="Audit evidence ledger" wide>
      <div className={`audit-dialog-status${verification.valid ? " is-valid" : " is-invalid"}`}>
        {verification.valid ? <CheckIcon /> : <AlertIcon />}
        <div><strong>{verification.valid ? "Audit chain verified" : "Audit chain failed verification"}</strong><span>{verification.event_count} events checked{verification.first_invalid_sequence ? ` · first invalid event ${verification.first_invalid_sequence}` : ""}</span></div>
      </div>
      <div className="audit-table-wrap">
        <table className="audit-table">
          <caption className="sr-only">Hash-chained audit events</caption>
          <thead><tr><th scope="col">Seq.</th><th scope="col">Event</th><th scope="col">Actor</th><th scope="col">Subject</th><th scope="col">Recorded</th><th scope="col">Evidence hash</th></tr></thead>
          <tbody>
            {[...events].sort((left, right) => right.sequence - left.sequence).map((event) => {
              const note = eventNote(event);
              return (
                <tr key={event.id}>
                  <td><span className="audit-sequence">{event.sequence}</span></td>
                  <td><strong>{humanizeConstant(event.event_type)}</strong>{note ? <small className="audit-note">{note}</small> : null}</td>
                  <td><span>{event.actor_id}</span><small>{humanizeConstant(event.actor_type)}</small></td>
                  <td><span>{humanizeConstant(event.subject_type)}</span><small title={event.subject_id}>{event.subject_id.slice(0, 12)}</small></td>
                  <td>{formatTimestamp(event.created_at)}</td>
                  <td>
                    <code title={event.event_hash}>{truncateHash(event.event_hash)}</code>
                    <details className="audit-evidence">
                      <summary>Inspect event evidence</summary>
                      <dl>
                        <div><dt>Subject ID</dt><dd><code>{event.subject_id}</code></dd></div>
                        <div><dt>Previous hash</dt><dd><code>{event.previous_hash ?? "Chain root"}</code></dd></div>
                        <div><dt>Event hash</dt><dd><code>{event.event_hash}</code></dd></div>
                      </dl>
                      <strong>Payload</strong>
                      <pre>{JSON.stringify(event.payload, null, 2)}</pre>
                    </details>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <div className="modal-actions"><button className="button button--primary" onClick={onClose} type="button">Done</button></div>
    </Modal>
  );
}
