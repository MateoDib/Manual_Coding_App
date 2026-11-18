import type { GraphDoc, GraphEdge } from "./types";
export const relations = [
  ["causal", "→", "Causalité : une flèche avec pointe"],
  ["link", "—", "Trait simple à qualifier, sans pointe"],
  ["definition", "=", "Définition ou équivalence, sans pointe"],
  ["coexistence", "&", "Coexistence entre deux topics, sans pointe"],
  ["addition", "+", "Combinaison additive entre deux topics, sans pointe"],
] as const;
export function edgeLabel(edge: GraphEdge) {
  return edge.kind === "definition"
    ? "="
    : edge.kind === "coexistence"
      ? "&"
      : edge.kind === "addition"
        ? "+"
        : edge.kind === "priority"
          ? edge.dominant === edge.source
            ? ">"
            : "<"
          : null;
}
export function reverseRelation(doc: GraphDoc, id: string) {
  const e = doc.edges.find((e) => e.id === id),
    v = doc.layout.edges[id];
  if (!e || !v) return;
  [e.source, e.target] = [e.target, e.source];
  [v.source_port, v.target_port] = [v.target_port, v.source_port];
  v.points.reverse();
  v.label_t = 1 - v.label_t;
}
