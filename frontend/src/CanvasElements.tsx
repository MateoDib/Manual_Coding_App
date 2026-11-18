import React, {
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
} from "react";
import {
  Handle,
  Position,
  NodeResizer,
  NodeToolbar,
  useReactFlow,
  type Node,
  type NodeProps,
  type EdgeProps,
} from "@xyflow/react";
import {
  type GraphNode,
  type Port,
  portLabels,
  isJunction,
  junctionSymbol,
} from "./types";
import { nodeText } from "./entry";
import { Context } from "./editorContext";
import { routePoints, pointOnRoute, svgRoute } from "./geometry";
import { entryContext, suggest, completeEntry } from "./suggestions";
import { edgeLabel } from "./relations";
export type FlowNode = Node<GraphNode>;
const positions: Record<Port, Position> = {
  left: Position.Left,
  right: Position.Right,
  top: Position.Top,
  bottom: Position.Bottom,
  "top-left": Position.Top,
  "top-right": Position.Top,
  "bottom-left": Position.Bottom,
  "bottom-right": Position.Bottom,
};
function InlineText({ data }: { data: GraphNode }) {
  const {
    editText,
    stopEditing,
    initialText,
    undoGraph,
    redoGraph,
    vocabulary,
  } = useContext(Context);
  const [text, setText] = useState(
    () => initialText(data.id) ?? nodeText(data),
  );
  const input = useRef<HTMLTextAreaElement>(null);
  const requestedSelection = useRef<number | null>(null);
  useLayoutEffect(() => {
    if (requestedSelection.current === null || !input.current) return;
    const at = requestedSelection.current;
    requestedSelection.current = null;
    input.current.focus({ preventScroll: true });
    input.current.setSelectionRange(at, at);
  });
  const rf = useReactFlow(),
    node = rf.getNode(data.id),
    screen = node ? rf.flowToScreenPosition(node.position) : { x: 0, y: 0 };
  const [cursor, setCursor] = useState(text.length),
    [active, setActive] = useState(-1),
    [hidden, setHidden] = useState(false);
  const context = entryContext(text, cursor, data.code),
    options = hidden ? [] : suggest(context, vocabulary);
  const choose = (index: number) => {
    if (!context || !options[index]) return;
    const item = options[index],
      next = completeEntry(text, context, item.value);
    requestedSelection.current = next.cursor;
    past.current.push(text);
    future.current = [];
    setText(next.text);
    setCursor(next.cursor);
    setActive(-1);
    setHidden(true);
    editText(data.id, next.text, false);
  };
  const past = useRef<string[]>([]),
    future = useRef<string[]>([]);
  useEffect(() => {
    // React Flow completes its node-focus handling after the double-click.
    // Focus the text field afterwards, or its own blur would close it at once.
    const timer = setTimeout(() => {
      // Fast typing may already have started. Never select that new text and
      // let the next keystroke replace it, or move focus away from another UI.
      if (past.current.length) return;
      input.current?.focus({ preventScroll: true });
      input.current?.select();
    }, 40);
    return () => clearTimeout(timer);
  }, []);
  return (
    <>
      <textarea
        ref={input}
        className="inline-text nodrag nopan nowheel"
        aria-label="Texte du bloc"
        value={text}
        maxLength={2000}
        placeholder="Écrire un topic…"
        aria-autocomplete="list"
        aria-expanded={options.length > 0}
        aria-controls={options.length ? `suggest-${data.id}` : undefined}
        aria-activedescendant={
          active >= 0 ? `suggest-${data.id}-${active}` : undefined
        }
        onSelect={(e) => setCursor(e.currentTarget.selectionStart)}
        onChange={(e) => {
          past.current.push(text);
          future.current = [];
          setText(e.target.value);
          setCursor(e.target.selectionStart);
          setActive(-1);
          setHidden(false);
          editText(data.id, e.target.value, false);
        }}
        onKeyDown={(e) => {
          e.stopPropagation();
          if (
            options.length &&
            (e.key === "ArrowDown" || e.key === "ArrowUp")
          ) {
            e.preventDefault();
            setActive(
              (v) =>
                (v + (e.key === "ArrowDown" ? 1 : -1) + options.length) %
                options.length,
            );
            return;
          }
          if (
            options.length &&
            (e.key === "Tab" || (e.key === "Enter" && active >= 0))
          ) {
            e.preventDefault();
            choose(active < 0 ? 0 : active);
            return;
          }
          if (options.length && e.key === "Escape") {
            e.preventDefault();
            setHidden(true);
            setActive(-1);
            return;
          }
          if (
            (e.key === ")" || e.key === "]") &&
            text[cursor] === e.key &&
            input.current?.selectionEnd === cursor
          ) {
            e.preventDefault();
            setCursor(cursor + 1);
            input.current.setSelectionRange(cursor + 1, cursor + 1);
            return;
          }
          if (
            (e.metaKey || e.ctrlKey) &&
            ["z", "y"].includes(e.key.toLowerCase())
          ) {
            e.preventDefault();
            const redo = e.shiftKey || e.key.toLowerCase() === "y";
            const stack = redo ? future.current : past.current;
            if (stack.length) {
              (redo ? past.current : future.current).push(text);
              const value = stack.pop()!;
              setText(value);
              editText(data.id, value, false);
            } else (redo ? redoGraph : undoGraph)();
            return;
          }
          if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
            e.preventDefault();
            const canvas = input.current?.closest<HTMLElement>(".canvas");
            if (editText(data.id, text, true))
              setTimeout(() => canvas?.focus({ preventScroll: true }), 0);
            return;
          }
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            const canvas = input.current?.closest<HTMLElement>(".canvas");
            if (editText(data.id, text, true))
              setTimeout(() => canvas?.focus({ preventScroll: true }), 0);
          }
          if (e.key === "Escape") {
            e.preventDefault();
            stopEditing();
          }
        }}
        onBlur={() => editText(data.id, text, true)}
      />
      {options.length > 0 && (
        <NodeToolbar
          nodeId={data.id}
          isVisible
          position={
            screen.y > window.innerHeight - 280 ? Position.Top : Position.Bottom
          }
          align={screen.x > window.innerWidth - 280 ? "end" : "start"}
        >
          <div
            className="entry-suggestions nodrag nopan nowheel"
            role="listbox"
            id={`suggest-${data.id}`}
            aria-label={
              context?.kind === "topics"
                ? "Topics existants"
                : context?.kind === "subtopics"
                  ? "Sous-thèmes existants"
                  : "Portées existantes"
            }
          >
            <small>
              {context?.kind === "topics"
                ? "Topics"
                : context?.kind === "subtopics"
                  ? "Sous-thèmes"
                  : "Portées"}{" "}
              · Tab pour réutiliser
            </small>
            {options.map((item, i) => (
              <button
                type="button"
                role="option"
                aria-selected={i === active}
                id={`suggest-${data.id}-${i}`}
                key={item.value}
                title={item.value}
                onPointerDown={(e) => e.preventDefault()}
                onClick={() => choose(i)}
              >
                <span>{item.label}</span>
                {item.preferred && <small>ce topic</small>}
              </button>
            ))}
          </div>
        </NodeToolbar>
      )}
    </>
  );
}
function ConceptNode({ data, selected }: NodeProps<FlowNode>) {
  const {
      doc,
      readOnly,
      beginGesture,
      resize,
      editing,
      initialText,
      editText,
    } = useContext(Context),
    b = doc.layout.nodes[data.id],
    group = isJunction(data.kind);
  // React Flow can render one old node while its controlled store reconciles
  // an imported/restored document. Old objects must not read the new layout.
  if (!b) return null;
  return (
    <div
      className={`graph-node ${group ? "junction" : ""} ${data.kind === "source" ? "source-node" : ""} ${selected ? "selected" : ""}`}
      style={{ width: b.width, height: b.height }}
      title={
        data.kind === "priority"
          ? `Prioritaire : ${doc.nodes.find((n) => n.id === data.dominant)?.label || doc.nodes.find((n) => n.id === data.dominant)?.code || "à préciser"}`
          : undefined
      }
    >
      {!readOnly && !group && (
        <NodeResizer
          isVisible={selected}
          minWidth={100}
          minHeight={40}
          handleStyle={{ display: "none" }}
          onResizeStart={beginGesture}
          onResize={(_, p) => resize(data.id, p, false)}
          onResizeEnd={(_, p) => resize(data.id, p, true)}
        />
      )}
      {!readOnly &&
        data.kind !== "source" &&
        (Object.keys(positions) as Port[]).map((p) => (
          <Handle
            key={p}
            id={p}
            type="source"
            position={positions[p]}
            style={
              p.includes("-")
                ? {
                    left: p.endsWith("left") ? 0 : "100%",
                    transform: "translate(-50%, -50%)",
                    top: p.startsWith("top") ? 0 : "100%",
                    bottom: "auto",
                  }
                : undefined
            }
            title={`Tirer depuis ${portLabels[p].toLowerCase()} pour relier ou créer un bloc`}
            aria-label={`Connecter par ${p}`}
          />
        ))}
      {editing === data.id && !readOnly ? (
        <>
          <InlineText key={data.id} data={data} />
          <button
            className="inline-close nodrag nopan"
            aria-label="Terminer l’édition du bloc"
            onClick={() => {
              const text = initialText(data.id);
              editText(data.id, text ?? nodeText(data), true);
            }}
          >
            ×
          </button>
        </>
      ) : (
        <div className="node-content">
          {group ? (
            junctionSymbol(doc, data)
          ) : doc.editor?.node_text[data.id] !== undefined ? (
            <div className="draft-label">{doc.editor.node_text[data.id]}</div>
          ) : (
            <>
              <div>
                {data.kind === "source" ? "| " : ""}
                {data.label || data.code.replaceAll("_", " ") || (
                  <span className="blank-label">Écrire…</span>
                )}
              </div>
              {data.subtopics.length > 0 && (
                <small>
                  ({data.subtopics.join(", ").replaceAll("_", " ")})
                </small>
              )}
              {data.scopes.length > 0 && (
                <small>[{data.scopes.join(", ").replaceAll("_", " ")}]</small>
              )}
            </>
          )}
        </div>
      )}
      {b.locked && (
        <span className="lock-indicator" title="Position verrouillée">
          ⌑
        </span>
      )}
    </div>
  );
}
function NarrativeEdge({ id, selected }: EdgeProps) {
  const { doc, readOnly, beginGesture, moveLabel, selectEdge, moveRoutePoint } =
      useContext(Context),
    rf = useReactFlow(),
    e = doc.edges.find((e) => e.id === id);
  if (!e || !doc.layout.edges[id]) return null;
  const v = doc.layout.edges[id],
    p = routePoints(doc, e),
    mid = pointOnRoute(p, v.route, v.label_t),
    label = edgeLabel(e);
  function dragLabel(event: React.PointerEvent) {
    if (readOnly) return;
    event.stopPropagation();
    event.preventDefault();
    selectEdge(id);
    beginGesture();
    const x = event.clientX,
      y = event.clientY,
      dx = v.label_dx,
      dy = v.label_dy,
      zoom = rf.getZoom();
    const move = (ev: PointerEvent) =>
      moveLabel(
        id,
        dx + (ev.clientX - x) / zoom,
        dy + (ev.clientY - y) / zoom,
        false,
      );
    const end = (ev: PointerEvent) => {
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", end);
      moveLabel(
        id,
        dx + (ev.clientX - x) / zoom,
        dy + (ev.clientY - y) / zoom,
        true,
      );
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", end, { once: true });
  }
  return (
    <g>
      <path
        d={svgRoute(p, v.route)}
        fill="none"
        stroke="#111"
        strokeWidth={selected ? 1.8 : 1.2}
        strokeDasharray={
          (v.stroke || (e.kind === "priority" ? "dashed" : "solid")) ===
          "dashed"
            ? "6 4"
            : v.stroke === "dotted"
              ? "1 4"
              : undefined
        }
        markerEnd={e.kind === "causal" ? "url(#narrative-arrow)" : undefined}
      />
      <path
        d={svgRoute(p, v.route)}
        fill="none"
        stroke="transparent"
        strokeWidth={22 / rf.getZoom()}
        pointerEvents="stroke"
        onClick={() => selectEdge(id)}
        style={{ cursor: "pointer" }}
        className="react-flow__edge-interaction"
      />
      {label && (
        <g
          data-group-edge={isJunction(e.kind) ? id : undefined}
          transform={`translate(${mid.x + v.label_dx},${mid.y + v.label_dy})`}
          onPointerDown={dragLabel}
          onClick={() => selectEdge(id)}
          style={{
            cursor: readOnly ? "default" : "move",
            pointerEvents: "all",
          }}
        >
          <rect x={-10} y={-11} width={20} height={22} fill="white" />
          <text
            textAnchor="middle"
            dominantBaseline="central"
            fill="black"
            fontSize={15}
          >
            {label}
          </text>
        </g>
      )}
      {selected &&
        !readOnly &&
        (v.route === "straight"
          ? [pointOnRoute(p, v.route, label ? 0.65 : 0.5)]
          : p.slice(1, -1)
        ).map((point, index) => (
          <circle
            key={index}
            className="route-handle"
            cx={point.x}
            cy={point.y}
            r={5 / rf.getZoom()}
            fill="white"
            stroke="black"
            pointerEvents="all"
            aria-label={`Déplacer le tracé ${index + 1}`}
            onPointerDown={(event) => {
              event.stopPropagation();
              event.preventDefault();
              beginGesture();
              const pointIndex = v.route === "straight" ? -1 : index;
              const move = (ev: PointerEvent) =>
                moveRoutePoint(
                  id,
                  pointIndex,
                  rf.screenToFlowPosition({ x: ev.clientX, y: ev.clientY }),
                  false,
                );
              const end = (ev: PointerEvent) => {
                window.removeEventListener("pointermove", move);
                window.removeEventListener("pointerup", end);
                moveRoutePoint(
                  id,
                  pointIndex,
                  rf.screenToFlowPosition({ x: ev.clientX, y: ev.clientY }),
                  true,
                );
              };
              window.addEventListener("pointermove", move);
              window.addEventListener("pointerup", end, { once: true });
            }}
          >
            <title>
              Tirer pour déplacer le tracé ; les extrémités restent attachées
            </title>
          </circle>
        ))}
    </g>
  );
}
export const nodeTypes = { concept: ConceptNode },
  edgeTypes = { narrative: NarrativeEdge };
