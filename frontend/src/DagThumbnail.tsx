import React, { useId } from "react";
import { isJunction, junctionSymbol, type GraphDoc } from "./types";
import {
  attachmentPosition,
  pointOnRoute,
  routePoints,
  svgRoute,
} from "./geometry";
import { edgeLabel } from "./relations";

/** Lightweight SVG only: previews never mount an editor or move its viewport. */
export function DagThumbnail({ doc, label }: { doc: GraphDoc; label: string }) {
  const arrow = "mini-arrow-" + useId().replaceAll(":", "");
  const points = doc.nodes.flatMap((n) => {
    const b = doc.layout.nodes[n.id];
    return [
      { x: b.x, y: b.y },
      { x: b.x + b.width, y: b.y + b.height },
    ];
  });
  for (const e of doc.edges) {
    const route = routePoints(doc, e),
      v = doc.layout.edges[e.id];
    points.push(...route);
    const at = pointOnRoute(route, v.route, v.label_t);
    points.push(
      { x: at.x + v.label_dx - 14, y: at.y + v.label_dy - 14 },
      { x: at.x + v.label_dx + 14, y: at.y + v.label_dy + 14 },
    );
  }
  const x = points.length ? Math.min(...points.map((p) => p.x)) : 0;
  const y = points.length ? Math.min(...points.map((p) => p.y)) : 0;
  const width = Math.max(80, Math.max(...points.map((p) => p.x), x) - x),
    height = Math.max(50, Math.max(...points.map((p) => p.y), y) - y);
  return (
    <svg
      className="dag-thumbnail"
      role="img"
      aria-label={"Aperçu de " + label}
      viewBox={`${x - 20} ${y - 20} ${width + 40} ${height + 40}`}
      preserveAspectRatio="xMidYMid meet"
    >
      <title>{label}</title>
      <defs>
        <marker
          id={arrow}
          viewBox="0 0 8 8"
          refX="7"
          refY="4"
          markerWidth="8"
          markerHeight="8"
          orient="auto"
          markerUnits="userSpaceOnUse"
        >
          <path d="M0,0 L8,4 L0,8 Z" fill="#111" />
        </marker>
      </defs>
      {doc.edges.map((e) => {
        const v = doc.layout.edges[e.id],
          points = routePoints(doc, e),
          symbol = edgeLabel(e),
          p = pointOnRoute(points, v.route, v.label_t);
        return (
          <g key={e.id}>
            <path
              d={svgRoute(points, v.route)}
              fill="none"
              stroke="#111"
              strokeWidth="1.3"
              strokeDasharray={
                v.stroke === "dashed"
                  ? "7 4"
                  : v.stroke === "dotted"
                    ? "2 4"
                    : undefined
              }
              markerEnd={e.kind === "causal" ? `url(#${arrow})` : undefined}
            />
            {symbol && (
              <g
                transform={`translate(${p.x + v.label_dx},${p.y + v.label_dy})`}
              >
                <rect x="-12" y="-11" width="24" height="22" fill="white" />
                <text
                  textAnchor="middle"
                  dominantBaseline="central"
                  fontFamily="serif"
                  fontSize="18"
                >
                  {symbol}
                </text>
              </g>
            )}
          </g>
        );
      })}
      {doc.nodes
        .filter((n) => n.kind === "source" && n.attachment)
        .map((n) => {
          const p = attachmentPosition(doc, n.attachment!),
            b = doc.layout.nodes[n.id];
          return (
            p && (
              <path
                key={"source-" + n.id}
                d={`M${b.x + b.width / 2},${b.y + b.height} L${p.x},${p.y}`}
                fill="none"
                stroke="#555"
                strokeDasharray="2 4"
              />
            )
          );
        })}
      {doc.nodes.map((n) => {
        const b = doc.layout.nodes[n.id],
          group = isJunction(n.kind),
          draft = doc.editor?.node_text[n.id];
        return (
          <g key={n.id}>
            {n.kind === "concept" && (
              <rect
                x={b.x}
                y={b.y}
                width={b.width}
                height={b.height}
                rx="5"
                fill="white"
                stroke="#111"
              />
            )}
            <foreignObject x={b.x} y={b.y} width={b.width} height={b.height}>
              <div className={"mini-node" + (group ? " mini-group" : "")}>
                <span>
                  {draft ??
                    (group
                      ? junctionSymbol(doc, n)
                      : (n.kind === "source" ? "| " : "") +
                        (n.label || n.code.replaceAll("_", " ")))}
                </span>
                {draft === undefined && !!n.subtopics.length && (
                  <small>({n.subtopics.join(", ").replaceAll("_", " ")})</small>
                )}
                {draft === undefined && !!n.scopes.length && (
                  <small>[{n.scopes.join(", ").replaceAll("_", " ")}]</small>
                )}
              </div>
            </foreignObject>
          </g>
        );
      })}
    </svg>
  );
}
