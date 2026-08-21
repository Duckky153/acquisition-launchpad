import { describe, expect, it } from "vitest";
import { formatBalance, formatCents, humanizeConstant, readinessLabel, truncateHash } from "./format";
import { workspaceFixture } from "../test/fixtures";

describe("format utilities", () => {
  it("formats integer cents without introducing decimal drift", () => {
    expect(formatCents(250000000)).toBe("$2,500,000");
    expect(formatCents(1)).toBe("$0");
  });

  it("labels debit, credit, zero, and missing balances", () => {
    const account = workspaceFixture.sourceAccounts[0];
    if (!account) throw new Error("fixture account missing");
    expect(formatBalance(account)).toBe("$1,200 Dr");
    expect(formatBalance({ ...account, debit_cents: 0, credit_cents: 4000 })).toBe("$40 Cr");
    expect(formatBalance({ ...account, debit_cents: 0, credit_cents: 0 })).toBe("$0");
    expect(formatBalance({ ...account, debit_cents: null })).toBe("Missing");
  });

  it("turns backend constants into operator language", () => {
    expect(humanizeConstant("DATA_PREPARATION_READY")).toBe("Data Preparation Ready");
    expect(readinessLabel("DATA_PREPARATION_READY")).toBe("Data prep ready");
  });

  it("keeps long hashes recognizable without flooding the UI", () => {
    expect(truncateHash("1234567890abcdefghijkl")).toBe("12345678…ghijkl");
  });
});
