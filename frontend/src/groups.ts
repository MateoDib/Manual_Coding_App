/** A joint group has members; a causal edge may target the group itself. */
import {
  defaultBox,
  defaultEdgeView,
  newNode,
  uid,
  type GraphDoc,
  type Port,
  isJunction,
  type JunctionKind,
} from "./types";
import { pointOnRoute, routePoints } from "./geometry";
import { newRecord } from "./tracking";

export function facingPort(
  from: { x: number; y: number },
  to: { x: number; y: number },
): Port {
  const dx = to.x - from.x,
    dy = to.y - from.y;
  return Math.abs(dx) >= Math.abs(dy)
    ? dx >= 0
      ? "right"
      : "left"
    : dy >= 0
      ? "bottom"
      : "top";
}

export function materializeGroup(doc: GraphDoc, edgeId: string): string {
  const edge = doc.edges.find((e) => e.id === edgeId);
  if (!edge || !isJunction(edge.kind))
    throw Error("Choisissez une relation &, +, =, > ou <.");
  const v = doc.layout.edges[edgeId],
    middle = pointOnRoute(routePoints(doc, edge), v.route, v.label_t),
    center = { x: middle.x + v.label_dx, y: middle.y + v.label_dy },
    group = newNode("", edge.kind as JunctionKind);
  const previousMeta = doc.tracking?.objects[edgeId];
  if (group.kind === "priority") group.dominant = edge.dominant;
  doc.nodes.push(group);
  doc.layout.nodes[group.id] = defaultBox(center.x - 14, center.y - 14, 28, 28);
  // The existing occurrence remains as a membership; its change is auditable.
  const oldTarget = edge.target,
    newEdgeId = uid("e");
  edge.kind = "membership";
  edge.target = group.id;
  edge.dominant = null;
  const a = doc.layout.nodes[edge.source],
    b = doc.layout.nodes[oldTarget];
  doc.layout.edges[edgeId] = {
    ...defaultEdgeView(),
    source_port: v.source_port,
    target_port: facingPort(center, {
      x: a.x + a.width / 2,
      y: a.y + a.height / 2,
    }),
  };
  doc.edges.push({
    id: newEdgeId,
    kind: "membership",
    source: oldTarget,
    target: group.id,
    dominant: null,
  });
  doc.layout.edges[newEdgeId] = {
    ...defaultEdgeView(),
    source_port: v.target_port,
    target_port: facingPort(center, {
      x: b.x + b.width / 2,
      y: b.y + b.height / 2,
    }),
  };
  for (const path of doc.paths)
    if (path.edge_ids.includes(edgeId)) {
      path.node_ids.push(group.id);
      path.edge_ids.push(newEdgeId);
    }
  // A citation for the coexistence still describes this same joint group.
  // No inherited source occurrence is invented for the new representation.
  if (doc.tracking && previousMeta)
    doc.tracking.objects[group.id] = {
      ...newRecord(),
      quote: { ...previousMeta.quote },
      review: previousMeta.review,
    };
  for (const node of doc.nodes)
    if (node.attachment?.kind === "edge" && node.attachment.id === edgeId)
      node.attachment = { kind: "node", id: group.id };
  return group.id;
}
