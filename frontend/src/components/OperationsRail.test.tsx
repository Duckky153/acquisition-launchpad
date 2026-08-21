import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { workspaceFixture } from "../test/fixtures";
import { OperationsRail } from "./OperationsRail";

describe("OperationsRail", () => {
  function renderRail() {
    const onResolve = vi.fn();
    const onViewAudit = vi.fn();
    render(<OperationsRail auditEvents={workspaceFixture.auditEvents} auditVerification={workspaceFixture.auditVerification} blockers={workspaceFixture.blockers} busy={false} entities={workspaceFixture.package.entities} onResolveBlocker={onResolve} onViewAudit={onViewAudit} sequence={workspaceFixture.sequence} />);
    return { onResolve, onViewAudit };
  }

  it("distinguishes system blockers from resolvable human blockers", async () => {
    const user = userEvent.setup();
    const { onResolve } = renderRail();
    expect(screen.getByText("Resolve through source correction")).toBeInTheDocument();
    const resolve = screen.getByRole("button", { name: "Resolve with note" });
    await user.click(resolve);
    expect(onResolve).toHaveBeenCalledWith(expect.objectContaining({ id: "blocker-manual", system_generated: false }));
  });

  it("keeps resolved history hidden until requested", async () => {
    const user = userEvent.setup();
    renderRail();
    expect(screen.queryByText("Old note")).not.toBeInTheDocument();
    await user.click(screen.getByRole("checkbox", { name: "Show resolved history" }));
    expect(screen.getByText("Old note")).toBeInTheDocument();
    expect(screen.getByText("Resolved by")).toBeInTheDocument();
    expect(screen.getByText("reviewer")).toBeInTheDocument();
    expect(screen.getByText("Resolution note")).toBeInTheDocument();
    expect(screen.getByText("Confirmed.")).toBeInTheDocument();
  });

  it("renders dependency order and exposes the audit ledger", async () => {
    const user = userEvent.setup();
    const { onViewAudit } = renderRail();
    expect(screen.getByText("Entity intake")).toBeInTheDocument();
    expect(screen.getByText("Blocked by Unapproved Account Mapping")).toBeInTheDocument();
    expect(screen.getByText("Hash chain verified")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Open evidence ledger/ }));
    expect(onViewAudit).toHaveBeenCalledOnce();
  });
});
