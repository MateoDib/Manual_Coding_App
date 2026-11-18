/** Move route geometry with its endpoints, without changing graph semantics. */
import type { GraphDoc, Point, Port } from "./types";
import { anchor } from "./geometry";

const close = (a: number, b: number) => Math.abs(a - b) < 1e-6;
const horizontal = (port: Port) => port === "left" || port === "right";

function orthogonalPoints(
  old: Point[],
  start: Point,
  end: Point,
  source: Port,
  target: Port,
): Point[] {
  const fallback = () =>
    horizontal(source) === horizontal(target)
      ? horizontal(source)
        ? [
            { x: (start.x + end.x) / 2, y: start.y },
            { x: (start.x + end.x) / 2, y: end.y },
          ]
        : [
            { x: start.x, y: (start.y + end.y) / 2 },
            { x: end.x, y: (start.y + end.y) / 2 },
          ]
      : [
          horizontal(source)
            ? { x: end.x, y: start.y }
            : { x: start.x, y: end.y },
        ];
  if (
    old.some(
      (p, i) => i > 0 && !close(p.x, old[i - 1].x) && !close(p.y, old[i - 1].y),
    )
  )
    return fallback();
  const distances = [0];
  for (let i = 1; i < old.length; i++)
    distances.push(
      distances[i - 1] +
        Math.hypot(old[i].x - old[i - 1].x, old[i].y - old[i - 1].y),
    );
  const total = distances.at(-1)! || 1;
  const result = old.map((p, i) => {
    const t = distances[i] / total;
    return {
      x: p.x + (start.x - old[0].x) * (1 - t) + (end.x - old.at(-1)!.x) * t,
      y: p.y + (start.y - old[0].y) * (1 - t) + (end.y - old.at(-1)!.y) * t,
    };
  });
  // Preserve the equal-coordinate constraints of every original segment.
  // If both endpoints impose incompatible constraints, introduce a dogleg.
  for (const axis of ["x", "y"] as const) {
    let first = 0;
    for (let last = 1; last <= old.length; last++) {
      if (last < old.length && close(old[last - 1][axis], old[last][axis]))
        continue;
      if (first === 0 && last === old.length && !close(start[axis], end[axis]))
        return fallback();
      const value =
        first === 0
          ? start[axis]
          : last === old.length
            ? end[axis]
            : result.slice(first, last).reduce((sum, p) => sum + p[axis], 0) /
              (last - first);
      for (let i = first; i < last; i++) result[i][axis] = value;
      first = last;
    }
  }
  return result.slice(1, -1);
}

export function followMovedNodes(before: GraphDoc, after: GraphDoc) {
  for (const edge of after.edges) {
    const old = before.edges.find((e) => e.id === edge.id),
      v = after.layout.edges[edge.id],
      previous = before.layout.edges[edge.id];
    if (
      !old ||
      old.source !== edge.source ||
      old.target !== edge.target ||
      !previous ||
      !v.points.length ||
      v.route !== previous.route ||
      v.source_port !== previous.source_port ||
      v.target_port !== previous.target_port ||
      JSON.stringify(v.points) !== JSON.stringify(previous.points)
    )
      continue;
    const a0 = anchor(before.layout.nodes[edge.source], previous.source_port),
      b0 = anchor(before.layout.nodes[edge.target], previous.target_port),
      a = anchor(after.layout.nodes[edge.source], v.source_port),
      b = anchor(after.layout.nodes[edge.target], v.target_port),
      da = { x: a.x - a0.x, y: a.y - a0.y },
      db = { x: b.x - b0.x, y: b.y - b0.y };
    if (close(da.x, 0) && close(da.y, 0) && close(db.x, 0) && close(db.y, 0))
      continue;
    if (close(da.x, db.x) && close(da.y, db.y))
      v.points = v.points.map((p) => ({ x: p.x + da.x, y: p.y + da.y }));
    else if (v.route === "orthogonal")
      v.points = orthogonalPoints(
        [a0, ...previous.points, b0],
        a,
        b,
        v.source_port,
        v.target_port,
      );
    else
      v.points = v.points.map((p, i) => {
        const t = v.points.length === 1 ? 0.5 : i / (v.points.length - 1);
        return {
          x: p.x + da.x * (1 - t) + db.x * t,
          y: p.y + da.y * (1 - t) + db.y * t,
        };
      });
  }
}
