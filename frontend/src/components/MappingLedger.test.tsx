import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { workspaceFixture } from "../test/fixtures";
import { MappingLedger } from "./MappingLedger";

function renderLedger(overrides?: { selected?: Set<string>; guidedFocus?: { sourceCode: string; requestId: number } | null }) {
  const onSelectionChange = vi.fn();
  const onRequestDecision = vi.fn();
  const onCreateMapping = vi.fn().mockResolvedValue(undefined);
  render(
    <MappingLedger
      accounts={workspaceFixture.sourceAccounts}
      busy={false}
      canonicalAccounts={workspaceFixture.canonicalAccounts}
      currency="USD"
      guidedFocus={overrides?.guidedFocus ?? null}
      onCreateMapping={onCreateMapping}
      onRequestDecision={onRequestDecision}
      onSelectionChange={onSelectionChange}
      readiness={workspaceFixture.readiness.entities}
      selectedSourceIds={overrides?.selected ?? new Set()}
    />,
  );
  return { onSelectionChange, onRequestDecision, onCreateMapping };
}

describe("MappingLedger", () => {
  it("renders source evidence and never labels a suggestion approved", () => {
    renderLedger();
    expect(screen.getByText("Operating Bank")).toBeInTheDocument();
    expect(screen.getByText("94% suggested")).toBeInTheDocument();
    expect(screen.getByText("Suggested")).toBeInTheDocument();
    expect(screen.getByText("by reviewer")).toBeInTheDocument();
  });

  it("filters by query and mapping decision state", async () => {
    const user = userEvent.setup();
    renderLedger();
    await user.type(screen.getByRole("searchbox", { name: "Search account mappings" }), "P-115");
    expect(screen.getByText("Trade Receivables")).toBeInTheDocument();
    expect(screen.queryByText("Operating Bank")).not.toBeInTheDocument();
    await user.clear(screen.getByRole("searchbox", { name: "Search account mappings" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Filter by mapping status" }), "PENDING");
    expect(screen.getByText("Operating Bank")).toBeInTheDocument();
    expect(screen.queryByText("Trade Receivables")).not.toBeInTheDocument();
  });

  it("selects only pending rows and passes their best candidates to human review", async () => {
    const user = userEvent.setup();
    const selected = new Set(["source-1"]);
    const { onRequestDecision } = renderLedger({ selected });
    const approve = screen.getByRole("button", { name: /Approve selected/ });
    await user.click(approve);
    expect(onRequestDecision).toHaveBeenCalledWith("approve", [expect.objectContaining({ id: "mapping-1", status: "SUGGESTED" })]);
    expect(screen.getByRole("checkbox", { name: "Select P-115" })).toBeDisabled();
  });

  it("opens evidence and routes candidate approval and rejection explicitly", async () => {
    const user = userEvent.setup();
    const { onRequestDecision } = renderLedger();
    await user.click(screen.getByRole("button", { name: "Show mapping evidence for P-101" }));
    expect(screen.getByText("Exact bank and cash semantic match.")).toBeInTheDocument();
    const candidates = screen.getAllByRole("article");
    const firstCandidate = candidates.find((item) => within(item).queryByText("Cash"));
    if (!firstCandidate) throw new Error("candidate card missing");
    await user.click(within(firstCandidate).getByRole("button", { name: "Review & approve" }));
    expect(onRequestDecision).toHaveBeenCalledWith("approve", [expect.objectContaining({ id: "mapping-1" })]);
    await user.click(within(firstCandidate).getByRole("button", { name: "Reject" }));
    expect(onRequestDecision).toHaveBeenCalledWith("reject", [expect.objectContaining({ id: "mapping-1" })]);
  });

  it("focuses and expands the requested guided-demo source account", () => {
    renderLedger({ guidedFocus: { sourceCode: "P-101", requestId: 1 } });
    expect(screen.getByRole("searchbox", { name: "Search account mappings" })).toHaveValue("P-101");
    expect(screen.getByRole("button", { name: "Hide mapping evidence for P-101" })).toBeInTheDocument();
    expect(screen.getByText("Exact bank and cash semantic match.")).toBeInTheDocument();
    expect(screen.queryByText("Trade Receivables")).not.toBeInTheDocument();
  });

  it("creates a same-type candidate but does not auto-approve it", async () => {
    const user = userEvent.setup();
    const { onCreateMapping } = renderLedger();
    await user.click(screen.getByRole("button", { name: "Show mapping evidence for P-101" }));
    await user.click(screen.getByRole("button", { name: "Add candidate" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Compatible canonical account" }), "canonical-ar");
    await user.type(screen.getByRole("textbox", { name: "Why should this be considered?" }), "Reviewed the synthetic source classification.");
    await user.click(screen.getByRole("button", { name: "Save candidate" }));
    expect(onCreateMapping).toHaveBeenCalledWith("source-1", "canonical-ar", "portfolio-reviewer", "Reviewed the synthetic source classification.");
  });
});
