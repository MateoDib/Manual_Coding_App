/** Original MIT implementation. No React Flow Pro example code is used. */
import type { Box } from "./types";
export type Guide = {
  axis: "x" | "y";
  value: number;
  from: number;
  to: number;
  label?: string;
};
export function bounds(boxes: Box[]): Box {
  return {
    x: Math.min(...boxes.map((b) => b.x)),
    y: Math.min(...boxes.map((b) => b.y)),
    width:
      Math.max(...boxes.map((b) => b.x + b.width)) -
      Math.min(...boxes.map((b) => b.x)),
    height:
      Math.max(...boxes.map((b) => b.y + b.height)) -
      Math.min(...boxes.map((b) => b.y)),
    locked: false,
  };
}
export function snap(
  moving: Box,
  others: Box[],
  zoom: number,
  disabled = false,
  previous?: { dx: number; dy: number },
): { dx: number; dy: number; guides: Guide[] } {
  if (disabled) return { dx: 0, dy: 0, guides: [] };
  const threshold = 6 / Math.max(0.1, zoom),
    guides: Guide[] = [];
  let dx = 0,
    dy = 0;
  for (const axis of ["x", "y"] as const) {
    const dim = axis === "x" ? "width" : "height",
      cross = axis === "x" ? "y" : "x",
      crossDim = axis === "x" ? "height" : "width";
    const anchors = [
      moving[axis],
      moving[axis] + moving[dim] / 2,
      moving[axis] + moving[dim],
    ];
    let best: { distance: number; delta: number; guide: Guide } | null = null;
    for (const o of others)
      for (const target of [o[axis], o[axis] + o[dim] / 2, o[axis] + o[dim]])
        for (const a of anchors) {
          const delta = target - a,
            distance = Math.abs(delta),
            sticky =
              previous &&
              Math.abs(delta - (axis === "x" ? previous.dx : previous.dy)) <
                0.05;
          const limit = sticky ? threshold * 1.5 : threshold;
          if (distance <= limit && (!best || distance < best.distance))
            best = {
              distance,
              delta,
              guide: {
                axis,
                value: target,
                from: Math.min(o[cross], moving[cross]) - 15,
                to:
                  Math.max(
                    o[cross] + o[crossDim],
                    moving[cross] + moving[crossDim],
                  ) + 15,
              },
            };
        }
    // Equal clear-space gaps, not distances between centers. Consider nearby neighbors.
    const peers = others
      .filter(
        (o) =>
          Math.abs(
            o[cross] + o[crossDim] / 2 - (moving[cross] + moving[crossDim] / 2),
          ) < Math.max(o[crossDim], moving[crossDim]),
      )
      .sort((a, b) => a[axis] - b[axis]);
    for (let i = 0; i < peers.length - 1; i++) {
      const a = peers[i],
        b = peers[i + 1],
        gap = b[axis] - (a[axis] + a[dim]);
      if (gap < 0) continue;
      for (const target of [
        b[axis] + b[dim] + gap,
        a[axis] - gap - moving[dim],
      ]) {
        const delta = target - moving[axis];
        if (
          Math.abs(delta) <= threshold &&
          (!best || Math.abs(delta) < best.distance)
        )
          best = {
            distance: Math.abs(delta),
            delta,
            guide: {
              axis,
              value: target,
              from: Math.min(a[cross], b[cross], moving[cross]) - 20,
              to:
                Math.max(
                  a[cross] + a[crossDim],
                  b[cross] + b[crossDim],
                  moving[cross] + moving[crossDim],
                ) + 20,
              label: "Espacements égaux",
            },
          };
      }
    }
    if (best) {
      if (axis === "x") dx = best.delta;
      else dy = best.delta;
      guides.push(best.guide);
    }
  }
  return { dx, dy, guides };
}
export function distribute(
  boxes: Record<string, Box>,
  ids: string[],
  axis: "x" | "y",
): Record<string, Box> {
  const result = structuredClone(boxes),
    dim = axis === "x" ? "width" : "height";
  const ordered = ids
    .filter((id) => !boxes[id].locked)
    .sort((a, b) => boxes[a][axis] - boxes[b][axis]);
  if (ordered.length < 3) return result;
  const first = boxes[ordered[0]],
    last = boxes[ordered.at(-1)!],
    space =
      (last[axis] +
        last[dim] -
        first[axis] -
        ordered.reduce((sum, id) => sum + boxes[id][dim], 0)) /
      (ordered.length - 1);
  let value = first[axis];
  for (const id of ordered) {
    result[id][axis] = value;
    value += result[id][dim] + space;
  }
  return result;
}
