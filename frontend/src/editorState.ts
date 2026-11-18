import { clone, type GraphDoc } from "./types";

export function stable(value: unknown): string {
  return JSON.stringify(value, (_key, item) =>
    item && typeof item === "object" && !Array.isArray(item)
      ? Object.fromEntries(
          Object.entries(item).sort(([a], [b]) => a.localeCompare(b)),
        )
      : item,
  );
}
export const same = (a: unknown, b: unknown) => stable(a) === stable(b);

export function removeObjects(
  document: GraphDoc,
  ids: string[],
  edgeId: string | null = null,
): GraphDoc {
  const doc = clone(document),
    removed = new Set(ids),
    edges = new Set(
      doc.edges
        .filter(
          (e) =>
            removed.has(e.source) || removed.has(e.target) || e.id === edgeId,
        )
        .map((e) => e.id),
    );
  doc.nodes = doc.nodes.filter((n) => !removed.has(n.id));
  doc.edges = doc.edges.filter((e) => !edges.has(e.id));
  for (const id of removed) {
    delete doc.layout.nodes[id];
    if (doc.editor) delete doc.editor.node_text[id];
  }
  for (const id of edges) delete doc.layout.edges[id];
  for (const node of doc.nodes)
    if (node.dominant && removed.has(node.dominant)) node.dominant = null;
  for (const node of doc.nodes)
    if (
      node.attachment &&
      (removed.has(node.attachment.id) || edges.has(node.attachment.id))
    )
      node.attachment = null;
  for (const path of doc.paths) {
    path.node_ids = path.node_ids.filter((id) => !removed.has(id));
    path.edge_ids = path.edge_ids.filter((id) => !edges.has(id));
  }
  if (doc.editor && !Object.keys(doc.editor.node_text).length)
    delete doc.editor;
  return doc;
}

type Timeline = { past: GraphDoc[]; future: GraphDoc[]; cursor: number | null };
const timelines = new Map<string, Timeline>();
export function timelineFor(key: string): Timeline {
  if (!timelines.has(key))
    timelines.set(key, { past: [], future: [], cursor: null });
  return timelines.get(key)!;
}
export type SavedView = {
  x: number;
  y: number;
  zoom: number;
  width: number;
  height: number;
};
const views = new Map<string, SavedView>();
export function readView(key: string): SavedView | null {
  try {
    const v =
      views.get(key) ??
      JSON.parse(sessionStorage.getItem("narrative-view:" + key) || "null");
    if (
      v &&
      [v.x, v.y, v.zoom, v.width, v.height].every(Number.isFinite) &&
      v.zoom >= 0.15 &&
      v.zoom <= 2.5
    )
      return v;
  } catch {}
  return null;
}
export function saveView(key: string, v: SavedView) {
  views.set(key, v);
  try {
    sessionStorage.setItem("narrative-view:" + key, JSON.stringify(v));
  } catch {}
}
export function centeredView(
  view: SavedView,
  width: number,
  height: number,
): SavedView {
  return {
    ...view,
    x: view.x + (width - view.width) / 2,
    y: view.y + (height - view.height) / 2,
    width,
    height,
  };
}
