import { useState, type FormEvent } from "react";
import type { Mapping } from "../types";
import { Modal } from "./Modal";

export interface DecisionSubmission {
  actorId: string;
  note: string;
}

interface DecisionDialogProps {
  mode: "approve" | "reject";
  mappings: Mapping[];
  busy: boolean;
  onClose: () => void;
  onSubmit: (submission: DecisionSubmission) => Promise<void>;
}

export function DecisionDialog({ mode, mappings, busy, onClose, onSubmit }: DecisionDialogProps): React.ReactElement {
  const [actorId, setActorId] = useState("portfolio-reviewer");
  const [note, setNote] = useState("");

  const submit = (event: FormEvent): void => {
    event.preventDefault();
    if (!actorId.trim() || !note.trim()) return;
    void onSubmit({ actorId: actorId.trim(), note: note.trim() });
  };

  const verb = mode === "approve" ? "Approve" : "Reject";
  return (
    <Modal
      description={`${verb} ${mappings.length} human mapping decision${mappings.length === 1 ? "" : "s"}. Confidence never approves a mapping automatically.`}
      onClose={onClose}
      title={`${verb} account ${mappings.length === 1 ? "mapping" : "mappings"}`}
    >
      <form className="decision-form" onSubmit={submit}>
        <div className="decision-summary">
          {mappings.slice(0, 4).map((mapping) => (
            <div className="decision-summary__row" key={mapping.id}>
              <span>{mapping.entity_external_id} · {mapping.source_account_code}</span>
              <strong>{mapping.canonical_account_code} · {mapping.canonical_account_name}</strong>
            </div>
          ))}
          {mappings.length > 4 ? <p>And {mappings.length - 4} more selected mappings.</p> : null}
        </div>
        <label className="field">
          <span>Human reviewer ID</span>
          <input autoComplete="off" onChange={(event) => setActorId(event.target.value)} required value={actorId} />
        </label>
        <label className="field">
          <span>Decision note</span>
          <textarea
            autoFocus
            onChange={(event) => setNote(event.target.value)}
            placeholder={mode === "approve" ? "What source evidence did you review?" : "Why is this mapping not acceptable?"}
            required
            rows={4}
            value={note}
          />
        </label>
        <div className="modal-actions">
          <button className="button button--quiet" disabled={busy} onClick={onClose} type="button">Cancel</button>
          <button className={`button ${mode === "reject" ? "button--danger" : "button--primary"}`} disabled={busy || !actorId.trim() || !note.trim()} type="submit">
            {busy ? "Recording decision…" : `${verb} ${mappings.length}`}
          </button>
        </div>
      </form>
    </Modal>
  );
}
