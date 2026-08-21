import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { workspaceFixture } from "../test/fixtures";
import { EntityRail } from "./EntityRail";

describe("EntityRail", () => {
  it("shows parent-first structure, source systems, and review progress", () => {
    render(<EntityRail onSelectEntity={vi.fn()} packageDetail={workspaceFixture.package} readiness={workspaceFixture.readiness.entities} selectedEntityId={null} sourceAccounts={workspaceFixture.sourceAccounts} />);
    expect(screen.getByRole("button", { name: /All entities/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByText("Synthetic ERP")).toBeInTheDocument();
    expect(screen.getByText("Synthetic Export")).toBeInTheDocument();
    expect(screen.getAllByText("1/2 mapped")).toHaveLength(2);
  });

  it("changes the mapping scope without mutating data", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<EntityRail onSelectEntity={onSelect} packageDetail={workspaceFixture.package} readiness={workspaceFixture.readiness.entities} selectedEntityId={null} sourceAccounts={workspaceFixture.sourceAccounts} />);
    await user.click(screen.getByRole("button", { name: /Child Services/ }));
    expect(onSelect).toHaveBeenCalledWith("entity-2");
  });

  it("states later modules as unimplemented", () => {
    render(<EntityRail onSelectEntity={vi.fn()} packageDetail={workspaceFixture.package} readiness={workspaceFixture.readiness.entities} selectedEntityId={null} sourceAccounts={workspaceFixture.sourceAccounts} />);
    expect(screen.getAllByText("Not implemented")).toHaveLength(3);
    expect(screen.getByText("Intercompany eliminations")).toBeInTheDocument();
  });
});
