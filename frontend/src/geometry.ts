import type { Box, Point, Port, GraphDoc, GraphEdge } from "./types";
export const direction: Record<Port, Point> = {
  left: { x: -1, y: 0 },
  right: { x: 1, y: 0 },
  top: { x: 0, y: -1 },
  bottom: { x: 0, y: 1 },
  "top-left": { x: -1, y: -1 },
  "top-right": { x: 1, y: -1 },
  "bottom-left": { x: -1, y: 1 },
  "bottom-right": { x: 1, y: 1 },
};
export function anchor(b: Box, p: Port): Point {
  return {
    left: { x: b.x, y: b.y + b.height / 2 },
    right: { x: b.x + b.width, y: b.y + b.height / 2 },
    top: { x: b.x + b.width / 2, y: b.y },
    bottom: { x: b.x + b.width / 2, y: b.y + b.height },
    "top-left": { x: b.x, y: b.y },
    "top-right": { x: b.x + b.width, y: b.y },
    "bottom-left": { x: b.x, y: b.y + b.height },
    "bottom-right": { x: b.x + b.width, y: b.y + b.height },
  }[p];
}
export function routePoints(doc: GraphDoc, e: GraphEdge): Point[] {
  const v = doc.layout.edges[e.id],
    a = anchor(doc.layout.nodes[e.source], v.source_port),
    b = anchor(doc.layout.nodes[e.target], v.target_port);
  if (v.route === "straight") return [a, b];
  let p = v.points;
  if (!p.length && v.route === "orthogonal")
    p = ["left", "right"].includes(v.source_port)
      ? [
          { x: (a.x + b.x) / 2, y: a.y },
          { x: (a.x + b.x) / 2, y: b.y },
        ]
      : [
          { x: a.x, y: (a.y + b.y) / 2 },
          { x: b.x, y: (a.y + b.y) / 2 },
        ];
  if (!p.length) {
    const d = Math.max(40, Math.hypot(a.x - b.x, a.y - b.y) / 2),
      u = direction[v.source_port],
      w = direction[v.target_port];
    p = [
      { x: a.x + u.x * d, y: a.y + u.y * d },
      { x: b.x + w.x * d, y: b.y + w.y * d },
    ];
  }
  return [a, ...p, b];
}
export function pointOnRoute(p: Point[], route: string, t: number): Point {
  if (route === "bezier") {
    const [a, b, c, d] = p;
    return {
      x:
        (1 - t) ** 3 * a.x +
        3 * (1 - t) ** 2 * t * b.x +
        3 * (1 - t) * t * t * c.x +
        t ** 3 * d.x,
      y:
        (1 - t) ** 3 * a.y +
        3 * (1 - t) ** 2 * t * b.y +
        3 * (1 - t) * t * t * c.y +
        t ** 3 * d.y,
    };
  }
  const lengths = p
    .slice(1)
    .map((b, i) => Math.hypot(b.x - p[i].x, b.y - p[i].y));
  let r = lengths.reduce((a, b) => a + b, 0) * t;
  for (let i = 0; i < lengths.length; i++) {
    const d = lengths[i];
    if (r <= d && d)
      return {
        x: p[i].x + ((p[i + 1].x - p[i].x) * r) / d,
        y: p[i].y + ((p[i + 1].y - p[i].y) * r) / d,
      };
    r -= d;
  }
  return p.at(-1)!;
}
export function svgRoute(p: Point[], route: string): string {
  return route === "bezier"
    ? `M${p[0].x},${p[0].y} C${p[1].x},${p[1].y} ${p[2].x},${p[2].y} ${p[3].x},${p[3].y}`
    : `M${p.map((v) => `${v.x},${v.y}`).join(" L")}`;
}
export function attachmentPosition(
  doc: GraphDoc,
  a: { kind: string; id: string },
): Point | null {
  if (a.kind === "node") {
    const b = doc.layout.nodes[a.id];
    if (!b) return null;
    return { x: b.x + b.width / 2, y: b.y };
  }
  if (a.kind === "edge") {
    const e = doc.edges.find((e) => e.id === a.id);
    if (!e || !doc.layout.edges[e.id]) return null;
    return pointOnRoute(routePoints(doc, e), doc.layout.edges[e.id].route, 0.5);
  }
  const p = doc.paths.find((p) => p.id === a.id);
  if (!p) return null;
  const boxes = p.node_ids
    .filter((id) => doc.nodes.find((n) => n.id === id)?.kind !== "source")
    .map((id) => doc.layout.nodes[id])
    .filter(Boolean);
  return boxes.length
    ? {
        x:
          (Math.min(...boxes.map((b) => b.x)) +
            Math.max(...boxes.map((b) => b.x + b.width))) /
          2,
        y: Math.min(...boxes.map((b) => b.y)) - 20,
      }
    : { x: 0, y: 0 };
}
