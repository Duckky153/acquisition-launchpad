import { describe, expect, it } from "vitest";
import { bestPendingMapping } from "./mappings";
import { workspaceFixture } from "../test/fixtures";

describe("mapping queue", () => {
  it("selects the highest-confidence pending candidate without treating it as approved", () => {
    const account = workspaceFixture.sourceAccounts[0];
    if (!account) throw new Error("fixture account missing");
    const candidate = bestPendingMapping(account);
    expect(candidate?.id).toBe("mapping-1");
    expect(candidate?.status).toBe("SUGGESTED");
    expect(account.approved_mapping).toBeNull();
  });

  it("does not select approved or rejected records as pending", () => {
    const account = workspaceFixture.sourceAccounts[1];
    if (!account) throw new Error("fixture account missing");
    expect(bestPendingMapping(account)).toBeNull();
  });
});
