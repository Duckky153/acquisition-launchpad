import { afterEach, describe, expect, it, vi } from "vitest";
import { launchpadApi } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("launchpad API client", () => {
  it("sends the optimistic version and human note for approval", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "mapping-1" }), { status: 200, headers: { "Content-Type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    await launchpadApi.approveMapping("package-1", "mapping-1", { actor_id: "reviewer", expected_version: 3, note: "Reviewed source evidence." });
    expect(fetchMock).toHaveBeenCalledWith(
      "http://127.0.0.1:8011/v1/packages/package-1/mappings/mapping-1/approve",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ actor_id: "reviewer", expected_version: 3, note: "Reviewed source evidence." }) }),
    );
  });

  it("preserves the backend domain error code and message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: { code: "CONFLICT", message: "mapping version conflict" } }), { status: 409, headers: { "Content-Type": "application/json" } })));
    await expect(launchpadApi.recomputeReadiness("missing")).rejects.toMatchObject({ code: "CONFLICT", status: 409, message: "mapping version conflict" });
  });
});
