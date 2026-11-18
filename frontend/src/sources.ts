import type { GraphDoc, GraphNode } from "./types";

type Attachment = NonNullable<GraphNode["attachment"]>;

export function attachmentPaths(doc: GraphDoc, target: Attachment): string[] {
  return doc.paths
    .filter((p) =>
      target.kind === "path"
        ? p.id === target.id
        : (target.kind === "node" ? p.node_ids : p.edge_ids).includes(
            target.id,
          ),
    )
    .map((p) => p.id);
}

// Membership follows what the annotation describes, never the last DAG used
// for drawing. One source can describe a shared concept in several DAGs.
export function attachSource(
  doc: GraphDoc,
  node: GraphNode,
  target: Attachment,
) {
  const paths = attachmentPaths(doc, target);
  if (
    !paths.length ||
    (target.kind === "node" &&
      doc.nodes.find((n) => n.id === target.id)?.kind === "source")
  )
    throw new Error("Choisissez un DAG, un topic ou une relation existante.");
  node.attachment = target;
  for (const p of doc.paths) {
    if (!paths.includes(p.id))
      p.node_ids = p.node_ids.filter((id) => id !== node.id);
    else if (!p.node_ids.includes(node.id)) p.node_ids.push(node.id);
  }
}

export function sourceTarget(
  doc: GraphDoc,
  activePath: string,
  nodeId?: string | null,
  edgeId?: string | null,
): Attachment {
  if (nodeId && doc.nodes.some((n) => n.id === nodeId && n.kind !== "source"))
    return { kind: "node", id: nodeId };
  if (edgeId && doc.edges.some((e) => e.id === edgeId))
    return { kind: "edge", id: edgeId };
  const selectedSource = doc.nodes.find(
    (n) => n.id === nodeId && n.kind === "source",
  );
  return (
    selectedSource?.attachment ?? {
      kind: "path",
      id: doc.paths.find((p) => p.id === activePath)?.id ?? doc.paths[0].id,
    }
  );
}

export function convertToSource(doc: GraphDoc, id: string, activePath: string) {
  const node = doc.nodes.find((n) => n.id === id)!;
  if (node.kind === "source") return;
  const incoming = doc.edges.find((e) => e.target === id);
  const owners = doc.paths.filter((p) => p.node_ids.includes(id));
  const path =
    owners.find((p) => p.id === activePath)?.id ?? owners[0]?.id ?? activePath;
  const target = sourceTarget(doc, path, incoming?.source);
  const removed = new Set(
    doc.edges
      .filter((e) => e.source === id || e.target === id)
      .map((e) => e.id),
  );
  doc.edges = doc.edges.filter((e) => !removed.has(e.id));
  for (const eid of removed) delete doc.layout.edges[eid];
  for (const p of doc.paths)
    p.edge_ids = p.edge_ids.filter((eid) => !removed.has(eid));
  for (const n of doc.nodes) {
    if (n.attachment?.kind === "edge" && removed.has(n.attachment.id)) {
      attachSource(doc, n, {
        kind: "path",
        id: doc.paths.find((p) => p.node_ids.includes(n.id))?.id ?? path,
      });
    } else if (n.attachment?.kind === "node" && n.attachment.id === id) {
      attachSource(doc, n, { kind: "path", id: path });
    }
  }
  node.kind = "source";
  node.code = "";
  node.label = "";
  node.subtopics = [];
  node.scopes = [];
  attachSource(doc, node, target);
}

export function dagLabel(doc: GraphDoc, id: string) {
  const i = doc.paths.findIndex((p) => p.id === id);
  if (i < 0) return "DAG inconnu";
  const label = doc.paths[i].label;
  return /^(Chemin|Branche|DAG) \d+$/.test(label)
    ? `DAG ${i + 1}`
    : `DAG ${i + 1} · ${label}`;
}
