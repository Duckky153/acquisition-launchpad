import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { workspaceFixture } from "../test/fixtures";
import type { SourceAccount } from "../types";
import { KpiStrip } from "./KpiStrip";

function renderStrip(accounts: SourceAccount[]): void {
  render(<KpiStrip accounts={accounts} blockers={workspaceFixture.blockers} currency="USD" readiness={workspaceFixture.readiness} sequence={workspaceFixture.sequence} />);
}

describe("KpiStrip", () => {
  const [pending, approved] = workspaceFixture.sourceAccounts;

  it("uses singular wording when one decision remains", () => {
    renderStrip(workspaceFixture.sourceAccounts);
    expect(screen.getByText("1 decision remains")).toBeInTheDocument();
  });

  it("uses plural wording when several decisions remain", () => {
    const unapproved = workspaceFixture.sourceAccounts.map((account) => ({ ...account, approved_mapping: null }));
    renderStrip(unapproved);
    expect(screen.getByText("2 decisions remain")).toBeInTheDocument();
  });

  it("reports complete human review when every account is approved", () => {
    if (!pending || !approved?.approved_mapping) throw new Error("fixture accounts missing");
    renderStrip([{ ...pending, approved_mapping: approved.approved_mapping }, approved]);
    expect(screen.getByText("Human review complete")).toBeInTheDocument();
  });
});
