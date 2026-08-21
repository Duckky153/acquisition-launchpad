import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { workspaceFixture } from "../test/fixtures";
import type { AuditEvent } from "../types";
import { AuditDialog } from "./AuditDialog";

describe("AuditDialog", () => {
  it("exposes reviewer notes, full chain fields, and the event payload", async () => {
    const user = userEvent.setup();
    const baseEvent = workspaceFixture.auditEvents[0];
    if (!baseEvent) throw new Error("audit fixture must include an event");
    const event: AuditEvent = {
      ...baseEvent,
      actor_type: "HUMAN",
      actor_id: "browser-e2e-reviewer",
      event_type: "MAPPING_APPROVED",
      previous_hash: "previous-hash-value",
      payload: {
        decision: "APPROVED",
        decision_note: "Reviewed the synthetic source and target evidence.",
      },
    };
    render(<AuditDialog events={[event]} onClose={vi.fn()} verification={workspaceFixture.auditVerification} />);

    expect(screen.getByText("browser-e2e-reviewer")).toBeInTheDocument();
    expect(screen.getByText("Reviewed the synthetic source and target evidence.")).toBeInTheDocument();
    await user.click(screen.getByText("Inspect event evidence"));

    const dialog = screen.getByRole("dialog", { name: "Audit evidence ledger" });
    expect(within(dialog).getByText("previous-hash-value")).toBeInTheDocument();
    expect(within(dialog).getByText(event.event_hash)).toBeInTheDocument();
    expect(within(dialog).getByText(/"decision_note": "Reviewed the synthetic source/)).toBeInTheDocument();
  });
});
