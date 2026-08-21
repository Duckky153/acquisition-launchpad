import { describe, expect, it } from "vitest";
import { buildEntityTree, flattenEntityTree } from "./entities";
import { workspaceFixture } from "../test/fixtures";

describe("entity hierarchy", () => {
  it("builds the parent-child structure deterministically", () => {
    const tree = buildEntityTree(workspaceFixture.package.entities);
    expect(tree).toHaveLength(1);
    expect(tree[0]?.entity.external_id).toBe("PARENT");
    expect(tree[0]?.children[0]?.entity.external_id).toBe("CHILD");
    expect(tree[0]?.children[0]?.depth).toBe(1);
  });

  it("flattens in dependency-friendly parent-first order", () => {
    const flat = flattenEntityTree(buildEntityTree(workspaceFixture.package.entities));
    expect(flat.map((node) => node.entity.external_id)).toEqual(["PARENT", "CHILD"]);
  });
});
