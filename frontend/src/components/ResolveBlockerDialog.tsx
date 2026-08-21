import { useState, type FormEvent } from "react";
import type { Blocker } from "../types";
import { Modal } from "./Modal";

interface ResolutionSubmission {
  actorId: string;
  note: string;
}

interface ResolveBlockerDialogProps {
  blocker: Blocker;
  busy: boolean;
  onClose: () => void;
  onSubmit: (submission: ResolutionSubmission) => Promise<void>;
}

export function ResolveBlockerDialog({ blocker, busy, onClose, onSubmit }: ResolveBlockerDialogProps): React.ReactElement {
  const [actorId, setActorId] = useState("portfolio-reviewer");
  const [note, setNote] = useState("");
  const submit = (event: FormEvent): void => {
    event.preventDefault();
    if (!actorId.trim() || !note.trim()) return;
    void onSubmit({ actorId: actorId.trim(), note: note.trim() });
  };
  return (
    <Modal description="Only human-created blockers can be resolved here. System blockers clear when the underlying evidence changes." onClose={onClose} title="Resolve review blocker">
      <form className="decision-form" onSubmit={submit}>
        <div className="blocker-dialog-summary"><strong>{blocker.title}</strong><p>{blocker.detail}</p></div>
        <label className="field"><span>Human reviewer ID</span><input onChange={(event) => setActorId(event.target.value)} required value={actorId} /></label>
        <label className="field"><span>Resolution evidence</span><textarea autoFocus onChange={(event) => setNote(event.target.value)} placeholder="What was reviewed or corrected?" required rows={4} value={note} /></label>
        <div className="modal-actions"><button className="button button--quiet" disabled={busy} onClick={onClose} type="button">Cancel</button><button className="button button--primary" disabled={busy || !actorId.trim() || !note.trim()} type="submit">{busy ? "Recording resolution…" : "Resolve blocker"}</button></div>
      </form>
    </Modal>
  );
}
