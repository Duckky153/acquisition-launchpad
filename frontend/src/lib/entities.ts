import type { EntitySummary } from "../types";

export interface EntityNode {
  entity: EntitySummary;
  children: EntityNode[];
  depth: number;
}

export function buildEntityTree(entities: EntitySummary[]): EntityNode[] {
  const byParent = new Map<string | null, EntitySummary[]>();
  for (const entity of entities) {
    const siblings = byParent.get(entity.parent_id) ?? [];
    siblings.push(entity);
    byParent.set(entity.parent_id, siblings);
  }
  for (const siblings of byParent.values()) {
    siblings.sort((left, right) => left.name.localeCompare(right.name));
  }

  const visit = (entity: EntitySummary, depth: number, visited: Set<string>): EntityNode => {
    if (visited.has(entity.id)) {
      return { entity, children: [], depth };
    }
    const nextVisited = new Set(visited).add(entity.id);
    return {
      entity,
      depth,
      children: (byParent.get(entity.id) ?? []).map((child) =>
        visit(child, depth + 1, nextVisited),
      ),
    };
  };

  return (byParent.get(null) ?? []).map((entity) => visit(entity, 0, new Set()));
}

export function flattenEntityTree(nodes: EntityNode[]): EntityNode[] {
  return nodes.flatMap((node) => [node, ...flattenEntityTree(node.children)]);
}
