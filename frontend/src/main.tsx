import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { Streamlit, RenderData } from "streamlit-component-lib";
import {
  ReactFlow,
  ReactFlowProvider,
  ConnectionMode,
  SelectionMode,
  Controls,
  Background,
  ViewportPortal,
  useReactFlow,
  type NodeChange,
  type Connection,
  type OnConnectEnd,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import "./style.css";
import {
  clone,
  uid,
  newNode,
  defaultBox,
  defaultEdgeView,
  type GraphDoc,
  type EditorArgs,
  type GraphEdge,
  type Box,
  type Port,
  type Kind,
  type JunctionKind,
} from "./types";
import { snap, bounds, distribute, type Guide } from "./alignment";
import {
  attachmentPosition,
  anchor,
  routePoints,
  pointOnRoute,
} from "./geometry";
import { Context } from "./editorContext";
import { nodeTypes, edgeTypes, type FlowNode } from "./CanvasElements";
import { NodeInspector, EdgeInspector } from "./Inspectors";
import { symbols, parseEntry, opposite } from "./entry";
import { textHeight } from "./textSizing";
import { same, removeObjects, timelineFor, readView } from "./editorState";
import { useWorkspaceView } from "./useWorkspaceView";
import { FloatingToolbar } from "./FloatingToolbar";
import { reverseRelation, relations, edgeLabel } from "./relations";
import {
  attachSource,
  convertToSource,
  dagLabel,
  sourceTarget,
} from "./sources";
import { publicationReady, type ExportKind } from "./publication";
import { normalizePaths, invalidateChangedEvidence } from "./tracking";
import { EnrichmentPanel } from "./EnrichmentPanel";
import { DagPicker } from "./DagPicker";
import { EvidenceBox } from "./EvidenceBox";
import { followMovedNodes } from "./movement";
import { materializeGroup, facingPort } from "./groups";
let recoveryDocument: GraphDoc | undefined;
function download(doc: GraphDoc) {
  const blob = new Blob([JSON.stringify(doc, null, 2)], {
      type: "application/json",
    }),
    url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "narrative.graph.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function downloadText(text: string, name: string) {
  const url = URL.createObjectURL(
    new Blob([text], { type: "text/plain;charset=utf-8" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function downloadBase64(data: string, name: string) {
  const bytes = Uint8Array.from(atob(data), (c) => c.charCodeAt(0));
  const url = URL.createObjectURL(
    new Blob([bytes], { type: "application/pdf" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function Editor({
  args,
  onReviewChange,
  onCommitReady,
}: {
  args: EditorArgs;
  onReviewChange?: (doc: GraphDoc, valid: boolean) => void;
  onCommitReady?: (fn: () => GraphDoc | null) => void;
}) {
  const review = !!onReviewChange;
  const [doc, setDoc] = useState<GraphDoc>(() =>
      normalizePaths(clone(args.document), args.response_digest || ""),
    ),
    current = useRef(doc),
    rf = useReactFlow<FlowNode>();
  const [selection, setSelection] = useState<string[]>([]),
    [selectedEdge, setSelectedEdge] = useState<string | null>(null),
    [activePath, setActivePath] = useState(args.document.paths[0].id);
  const [inspectorDirty, setInspectorDirty] = useState(false);
  const [pointerHeld, setPointerHeld] = useState(false),
    [moving, setMoving] = useState(false),
    [boxSelecting, setBoxSelecting] = useState(false);
  const pasteCount = useRef(0);
  const [guides, setGuides] = useState<Guide[]>([]),
    [message, setMessage] = useState(""),
    [saving, setSaving] = useState(false),
    [grid, setGrid] = useState(true),
    [inspector, setInspector] = useState(false);
  const [relationKind, setRelationKind] = useState<GraphEdge["kind"]>("causal");
  const [importText, setImportText] = useState(
      args.document.provenance.original_text,
    ),
    [jump, setJump] = useState(String(args.row + 1));
  const [editing, setEditing] = useState<string | null>(null),
    [options, setOptions] = useState(false),
    [enrichment, setEnrichment] = useState(false),
    [dagPicker, setDagPicker] = useState(false),
    [resumeError, setResumeError] = useState(""),
    [latex, setLatex] = useState(false),
    [dictionary, setDictionary] = useState(false),
    [dictionaryQuery, setDictionaryQuery] = useState(""),
    [dictionaryKind, setDictionaryKind] = useState<
      "topics" | "subtopics" | "scopes"
    >("topics"),
    [showProposal, setShowProposal] = useState(false),
    [reviewValid, setReviewValid] = useState(true);
  const pendingText = useRef<{ id: string; text: string } | null>(null),
    inlineRemembered = useRef(false),
    autoCode = useRef(new Set<string>()),
    textTimer = useRef<ReturnType<typeof setTimeout>>(),
    canvasRef = useRef<HTMLDivElement>(null),
    proposalDraft = useRef<GraphDoc | null>(null),
    proposalCommit = useRef<(() => GraphDoc | null) | null>(null),
    inspectorFlush = useRef<(() => boolean) | null>(null),
    pendingExport = useRef<ExportKind | null>(null),
    measuredNodes = useRef(
      new Map<string, { width: number; height: number }>(),
    ),
    restoringHistory = useRef(false),
    deferredUndo = useRef(0),
    timeline = useRef(timelineFor(args.document_key)),
    proposalDialog = useRef<HTMLElement>(null),
    conflictRecovery = useRef<GraphDoc | null>(null),
    seenProposal = useRef<string | null>(null),
    connectionDone = useRef(false),
    prioritySource = useRef(false);
  const history = useRef<GraphDoc[]>(timeline.current.past),
    future = useRef<GraphDoc[]>(timeline.current.future),
    clipboard = useRef<GraphDoc | null>(null),
    revision = useRef(args.revision),
    inFlight = useRef<string | null>(null),
    flightAction = useRef("save"),
    queued = useRef<{
      doc: GraphDoc;
      action: string;
      extra: Record<string, unknown>;
    } | null>(null);
  const replacement = useRef(args.replace_token),
    alt = useRef(false),
    gesture = useRef(false),
    snapPrevious = useRef<{ dx: number; dy: number }>(),
    container = useRef<HTMLDivElement>(null);
  const disabled = !!args.read_only;
  const view = useWorkspaceView(
    args.document_key,
    canvasRef,
    doc.nodes.length,
    review,
  );
  function saveTimeline() {
    timeline.current.past = history.current;
    timeline.current.future = future.current;
  }
  useEffect(() => () => saveTimeline(), []);

  function local(next: GraphDoc, semanticEdit = false) {
    normalizePaths(next, args.response_digest);
    for (const node of next.nodes)
      if (
        node.kind === "priority" &&
        node.dominant &&
        !next.edges.some(
          (e) =>
            e.kind === "membership" &&
            e.target === node.id &&
            e.source === node.dominant,
        )
      )
        node.dominant = null;
    if (semanticEdit && invalidateChangedEvidence(current.current, next))
      next.status = "draft";
    setActivePath((id) =>
      next.paths.some((p) => p.id === id) ? id : next.paths[0].id,
    );
    setSelection((ids) => ids.filter((id) => !!next.layout.nodes[id]));
    setSelectedEdge((id) => (id && next.layout.edges[id] ? id : null));
    current.current = next;
    if (!review) recoveryDocument = next;
    setDoc(next);
    if (!review && !disabled)
      try {
        sessionStorage.setItem(
          "narrative-draft:" + args.document_key,
          JSON.stringify({
            document: next,
            base_revision: revision.current,
            pending: pendingText.current,
            auto_codes: [...autoCode.current],
          }),
        );
      } catch {
        /* Saving on the server remains authoritative. */
      }
  }
  function remember() {
    history.current.push(clone(current.current));
    future.current = [];
    saveTimeline();
  }
  function transmit(
    next: GraphDoc,
    action = "save",
    extra: Record<string, unknown> = {},
  ) {
    if (disabled) return;
    normalizePaths(next, args.response_digest);
    if (action !== "save") {
      const snapshot = commitCurrent();
      if (!snapshot) return;
      next = snapshot;
    }
    if (review) {
      onReviewChange?.(clone(next), true);
      return;
    }
    if (inFlight.current) {
      if (
        queued.current &&
        queued.current.action !== "save" &&
        action === "save"
      )
        queued.current.doc = clone(next);
      else queued.current = { doc: clone(next), action, extra };
      setSaving(true);
      return;
    }
    const request = uid("r");
    inFlight.current = request;
    flightAction.current = action;
    setSaving(true);
    setMessage("");
    Streamlit.setComponentValue({
      document_key: args.document_key,
      client_session: args.client_session,
      request_id: request,
      base_revision: revision.current,
      document: next,
      action,
      ...extra,
    });
  }
  function mutate(fn: (d: GraphDoc) => void, persist = true) {
    if (disabled) return;
    const next = clone(current.current);
    fn(next);
    for (const n of next.nodes)
      if (n.kind === "source" && n.attachment)
        attachSource(next, n, n.attachment);
    if (same(next, current.current)) return;
    if (
      next.nodes.length > 150 ||
      next.edges.length > 500 ||
      next.paths.length > 150
    ) {
      setMessage(
        "Ce document atteint la limite de 150 objets, 500 liens ou 150 DAGs. Exportez-le puis ouvrez un autre graphe.",
      );
      return;
    }
    if (
      current.current.status === "none" &&
      next.status === "none" &&
      JSON.stringify([next.nodes, next.edges, next.paths]) !==
        JSON.stringify([
          current.current.nodes,
          current.current.edges,
          current.current.paths,
        ])
    )
      next.status = "coded";
    followMovedNodes(current.current, next);
    remember();
    local(next, true);
    if (persist) transmit(next);
  }
  function beginGesture() {
    if (disabled || gesture.current) return;
    remember();
    gesture.current = true;
    setMoving(true);
  }
  function finishGesture() {
    setMoving(false);
    if (!gesture.current) return;
    gesture.current = false;
    if (same(history.current.at(-1), current.current)) history.current.pop();
    saveTimeline();
    setGuides([]);
    snapPrevious.current = undefined;
    transmit(current.current);
  }
  useEffect(() => {
    const release = () => setPointerHeld(false);
    const cancel = () => {
      release();
      setBoxSelecting(false);
      if (gesture.current) finishGesture();
    };
    window.addEventListener("pointerup", release);
    window.addEventListener("pointercancel", cancel);
    window.addEventListener("blur", cancel);
    try {
      if (window.parent !== window)
        window.parent.addEventListener("pointerup", cancel);
    } catch {}
    return () => {
      window.removeEventListener("pointerup", release);
      window.removeEventListener("pointercancel", cancel);
      window.removeEventListener("blur", cancel);
      try {
        if (window.parent !== window)
          window.parent.removeEventListener("pointerup", cancel);
      } catch {}
    };
  }, []);
  useEffect(() => {
    if (review || disabled) return;
    try {
      const raw = sessionStorage.getItem(
        "narrative-draft:" + args.document_key,
      );
      if (raw) {
        const cached = JSON.parse(raw);
        if (
          cached.base_revision === args.revision ||
          same(cached.document, args.document)
        ) {
          if (
            cached.document?.schema_version === 1 &&
            cached.document.paths?.length
          ) {
            pendingText.current = cached.pending;
            local(cached.document);
            if (cached.pending) {
              setEditing(cached.pending.id);
              if (cached.auto_codes?.includes(cached.pending.id))
                autoCode.current.add(cached.pending.id);
            }
            if (!same(cached.document, args.document))
              transmit(cached.document);
          }
        } else {
          conflictRecovery.current = cached.document;
          setMessage(
            "Un brouillon de cet onglet appartient à une autre révision. Exportez-le depuis les options avant de poursuivre.",
          );
        }
      }
    } catch {
      /* An unavailable or damaged browser cache never blocks the app. */
    }
    return () => {
      if (textTimer.current) clearTimeout(textTimer.current);
    };
  }, []);
  useEffect(() => {
    const p = args.ai_proposal;
    if (!review && p?.status === "pending" && p.id !== seenProposal.current) {
      seenProposal.current = p.id;
      proposalDraft.current = clone(p.document);
      setShowProposal(true);
    }
    if (!p || p.status !== "pending") setShowProposal(false);
    if (
      !review &&
      args.ai_decision &&
      args.ai_decision.id === seenProposal.current
    ) {
      setShowProposal(false);
      proposalCommit.current = null;
    }
    if (args.replace_token !== replacement.current) {
      replacement.current = args.replace_token;
      setDagPicker(false);
      setResumeError("");
      pendingText.current = null;
      setEditing(null);
      if (!same(current.current, args.document) && !restoringHistory.current)
        remember();
      restoringHistory.current = false;
      local(clone(args.document));

      setSelection(args.selection_after_replace || []);
      setSelectedEdge(null);
      setActivePath(args.document.paths[0].id);
      setImportText(args.document.provenance.original_text);
    }
    if (args.ack && args.ack === inFlight.current) {
      inFlight.current = null;
      revision.current = args.revision;
      setSaving(false);
      if (args.error) {
        setMessage(args.error);
        queued.current = null;
        pendingExport.current = null;
      } else if (deferredUndo.current) {
        const count = deferredUndo.current;
        deferredUndo.current = 0;
        for (let i = 0; i < count; i++) undo();
      } else if (queued.current) {
        const pending = queued.current;
        queued.current = null;
        transmit(pending.doc, pending.action, pending.extra);
      } else if (!pendingText.current) {
        try {
          sessionStorage.removeItem("narrative-draft:" + args.document_key);
        } catch {
          /* Optional recovery cache. */
        }
      }
    }
  }, [args]);
  useEffect(() => {
    const observer = new ResizeObserver(
      () =>
        !review &&
        Streamlit.setFrameHeight((container.current?.offsetHeight || 740) + 4),
    );
    if (container.current) observer.observe(container.current);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    const warn = (e: BeforeUnloadEvent) => {
      if (
        inFlight.current ||
        queued.current ||
        inspectorDirty ||
        pendingText.current
      ) {
        e.preventDefault();
        e.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [inspectorDirty]);
  function undo() {
    if (
      inFlight.current &&
      [
        "import_json",
        "import_sequence",
        "clone_previous",
        "clone_selected",
        "new_graph",
        "clone_coder",
        "restore_revision",
        "validate",
        "ai_accept",
        "paste_selection",
        "duplicate_selection",
      ].includes(flightAction.current)
    ) {
      deferredUndo.current++;
      return;
    }

    pendingText.current = null;
    setEditing(null);
    if (textTimer.current) clearTimeout(textTimer.current);
    if (disabled) return;
    if (!history.current.length && !review) {
      const cursor = timeline.current.cursor ?? args.revision;
      const previous = args.history?.find((h) => h.revision < cursor);
      if (previous) {
        future.current.push(clone(current.current));
        timeline.current.cursor = previous.revision;
        saveTimeline();
        restoringHistory.current = true;
        transmit(current.current, "restore_revision", {
          revision: previous.revision,
        });
      }
      return;
    }
    if (!history.current.length) return;
    future.current.push(clone(current.current));
    const previous = history.current.pop()!;
    saveTimeline();
    local(previous);
    transmit(previous);
  }
  function redo() {
    pendingText.current = null;
    setEditing(null);
    if (textTimer.current) clearTimeout(textTimer.current);
    if (!future.current.length || disabled) return;
    history.current.push(clone(current.current));
    const next = future.current.pop()!;
    saveTimeline();
    local(next);
    transmit(next);
  }
  function removeSelected() {
    if (!selection.length && !selectedEdge) return;
    const next = removeObjects(current.current, selection, selectedEdge);
    remember();
    local(next, true);
    transmit(next);
    setSelection([]);
    setSelectedEdge(null);
  }
  function add(
    kind: Kind = "concept",
    code = "",
    point?: { x: number; y: number },
  ) {
    let id = "";
    mutate((d) => {
      const n = newNode(code, kind);
      id = n.id;
      d.nodes.push(n);
      const p =
        point ||
        rf.screenToFlowPosition({
          x:
            (canvasRef.current?.getBoundingClientRect().left || 0) +
            (canvasRef.current?.clientWidth || 600) / 2 -
            84,
          y:
            (canvasRef.current?.getBoundingClientRect().top || 0) +
            (canvasRef.current?.clientHeight || 500) / 2 -
            32,
        });
      d.layout.nodes[id] = defaultBox(
        p.x,
        p.y,
        ["coexistence", "addition", "definition", "priority"].includes(kind)
          ? 28
          : 168,
        ["coexistence", "addition", "definition", "priority"].includes(kind)
          ? 28
          : 64,
      );
      d.paths.find((p) => p.id === activePath)!.node_ids.push(id);
      d.status = "coded";
    });
    setSelection([id]);
    setSelectedEdge(null);
    setInspector(false);
    if (kind === "concept" || kind === "source") {
      autoCode.current.add(id);
      pendingText.current = { id, text: code.replaceAll("_", " ") };
      setEditing(id);
      inlineRemembered.current = false;
    }
  }
  function connect(
    source: string,
    target: string,
    kind = relationKind,
    sourcePort: Port = "right",
    targetPort: Port = "left",
  ) {
    const d = current.current,
      a = d.nodes.find((n) => n.id === source),
      b = d.nodes.find((n) => n.id === target);
    if (!a || !b || source === target) {
      setMessage("Choisissez deux objets différents.");
      return;
    }
    if (a.kind === "source" || b.kind === "source") {
      setMessage(
        "Attachez une source avec le champ « Concerne » de son inspecteur.",
      );
      return;
    }
    if (
      ["coexistence", "addition", "definition", "priority"].includes(b.kind) &&
      ["coexistence", "addition", "link"].includes(kind)
    )
      kind = "membership";
    if (
      kind === "membership" &&
      ["coexistence", "addition", "definition", "priority"].includes(a.kind) &&
      !["coexistence", "addition", "definition", "priority"].includes(b.kind)
    ) {
      connect(target, source, "membership", targetPort, sourcePort);
      return;
    }
    if (
      kind === "membership" &&
      ["definition", "priority"].includes(b.kind) &&
      d.edges.filter((e) => e.kind === "membership" && e.target === target)
        .length >= 2
    ) {
      setMessage(
        "Cette relation a déjà deux sujets. Utilisez → pour viser la relation entière, ou modifiez un de ses liens.",
      );
      return;
    }
    if (
      kind === "membership" &&
      !["coexistence", "addition", "definition", "priority"].includes(b.kind)
    ) {
      setMessage("Une composition doit aboutir à &, +, =, > ou <.");
      return;
    }
    if (
      d.edges.some(
        (e) => e.source === source && e.target === target && e.kind === kind,
      )
    ) {
      setMessage("Cette relation existe déjà.");
      return;
    }
    mutate((next) => {
      const e: GraphEdge = {
        id: uid("e"),
        source,
        target,
        kind,
        dominant:
          kind === "priority"
            ? prioritySource.current
              ? source
              : target
            : null,
      };
      next.edges.push(e);
      next.layout.edges[e.id] = {
        ...defaultEdgeView(),
        source_port: sourcePort,
        target_port: targetPort,
      };
      const p = next.paths.find((p) => p.id === activePath)!;
      p.edge_ids.push(e.id);
      for (const n of [source, target])
        if (!p.node_ids.includes(n)) p.node_ids.push(n);
    });
  }
  function group(kind: JunctionKind, dominant?: string) {
    const ids = selection.filter(
      (id) => current.current.nodes.find((n) => n.id === id)?.kind !== "source",
    );
    if (["definition", "priority"].includes(kind) && ids.length !== 2) {
      setMessage("Sélectionnez exactement deux sujets pour cette relation.");
      return;
    }
    if (ids.length < 2) {
      setMessage(
        "Sélectionnez au moins deux concepts (Maj + clic), puis choisissez & ou +.",
      );
      return;
    }
    let id = "";
    mutate((d) => {
      const b = bounds(ids.map((id) => d.layout.nodes[id])),
        n = newNode("", kind);
      id = n.id;
      if (kind === "priority") n.dominant = dominant || null;
      d.nodes.push(n);
      const centers = ids.map((id) => {
        const v = d.layout.nodes[id];
        return { x: v.x + v.width / 2, y: v.y + v.height / 2 };
      });
      const center = {
        x: centers.reduce((v, p) => v + p.x, 0) / centers.length,
        y: centers.reduce((v, p) => v + p.y, 0) / centers.length,
      };
      const free =
        ids.length === 2 &&
        !ids.some((id) => {
          const v = d.layout.nodes[id];
          return (
            center.x > v.x - 20 &&
            center.x < v.x + v.width + 20 &&
            center.y > v.y - 20 &&
            center.y < v.y + v.height + 20
          );
        });
      d.layout.nodes[id] = defaultBox(
        free ? center.x - 14 : b.x + b.width + 75,
        free ? center.y - 14 : b.y + b.height / 2 - 14,
        28,
        28,
      );
      const p = d.paths.find((p) => p.id === activePath)!;
      p.node_ids = [...new Set([...p.node_ids, ...ids, id])];
      for (const member of ids) {
        const e: GraphEdge = {
          id: uid("e"),
          source: member,
          target: id,
          kind: "membership",
          dominant: null,
        };
        d.edges.push(e);
        const v = d.layout.nodes[member],
          g = d.layout.nodes[id],
          a = { x: v.x + v.width / 2, y: v.y + v.height / 2 },
          c = { x: g.x + 14, y: g.y + 14 };
        d.layout.edges[e.id] = {
          ...defaultEdgeView(),
          source_port: facingPort(a, c),
          target_port: facingPort(c, a),
        };
        p.edge_ids.push(e.id);
      }
    });
    setSelection([id]);
    setSelectedEdge(null);
  }
  function copySelection() {
    if (!selection.length) return;
    if (!review) {
      pasteCount.current = 0;
      transmit(current.current, "copy_selection", { node_ids: selection });
      return;
    }
    const ids = new Set(selection);
    if (!ids.size) return;
    const d = clone(current.current);
    d.nodes = d.nodes.filter((n) => ids.has(n.id));
    d.edges = d.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
    clipboard.current = d;
    setMessage("Sélection copiée dans cet éditeur.");
  }
  function duplicateSelection() {
    if (!selection.length) return;
    if (review) {
      copySelection();
      paste();
    } else
      transmit(current.current, "duplicate_selection", { node_ids: selection });
  }
  function paste() {
    if (!review) {
      pasteCount.current++;
      const canvas = canvasRef.current?.getBoundingClientRect();
      if (!canvas) return;
      transmit(current.current, "paste_selection", {
        at: rf.screenToFlowPosition({
          x: canvas.left + canvas.width / 2 + 25 * pasteCount.current,
          y: canvas.top + canvas.height / 2 + 25 * pasteCount.current,
        }),
      });
      return;
    }
    const source = clipboard.current;
    if (!source?.nodes.length) return;
    const map = new Map(source.nodes.map((n) => [n.id, uid()]));
    mutate((d) => {
      const p = d.paths.find((p) => p.id === activePath)!;
      for (const original of source.nodes) {
        const n = clone(original);
        n.id = map.get(original.id)!;
        if (n.dominant) n.dominant = map.get(n.dominant) || null;
        if (n.attachment)
          n.attachment =
            n.attachment.kind === "node" && map.has(n.attachment.id)
              ? { kind: "node", id: map.get(n.attachment.id)! }
              : null;
        d.nodes.push(n);
        p.node_ids.push(n.id);
        const b = source.layout.nodes[original.id];
        d.layout.nodes[n.id] = {
          ...b,
          x: b.x + 35,
          y: b.y + 35,
          locked: false,
        };
      }
      for (const original of source.edges) {
        const e = {
          ...original,
          id: uid("e"),
          source: map.get(original.source)!,
          target: map.get(original.target)!,
          dominant: original.dominant ? map.get(original.dominant)! : null,
        };
        d.edges.push(e);
        p.edge_ids.push(e.id);
        d.layout.edges[e.id] = {
          ...clone(source.layout.edges[original.id]),
          points: source.layout.edges[original.id].points.map((v) => ({
            x: v.x + 35,
            y: v.y + 35,
          })),
        };
      }
    });
    setSelection([...map.values()]);
  }
  function align(mode: string) {
    if (selection.length < 2) return;
    mutate((d) => {
      const movable = selection.filter((id) => !d.layout.nodes[id].locked);
      if (mode === "distribute-x" || mode === "distribute-y") {
        d.layout.nodes = distribute(
          d.layout.nodes,
          movable,
          mode.endsWith("x") ? "x" : "y",
        );
        return;
      }
      const b = bounds(selection.map((id) => d.layout.nodes[id]));
      for (const id of movable) {
        const n = d.layout.nodes[id];
        if (mode === "left") n.x = b.x;
        if (mode === "center-x") n.x = b.x + b.width / 2 - n.width / 2;
        if (mode === "right") n.x = b.x + b.width - n.width;
        if (mode === "top") n.y = b.y;
        if (mode === "center-y") n.y = b.y + b.height / 2 - n.height / 2;
        if (mode === "bottom") n.y = b.y + b.height - n.height;
      }
    });
  }
  function autoLayout() {
    const d = current.current,
      indeg = new Map(d.nodes.map((n) => [n.id, 0])),
      adj = new Map(d.nodes.map((n) => [n.id, [] as string[]])),
      rank = new Map(d.nodes.map((n) => [n.id, 0]));
    for (const e of d.edges)
      if (e.kind !== "priority") {
        adj.get(e.source)!.push(e.target);
        indeg.set(e.target, indeg.get(e.target)! + 1);
      }
    const q = d.nodes.filter((n) => indeg.get(n.id) === 0).map((n) => n.id);
    let seen = 0;
    while (q.length) {
      const id = q.shift()!;
      seen++;
      for (const t of adj.get(id)!) {
        rank.set(t, Math.max(rank.get(t)!, rank.get(id)! + 1));
        indeg.set(t, indeg.get(t)! - 1);
        if (indeg.get(t) === 0) q.push(t);
      }
    }
    if (seen !== d.nodes.length) {
      setMessage(
        "La disposition automatique nécessite une structure sans boucle. Vos positions sont conservées.",
      );
      return;
    }
    mutate((next) => {
      const rows = new Map<number, number>();
      for (const n of next.nodes) {
        const r = rank.get(n.id)!,
          y = rows.get(r) || 0;
        rows.set(r, y + 1);
        if (!next.layout.nodes[n.id].locked) {
          next.layout.nodes[n.id].x = r * 235;
          next.layout.nodes[n.id].y = y * 115;
        }
      }
      for (const e of Object.values(next.layout.edges)) e.points = [];
    });
  }
  function changeNodes(changes: NodeChange<FlowNode>[]) {
    // Keep React Flow's measured dimensions across controlled renders. Dropping
    // them clears its handle bounds and can hide nodes or blur an active field.
    // These browser measurements are transient, separate from figure geometry.
    for (const c of changes)
      if (c.type === "dimensions" && c.dimensions)
        measuredNodes.current.set(c.id, c.dimensions);
    if (disabled) return;
    let next = clone(current.current),
      changed = false;
    const moved: string[] = [];
    for (const c of changes) {
      if (c.type === "select" && next.layout.nodes[c.id]) {
        setSelection((ids) =>
          c.selected
            ? [...new Set([...ids, c.id])]
            : ids.filter((id) => id !== c.id),
        );
        if (c.selected) setSelectedEdge(null);
      }
      if (
        c.type === "position" &&
        c.position &&
        next.layout.nodes[c.id] &&
        !next.layout.nodes[c.id].locked
      ) {
        Object.assign(next.layout.nodes[c.id], c.position);
        moved.push(c.id);
        changed = true;
      }
    }
    if (moved.length && gesture.current) {
      const ids = (selection.includes(moved[0]) ? selection : moved).filter(
          (id) => next.layout.nodes[id] && !next.layout.nodes[id].locked,
        ),
        b = bounds(ids.map((id) => next.layout.nodes[id])),
        others = Object.entries(next.layout.nodes)
          .filter(([id]) => !ids.includes(id))
          .map(([, b]) => b),
        s = snap(b, others, rf.getZoom(), alt.current, snapPrevious.current);
      for (const id of ids)
        if (!next.layout.nodes[id].locked) {
          next.layout.nodes[id].x += s.dx;
          next.layout.nodes[id].y += s.dy;
        }
      snapPrevious.current = { dx: s.dx, dy: s.dy };
      setGuides(s.guides);
    }
    if (changed) {
      followMovedNodes(current.current, next);
      local(next);
      if (!gesture.current) transmit(next);
    }
  }
  const resize = (id: string, b: Partial<Box>, finish: boolean) => {
    if (!current.current.layout.nodes[id]) return;
    const next = clone(current.current);
    Object.assign(next.layout.nodes[id], {
      x: b.x,
      y: b.y,
      width: b.width,
      height: b.height,
    });
    followMovedNodes(current.current, next);
    local(next);
    if (finish) finishGesture();
  };
  const moveLabel = (id: string, dx: number, dy: number, finish: boolean) => {
    if (!current.current.layout.edges[id]) return;
    const next = clone(current.current);
    Object.assign(next.layout.edges[id], { label_dx: dx, label_dy: dy });
    local(next);
    if (finish) finishGesture();
  };
  useEffect(() => {
    const down = (e: KeyboardEvent) => {
      alt.current = e.altKey;
      const target = e.target as HTMLElement;
      if (
        !review &&
        document.querySelector(".proposal-backdrop, .dag-picker-backdrop")
      )
        return;
      if (review && !target.closest(".proposal-dialog")) return;
      if (
        target.closest(".editor") &&
        target.closest(".editor") !== container.current
      )
        return;
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === "s") {
        e.preventDefault();
        (target.closest("form") as HTMLFormElement | null)?.requestSubmit();
        transmit(current.current);
        return;
      }
      const nativeText = target.closest<HTMLElement>("[data-native-text]");
      if (nativeText) {
        if (mod && e.key.toLowerCase() === "a") {
          e.preventDefault();
          const range = document.createRange();
          range.selectNodeContents(nativeText);
          const selectedText = window.getSelection();
          selectedText?.removeAllRanges();
          selectedText?.addRange(range);
          return;
        }
        if (!(mod && e.key.toLowerCase() === "z") && e.key !== "Escape") return;
      }
      const selectedText = window.getSelection();
      if (
        mod &&
        ["c", "x"].includes(e.key.toLowerCase()) &&
        selectedText &&
        !selectedText.isCollapsed
      )
        return;
      if (target.closest("input,textarea,select,[contenteditable]")) return;
      if (mod && e.key.toLowerCase() === "z") {
        e.preventDefault();
        e.shiftKey ? redo() : undo();
      } else if (mod && e.key.toLowerCase() === "s") {
        e.preventDefault();
        transmit(current.current);
      } else if (mod && e.key.toLowerCase() === "c") {
        e.preventDefault();
        copySelection();
      } else if (mod && e.key.toLowerCase() === "v") {
        e.preventDefault();
        paste();
      } else if (mod && e.key.toLowerCase() === "a") {
        e.preventDefault();
        setSelection(current.current.nodes.map((n) => n.id));
        setSelectedEdge(null);
      } else if (mod && e.key.toLowerCase() === "x") {
        e.preventDefault();
        copySelection();
        removeSelected();
      } else if (mod && e.key.toLowerCase() === "d") {
        e.preventDefault();
        duplicateSelection();
      } else if (
        ["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown"].includes(e.key) &&
        selection.length
      ) {
        e.preventDefault();
        const step = e.shiftKey ? 20 : 2;
        mutate((d) => {
          for (const id of selection) {
            const b = d.layout.nodes[id];
            if (!b || b.locked) continue;
            if (e.key === "ArrowLeft") b.x -= step;
            if (e.key === "ArrowRight") b.x += step;
            if (e.key === "ArrowUp") b.y -= step;
            if (e.key === "ArrowDown") b.y += step;
          }
        });
      } else if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        removeSelected();
      } else if (e.key === "Escape") {
        setSelection([]);
        setSelectedEdge(null);
        setMessage("");
      }
    };
    const up = (e: KeyboardEvent) => {
      alt.current = e.altKey;
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [selection, selectedEdge, args, rf.viewportInitialized]);
  const flowNodes: FlowNode[] = doc.nodes.map((n) => ({
    id: n.id,
    type: "concept",
    data: n,
    position: { x: doc.layout.nodes[n.id].x, y: doc.layout.nodes[n.id].y },
    width: doc.layout.nodes[n.id].width,
    height: doc.layout.nodes[n.id].height,
    measured: measuredNodes.current.get(n.id),
    style: {
      width: doc.layout.nodes[n.id].width,
      height: doc.layout.nodes[n.id].height,
    },
    selected: selection.includes(n.id),
    draggable: !disabled && !doc.layout.nodes[n.id].locked,
  }));
  const flowEdges = doc.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: doc.layout.edges[e.id].source_port,
    targetHandle: doc.layout.edges[e.id].target_port,
    type: "narrative",
    selected: e.id === selectedEdge,
    reconnectable: !disabled,
  }));
  const selected =
    selection.length === 1
      ? doc.nodes.find((n) => n.id === selection[0])
      : undefined;
  function applyText(
    id: string,
    text: string,
    finish: boolean,
    persist = true,
  ): boolean {
    const original = current.current.nodes.find((n) => n.id === id);
    if (!original) return true;
    pendingText.current = { id, text };
    if (finish && !text.trim()) {
      const next = removeObjects(current.current, [id]);
      if (!same(next, current.current)) {
        if (!inlineRemembered.current) remember();
        local(next, true);
        if (persist) transmit(next);
      }
      pendingText.current = null;
      setEditing(null);
      inlineRemembered.current = false;
      autoCode.current.delete(id);
      return true;
    }
    try {
      // A bare marker is an unfinished source, never a command that deletes
      // and recreates the selected node (which would leave a dangling target).
      if (text.trim() === "|") {
        if (finish) {
          if (textTimer.current) clearTimeout(textTimer.current);
          if (!inlineRemembered.current) remember();
          const next = removeObjects(current.current, [id]);
          pendingText.current = null;
          setEditing(null);
          inlineRemembered.current = false;
          autoCode.current.delete(id);
          local(next, true);
          if (persist) transmit(next);
          return true;
        }
        const next = clone(current.current);
        convertToSource(next, id, activePath);
        const n = next.nodes.find((n) => n.id === id)!;
        n.code = "";
        n.label = "";
        n.subtopics = [];
        n.scopes = [];
        if (next.editor) {
          delete next.editor.node_text[id];
          if (!Object.keys(next.editor.node_text).length) delete next.editor;
        }
        next.status = "draft";
        if (!inlineRemembered.current) {
          remember();
          inlineRemembered.current = true;
        }
        autoCode.current.add(id);
        local(next, true);
        if (persist) {
          if (textTimer.current) clearTimeout(textTimer.current);
          textTimer.current = setTimeout(() => transmit(current.current), 650);
        }
        return true;
      }
      const parsed = parseEntry(
        original.kind === "source" && !text.trim().startsWith("|")
          ? "| " + text
          : text,
      );
      if (
        parsed.type === "symbol" &&
        !["&", "+", "=", ">", "<"].includes(parsed.value)
      ) {
        if (!finish) return false;
        if (!original.code || autoCode.current.has(id)) {
          const next = removeObjects(current.current, [id]);
          if (!inlineRemembered.current) remember();
          pendingText.current = null;
          setEditing(null);
          inlineRemembered.current = false;
          autoCode.current.delete(id);
          local(next, true);
          if (parsed.value === "none") {
            next.status = "none";
            local(next, true);
            if (persist) transmit(next);
          } else {
            if (persist) transmit(next);
            applySymbol(parsed.value);
          }
          return true;
        }
        throw new Error(
          "Ce symbole se choisit sur la toile ou dans la barre des symboles. Ce champ modifie un bloc.",
        );
      }
      const next = clone(current.current),
        n = next.nodes.find((n) => n.id === id)!;
      if (next.editor) {
        delete next.editor.node_text[id];
        if (!Object.keys(next.editor.node_text).length) delete next.editor;
      }
      if (parsed.type === "node") {
        if (n.kind !== "source" && parsed.kind === "source") {
          convertToSource(next, id, activePath);
          autoCode.current.add(id);
        }
        if (
          ["coexistence", "addition", "definition", "priority"].includes(
            n.kind,
          ) &&
          parsed.kind === "concept"
        ) {
          next.edges.forEach((e) => {
            if (e.target === id && e.kind === "membership") e.kind = "causal";
          });
          Object.assign(next.layout.nodes[id], { width: 168, height: 64 });
        }
        n.kind = parsed.kind;
        if (parsed.kind !== "source") n.attachment = null;
        if (!n.code || autoCode.current.has(id)) n.code = parsed.code;
        n.label = parsed.label;
        n.subtopics = parsed.subtopics;
        n.scopes = parsed.scopes;
      } else if (parsed.type === "qualifier") {
        if (n.kind !== "concept")
          throw new Error(
            "Sélectionnez un topic pour lui ajouter des précisions.",
          );
        n.subtopics = [...new Set([...n.subtopics, ...parsed.subtopics])];
        n.scopes = [...new Set([...n.scopes, ...parsed.scopes])];
      } else {
        n.kind = (
          {
            "&": "coexistence",
            "+": "addition",
            "=": "definition",
            ">": "priority",
            "<": "priority",
          } as Record<string, JunctionKind>
        )[parsed.value];
        n.dominant = null;
        n.code = "";
        n.label = parsed.value;
        n.subtopics = [];
        n.scopes = [];
        n.attachment = null;
        next.layout.nodes[id].width = 28;
        next.layout.nodes[id].height = 28;
        // Incoming causal links still target the whole group, not its members.
      }
      if (n.kind === "concept" || n.kind === "source")
        next.layout.nodes[id].height = Math.max(
          next.layout.nodes[id].height,
          textHeight(n, next.layout.nodes[id].width),
        );
      // Display text never validates a draft; only an explicit validation does.
      if (!same(next, current.current) && !inlineRemembered.current) {
        remember();
        inlineRemembered.current = true;
      }
      if (finish) {
        if (textTimer.current) clearTimeout(textTimer.current);
        pendingText.current = null;
        setEditing(null);
        inlineRemembered.current = false;
        autoCode.current.delete(id);
      }
      local(next, true);
      if (review) onReviewChange?.(clone(next), true);
      if (persist) {
        if (textTimer.current) clearTimeout(textTimer.current);
        if (finish) transmit(next);
        else
          textTimer.current = setTimeout(() => transmit(current.current), 650);
      }
      return true;
    } catch (error) {
      // Retain incomplete syntax as a draft, separate from analysis codes.
      const next = clone(current.current);
      next.editor ??= { node_text: {} };
      next.editor.node_text[id] = text;
      next.status = "draft";
      const b = next.layout.nodes[id];
      b.height = Math.max(
        b.height,
        textHeight(
          { ...original, label: text, subtopics: [], scopes: [] },
          b.width,
        ),
      );
      if (!same(next, current.current) && !inlineRemembered.current) {
        remember();
        inlineRemembered.current = true;
      }
      if (finish) {
        pendingText.current = null;
        setEditing(null);
        inlineRemembered.current = false;
        autoCode.current.delete(id);
        setMessage(
          "Texte conservé comme brouillon : " + (error as Error).message,
        );
      }
      local(next, true);
      onReviewChange?.(clone(next), true);
      if (persist) {
        if (textTimer.current) clearTimeout(textTimer.current);
        if (finish) transmit(next);
        else
          textTimer.current = setTimeout(() => transmit(current.current), 650);
      }
      return true;
    }
  }
  useEffect(() => {
    onCommitReady?.(() => {
      if (inspectorFlush.current && !inspectorFlush.current()) return null;
      const pending = pendingText.current;
      if (pending && !applyText(pending.id, pending.text, true, false))
        return null;
      return clone(current.current);
    });
  });

  function editNode(id: string) {
    setEditing(id);
    setInspector(false);
    inlineRemembered.current = false;
  }
  function applySymbol(symbol: string, point?: { x: number; y: number }) {
    if (symbol === "membership") {
      setRelationKind("membership");
      if (selectedEdge)
        mutate((d) => {
          const e = d.edges.find((e) => e.id === selectedEdge)!;
          e.kind = "membership";
          e.dominant = null;
        });
      return;
    }
    if (
      ["&", "+", "=", ">", "<"].includes(symbol) &&
      selection.length >= 2 &&
      !selectedEdge
    ) {
      group(
        (
          {
            "&": "coexistence",
            "+": "addition",
            "=": "definition",
            ">": "priority",
            "<": "priority",
          } as Record<string, JunctionKind>
        )[symbol],
        symbol === ">"
          ? selection[0]
          : symbol === "<"
            ? selection[1]
            : undefined,
      );
    } else if (["→", "—", "=", "&", "+", "<", ">"].includes(symbol)) {
      const kind =
        symbol === "→"
          ? "causal"
          : symbol === "—"
            ? "link"
            : symbol === "="
              ? "definition"
              : symbol === "&"
                ? "coexistence"
                : symbol === "+"
                  ? "addition"
                  : "priority";
      prioritySource.current = symbol === ">";
      setRelationKind(kind);
      if (selectedEdge)
        mutate((d) => {
          const e = d.edges.find((e) => e.id === selectedEdge)!;
          const junction = [
            "coexistence",
            "addition",
            "definition",
            "priority",
          ].includes(d.nodes.find((n) => n.id === e.target)!.kind);
          e.kind =
            ["coexistence", "addition", "link"].includes(kind) && junction
              ? "membership"
              : kind;
          e.dominant =
            kind === "priority" ? (symbol === ">" ? e.source : e.target) : null;
        });
      else if (selection.length === 2)
        connect(selection[0], selection[1], kind);
      else setMessage("");
    } else if (symbol === "|") {
      const target = sourceTarget(
        current.current,
        activePath,
        selection.length === 1 ? selection[0] : null,
        selectedEdge,
      );
      let id = "";
      mutate((d) => {
        const n = newNode("", "source");
        id = n.id;
        d.nodes.push(n);
        attachSource(d, n, target);
        const anchorPoint = attachmentPosition(d, target);
        d.layout.nodes[id] = defaultBox(
          point?.x ?? (anchorPoint ? anchorPoint.x - 84 : 0),
          point?.y ?? (anchorPoint ? anchorPoint.y - 110 : 0),
        );
        d.status = "draft";
      });
      if (!id) return;
      autoCode.current.add(id);
      pendingText.current = { id, text: "| " };
      inlineRemembered.current = false;
      setSelectedEdge(null);
      setInspector(false);
      setSelection([id]);
      setEditing(id);
    } else if (symbol === "()" || symbol === "[]") {
      if (!selected || selected.kind !== "concept") {
        setMessage("Sélectionnez un topic, puis ajoutez ses précisions.");
        return;
      }
      setInspector(true);
      setTimeout(
        () =>
          container.current
            ?.querySelector<HTMLTextAreaElement>(
              symbol === "()"
                ? 'textarea[aria-label="Sous-thèmes"]'
                : 'textarea[aria-label="Portées"]',
            )
            ?.focus(),
        50,
      );
    } else if (symbol === ";") {
      add("concept", "", point);
      setMessage(
        "Ce bloc indépendant démarre un autre DAG. Les connexions déterminent automatiquement les DAGs.",
      );
    } else if (symbol === "none") {
      if (inspectorFlush.current && !inspectorFlush.current()) return;
      const pending = pendingText.current;
      if (pending && !applyText(pending.id, pending.text, true, false)) return;
      if (current.current.status === "none") transmit(current.current);
      else
        mutate((d) => {
          d.status = "none";
        });
      setMessage("");
    }
  }
  const dropConnection: OnConnectEnd = (event, state) => {
    if (
      disabled ||
      connectionDone.current ||
      !state.fromNode ||
      !state.fromHandle
    )
      return;
    const p = "changedTouches" in event ? event.changedTouches[0] : event;
    const target =
      document.elementFromPoint(p.clientX, p.clientY) ||
      (event.target as Element);
    const groupEdge = target
      .closest("[data-group-edge]")
      ?.getAttribute("data-group-edge");
    if (groupEdge) {
      const relation = current.current.edges.find((e) => e.id === groupEdge);
      if (
        relation &&
        ["definition", "priority"].includes(relation.kind) &&
        ["coexistence", "addition", "link", "membership"].includes(relationKind)
      ) {
        setMessage(
          "Cette relation a deux sujets. Choisissez → pour relier une cause à la relation entière.",
        );
        return;
      }
      mutate((d) => {
        const id = materializeGroup(d, groupEdge),
          source = state.fromNode!.id;
        const e: GraphEdge = {
          id: uid("e"),
          source,
          target: id,
          kind: ["coexistence", "addition", "link", "membership"].includes(
            relationKind,
          )
            ? "membership"
            : relationKind,
          dominant:
            relationKind === "priority"
              ? prioritySource.current
                ? source
                : id
              : null,
        };
        d.edges.push(e);
        d.layout.edges[e.id] = {
          ...defaultEdgeView(),
          source_port: state.fromHandle!.id as Port,
          target_port: facingPort(d.layout.nodes[id], d.layout.nodes[source]),
        };
        const path = d.paths.find((p) => p.node_ids.includes(id))!;
        path.node_ids = [...new Set([...path.node_ids, source])];
        path.edge_ids.push(e.id);
      });
      return;
    }
    if (!target.closest(".react-flow__pane")) return;
    const newMember =
      relationKind === "membership" &&
      ["coexistence", "addition", "definition", "priority"].includes(
        state.fromNode.data.kind as string,
      );
    if (relationKind === "membership" && !newMember) {
      setMessage(
        "Reliez ce trait à une unité de relation (&, +, =, > ou <), ou choisissez → pour créer la suite.",
      );
      return;
    }
    const at = rf.screenToFlowPosition({ x: p.clientX, y: p.clientY }),
      source = state.fromNode.id,
      sourcePort = state.fromHandle.id as Port;
    if (
      newMember &&
      ["definition", "priority"].includes(state.fromNode.data.kind as string) &&
      current.current.edges.filter(
        (e) => e.kind === "membership" && e.target === state.fromNode!.id,
      ).length >= 2
    ) {
      setMessage("Cette relation relie déjà deux sujets.");
      return;
    }
    const n = newNode();
    mutate((d) => {
      const sourceBox = d.layout.nodes[source];
      const offset = anchor(defaultBox(), opposite[sourcePort]);
      const b = defaultBox(at.x - offset.x, at.y - offset.y),
        a = sourceBox;
      // Keep horizontal/vertical connections straight when dropped nearby.
      if (
        ["left", "right"].includes(sourcePort) &&
        Math.abs(b.y + b.height / 2 - a.y - a.height / 2) < 18 / rf.getZoom()
      )
        b.y = a.y + (a.height - b.height) / 2;
      if (
        ["top", "bottom"].includes(sourcePort) &&
        Math.abs(b.x + b.width / 2 - a.x - a.width / 2) < 18 / rf.getZoom()
      )
        b.x = a.x + (a.width - b.width) / 2;
      d.nodes.push(n);
      d.layout.nodes[n.id] = b;
      const e: GraphEdge = {
        id: uid("e"),
        source: newMember ? n.id : source,
        target: newMember ? source : n.id,
        kind: relationKind,
        dominant:
          relationKind === "priority"
            ? prioritySource.current
              ? source
              : n.id
            : null,
      };
      d.edges.push(e);
      d.layout.edges[e.id] = {
        ...defaultEdgeView(),
        source_port: newMember ? opposite[sourcePort] : sourcePort,
        target_port: newMember ? sourcePort : opposite[sourcePort],
      };
      const path = d.paths.find((p) => p.id === activePath)!;
      path.node_ids = [...new Set([...path.node_ids, source, n.id])];
      path.edge_ids.push(e.id);
      d.status = "coded";
    });
    autoCode.current.add(n.id);
    pendingText.current = { id: n.id, text: "" };
    inlineRemembered.current = false;
    setSelection([n.id]);
    setSelectedEdge(null);
    setEditing(n.id);
  };
  function reconnect(id: string, c: Connection) {
    if (c.source === c.target) return;
    const target = current.current.nodes.find((n) => n.id === c.target),
      source = current.current.nodes.find((n) => n.id === c.source);
    if (
      !target ||
      !source ||
      target.kind === "source" ||
      source.kind === "source"
    )
      return;
    if (
      current.current.edges.find((e) => e.id === id)?.kind === "membership" &&
      ["definition", "priority"].includes(target.kind) &&
      current.current.edges.filter(
        (e) => e.id !== id && e.kind === "membership" && e.target === c.target,
      ).length >= 2
    ) {
      setMessage("Cette relation a déjà deux sujets.");
      return;
    }
    mutate((d) => {
      const e = d.edges.find((e) => e.id === id)!;
      const previousUnit = d.nodes.find((n) => n.id === e.target);
      if (
        e.kind === "membership" &&
        previousUnit?.kind === "priority" &&
        previousUnit.dominant === e.source
      )
        previousUnit.dominant = c.target === e.target ? c.source : null;
      const wasSource = e.dominant === e.source;
      e.source = c.source;
      e.target = c.target;
      if (
        e.kind === "membership" &&
        !["addition", "coexistence", "definition", "priority"].includes(
          target.kind,
        )
      )
        e.kind = "link";
      if (e.kind === "priority") e.dominant = wasSource ? e.source : e.target;
      Object.assign(d.layout.edges[id], {
        source_port: c.sourceHandle || "right",
        target_port: c.targetHandle || "left",
        points: [],
      });
      d.paths
        .filter((p) => p.edge_ids.includes(id))
        .forEach(
          (p) =>
            (p.node_ids = [...new Set([...p.node_ids, e.source, e.target])]),
        );
    });
  }
  // An ordinary autosave must not disable the button the user is clicking:
  // leaving a text field flushes it before the click. Queue navigation after
  // that save; only an actual navigation/request locks navigation controls.
  const busy =
    saving &&
    (flightAction.current !== "save" ||
      !!(queued.current && queued.current.action !== "save"));
  const previousDagSource = args.previous_sources
    ?.filter((source) => source.paths.length)
    .at(-1);
  const workspaceHeight = view.height;
  const pendingProposal =
    args.ai_proposal?.status === "pending" ? args.ai_proposal : null;
  const latestLatex = publicationReady(
    doc,
    args,
    saving || !!queued.current,
    inspectorDirty || !!pendingText.current || gesture.current,
  );
  function commitCurrent(): GraphDoc | null {
    if (inspectorFlush.current && !inspectorFlush.current()) return null;
    const p = pendingText.current;
    if (p && !applyText(p.id, p.text, true, false)) return null;
    if (textTimer.current) clearTimeout(textTimer.current);
    return clone(current.current);
  }
  function requestExport(kind: ExportKind) {
    const snapshot = commitCurrent();
    if (!snapshot) return;
    pendingExport.current = kind;
    // Even a just-flushed inspector can have started an autosave. Wait for
    // its acknowledgement, then export exactly the acknowledged snapshot.
    transmit(snapshot);
  }
  useEffect(() => {
    const kind = pendingExport.current;
    if (
      !kind ||
      !latestLatex ||
      !publicationReady(
        current.current,
        args,
        !!inFlight.current || !!queued.current,
        !!pendingText.current || inspectorDirty || gesture.current,
      )
    )
      return;
    pendingExport.current = null;
    const bundle = args.latex!;
    if (kind === "json") download(args.document);
    else if (kind === "pdf") {
      if (bundle.current && bundle.pdf)
        downloadBase64(bundle.pdf, "narrative.pdf");
      else
        setMessage(
          "Compilez l’aperçu PDF de la version actuelle avant de le télécharger.",
        );
    } else
      downloadText(
        kind === "tikz" ? bundle.tikz : bundle.standalone,
        kind === "tikz" ? "narrative.tikz" : "narrative.tex",
      );
  }, [args, doc, saving, inspectorDirty, editing]);
  useEffect(() => {
    if (!showProposal || review) return;
    const previous = document.activeElement as HTMLElement | null;
    const timer = setTimeout(
      () =>
        proposalDialog.current
          ?.querySelector<HTMLButtonElement>("button")
          ?.focus(),
      0,
    );
    return () => {
      clearTimeout(timer);
      previous?.focus?.();
    };
  }, [showProposal, review]);
  return (
    <Context.Provider
      value={{
        doc,
        readOnly: disabled,
        beginGesture,
        resize,
        moveLabel,
        undoGraph: undo,
        redoGraph: redo,
        vocabulary: {
          topics: args.topics,
          subtopics: args.subtopics,
          scopes: args.scopes,
          labels: args.topic_labels,
        },
        selectEdge: (id) => {
          setSelectedEdge(id);
          setSelection([]);
          setInspector(false);
        },
        moveRoutePoint: (id, index, point, finish) => {
          const next = clone(current.current),
            v = next.layout.edges[id],
            edge = next.edges.find((e) => e.id === id);
          if (!v || !edge) return;
          if (v.route === "straight" || index < 0) {
            const p = routePoints(next, edge),
              start = p[0],
              end = p.at(-1)!;
            v.route = "bezier";
            v.points = [
              { x: start.x + (point.x - start.x) * 0.8, y: point.y },
              { x: end.x + (point.x - end.x) * 0.8, y: point.y },
            ];
          } else if (v.route === "orthogonal" && v.points.length <= 2) {
            const p = routePoints(next, edge),
              start = p[0],
              end = p.at(-1)!;
            v.points = ["left", "right"].includes(v.source_port)
              ? [
                  { x: point.x, y: start.y },
                  { x: point.x, y: end.y },
                ]
              : [
                  { x: start.x, y: point.y },
                  { x: end.x, y: point.y },
                ];
          } else {
            if (!v.points.length)
              v.points = routePoints(next, edge).slice(1, -1);
            v.points[index] = point;
          }
          local(next);
          if (finish) finishGesture();
        },
        editing,
        editText: applyText,
        stopEditing: () => {
          const p = pendingText.current;
          if (p) applyText(p.id, p.text, true);
          else setEditing(null);
        },
        initialText: (id: string) =>
          pendingText.current?.id === id
            ? pendingText.current.text
            : doc.editor?.node_text[id],
      }}
    >
      <div
        className={`editor ${review ? "review-editor" : ""}`}
        ref={container}
        style={{ height: disabled ? 370 : workspaceHeight }}
      >
        <header>
          <div className="heading">
            <strong>{review ? "Proposition à relire" : args.title}</strong>
            {!review && args.phase && (
              <span className="phase-badge">{args.phase}</span>
            )}
          </div>
          <div className="header-actions">
            {!disabled && !review && args.ai_enabled && (
              <button
                disabled={!args.ai_ready || busy}
                title={
                  args.ai_ready
                    ? `Envoyer le contexte utile à OpenAI (${args.ai_model}) pour préparer une proposition. Aucun identifiant ajouté ; les textes peuvent contenir des informations personnelles.`
                    : "OPENAI_API_KEY doit être disponible dans l’environnement de lancement."
                }
                onClick={() =>
                  pendingProposal
                    ? setShowProposal(true)
                    : transmit(current.current, "ai_request")
                }
              >
                {pendingProposal
                  ? "Voir la proposition IA"
                  : "Recommandation IA"}
              </button>
            )}
            {!disabled && !review && (
              <>
                <button
                  aria-pressed={dictionary}
                  onClick={() => {
                    setDictionary(!dictionary);
                    setLatex(false);
                  }}
                >
                  Lexique
                </button>
                <button
                  aria-pressed={latex}
                  onClick={() => {
                    if (!latex) {
                      const snapshot = commitCurrent();
                      if (!snapshot) return;
                      transmit(snapshot);
                    }
                    setLatex(!latex);
                    setDictionary(false);
                  }}
                >
                  LaTeX
                </button>
              </>
            )}
            {!disabled && (
              <button
                title="Options, historique et fichiers"
                aria-label="Options"
                aria-pressed={options}
                onClick={() => setOptions(!options)}
              >
                ⋯
              </button>
            )}
            <span className="save-status" role="status">
              {disabled
                ? "Lecture seule"
                : review
                  ? "À valider"
                  : inspectorDirty || pendingText.current
                    ? "Saisie en cours"
                    : saving
                      ? "Enregistrement…"
                      : message
                        ? "À vérifier"
                        : revision.current
                          ? doc.status === "none"
                            ? "none · Enregistré"
                            : "Enregistré"
                          : "Brouillon"}
            </span>
          </div>
        </header>
        {doc.status === "none" && (
          <div className="none-banner" role="status">
            none · Aucun ajout substantiel pour cette réponse.{" "}
            {doc.nodes.length > 0
              ? "Le graphe cumulatif reste conservé."
              : "Aucun bloc de topic n’est créé."}
          </div>
        )}
        {message && (
          <div role="alert" className="notice">
            {message}
            <button
              onClick={() => setMessage("")}
              aria-label="Fermer le message"
            >
              ×
            </button>
          </div>
        )}
        {!doc.provenance.import_reviewed && (
          <div className="notice">
            Import à vérifier : {doc.provenance.import_warnings.join(" ")}{" "}
            {!disabled && (
              <button
                onClick={() =>
                  mutate((d) => {
                    d.provenance.import_reviewed = true;
                  })
                }
              >
                Regroupement vérifié
              </button>
            )}
          </div>
        )}
        <div className="workspace">
          {!disabled && !review && (
            <section
              className="interview-panel"
              aria-label="Question et réponse"
            >
              <section className="question-panel">
                <h3>Question</h3>
                <div
                  className="transcript-scroll"
                  tabIndex={0}
                  role="textbox"
                  aria-readonly="true"
                  aria-multiline="true"
                  aria-label="Question de l’entretien"
                  data-native-text
                >
                  {args.question}
                </div>
              </section>
              <section className="answer-panel">
                <h3>Réponse</h3>
                <div
                  className="transcript-scroll"
                  tabIndex={0}
                  role="textbox"
                  aria-readonly="true"
                  aria-multiline="true"
                  aria-label="Réponse du participant"
                  data-native-text
                >
                  {args.response}
                </div>
              </section>
            </section>
          )}
          <div className="graph-area">
            {!disabled && (
              <div className="toolbar" aria-label="Symboles du coding scheme">
                <button
                  title="Ajouter un topic (ou double-cliquer sur la toile)"
                  aria-label="Ajouter un topic"
                  onClick={() => add()}
                >
                  T
                </button>
                {symbols.map(([symbol, explanation]) => (
                  <button
                    className="symbol-button"
                    key={symbol}
                    title={explanation}
                    aria-label={symbol}
                    aria-pressed={
                      ["→", "—", "=", "&", "+", "<", ">"].includes(symbol)
                        ? relationKind ===
                            (symbol === "→"
                              ? "causal"
                              : symbol === "="
                                ? "definition"
                                : symbol === "—"
                                  ? "link"
                                  : symbol === "&"
                                    ? "coexistence"
                                    : symbol === "+"
                                      ? "addition"
                                      : "priority") &&
                          (!["<", ">"].includes(symbol) ||
                            (symbol === ">") === prioritySource.current)
                        : symbol === "none"
                          ? doc.status === "none"
                          : undefined
                    }
                    onClick={() => applySymbol(symbol)}
                  >
                    {symbol}
                  </button>
                ))}
                {doc.paths.length > 1 && (
                  <select
                    aria-label="DAG actif"
                    value={activePath}
                    onChange={(e) => setActivePath(e.target.value)}
                  >
                    {doc.paths.map((p) => (
                      <option key={p.id} value={p.id}>
                        {dagLabel(doc, p.id)}
                      </option>
                    ))}
                  </select>
                )}
                <span className="toolbar-spacer" />
                <button
                  title="Annuler (⌘/Ctrl Z)"
                  aria-label="Annuler"
                  disabled={
                    !history.current.length &&
                    !args.history?.some(
                      (h) =>
                        h.revision < (timeline.current.cursor ?? args.revision),
                    )
                  }
                  onClick={undo}
                >
                  ↶
                </button>
                <button
                  title="Rétablir (⌘/Ctrl Maj Z)"
                  aria-label="Rétablir"
                  disabled={!future.current.length}
                  onClick={redo}
                >
                  ↷
                </button>
                <button
                  title="Organiser automatiquement les blocs"
                  onClick={autoLayout}
                >
                  Organiser
                </button>
                <button
                  title="Adapter la figure à la zone visible (action volontaire)"
                  onClick={() => void view.recenter()}
                >
                  Recentrer
                </button>
              </div>
            )}
            <div
              className="canvas"
              ref={canvasRef}
              onPointerDownCapture={(event) => {
                if ((event.target as HTMLElement).closest(".inspector-panel"))
                  return;
                if (inspectorFlush.current && !inspectorFlush.current()) {
                  event.preventDefault();
                  event.stopPropagation();
                  return;
                }
                const target = event.target as HTMLElement;
                if (
                  !target.closest(
                    "input,textarea,select,.selection-tools,.inspector-panel",
                  )
                )
                  window.getSelection()?.removeAllRanges();
                if (
                  event.button === 0 &&
                  target.closest(
                    ".react-flow__node, .react-flow__nodesselection-rect",
                  ) &&
                  !target.closest(
                    "input,textarea,select,button,.selection-tools,.inspector-panel",
                  )
                )
                  setPointerHeld(true);
              }}
              tabIndex={0}
              aria-label="Toile de codage"
            >
              <ReactFlow<FlowNode>
                nodes={flowNodes}
                edges={flowEdges}
                nodeTypes={nodeTypes}
                edgeTypes={edgeTypes}
                onNodesChange={changeNodes}
                onNodeDragStart={() => {
                  beginGesture();
                }}
                onNodeDragStop={finishGesture}
                onSelectionDragStart={beginGesture}
                onSelectionDragStop={finishGesture}
                onSelectionStart={() => {
                  setBoxSelecting(true);
                  setSelectedEdge(null);
                }}
                onSelectionEnd={() => setBoxSelecting(false)}
                onConnectStart={() => {
                  connectionDone.current = false;
                }}
                onConnect={(c: Connection) => {
                  connectionDone.current = true;
                  connect(
                    c.source,
                    c.target,
                    relationKind,
                    (c.sourceHandle || "right") as Port,
                    (c.targetHandle || "left") as Port,
                  );
                }}
                onConnectEnd={dropConnection}
                connectionMode={ConnectionMode.Loose}
                onReconnect={(e, c) => reconnect(e.id, c)}
                reconnectRadius={18}
                onEdgeClick={(_, e) => {
                  const paths = current.current.paths.filter((p) =>
                    p.edge_ids.includes(e.id),
                  );
                  if (paths.length === 1) setActivePath(paths[0].id);
                  setSelectedEdge(e.id);
                  setSelection([]);

                  setInspector(false);
                }}
                onPaneClick={() => {
                  if (disabled) return;
                  const p = pendingText.current;
                  if (p) applyText(p.id, p.text, true);
                  setEditing(null);

                  setSelection([]);
                  setSelectedEdge(null);
                  setInspector(false);
                }}
                onDoubleClick={(e) => {
                  if (
                    !disabled &&
                    (e.target as HTMLElement).classList.contains(
                      "react-flow__pane",
                    )
                  )
                    add(
                      "concept",
                      "",
                      rf.screenToFlowPosition({ x: e.clientX, y: e.clientY }),
                    );
                }}
                onNodeClick={(_, n) => {
                  const paths = current.current.paths.filter((p) =>
                    p.node_ids.includes(n.id),
                  );
                  if (paths.length === 1) setActivePath(paths[0].id);
                  setInspector(false);
                }}
                onNodeDoubleClick={(_, n) => {
                  if (!disabled) {
                    if (["definition", "priority"].includes(n.data.kind))
                      setInspector(true);
                    else editNode(n.id);
                  }
                }}
                autoPanOnNodeFocus={false}
                defaultViewport={view.initialViewport}
                onMoveEnd={(_, viewport) => view.rememberView(viewport)}
                autoPanOnNodeDrag={false}
                autoPanOnConnect={false}
                zoomOnScroll={false}
                zoomOnPinch={true}
                minZoom={0.15}
                maxZoom={2.5}
                nodesConnectable={!disabled}
                elementsSelectable
                panOnScroll={false}
                zoomOnDoubleClick={false}
                selectionOnDrag={!disabled}
                selectionMode={SelectionMode.Partial}
                panOnDrag={[1, 2]}
                panActivationKeyCode="Space"
                autoPanOnSelection={false}
                multiSelectionKeyCode="Shift"
                deleteKeyCode={null}
                colorMode="light"
              >
                {grid && <Background gap={20} size={1} color="#dedede" />}
                <Controls showInteractive={false} />
                <svg
                  style={{
                    position: "absolute",
                    width: 0,
                    height: 0,
                    pointerEvents: "none",
                  }}
                >
                  <defs>
                    <marker
                      id="narrative-arrow"
                      viewBox="0 0 10 10"
                      refX="9"
                      refY="5"
                      markerWidth="8"
                      markerHeight="8"
                      orient="auto-start-reverse"
                    >
                      <path d="M0 0 L10 5 L0 10 z" fill="black" />
                    </marker>
                  </defs>
                </svg>
                <ViewportPortal>
                  <svg className="overlays" aria-hidden="true">
                    {guides.map((g, i) =>
                      g.axis === "x" ? (
                        <g key={i}>
                          <line
                            x1={g.value}
                            x2={g.value}
                            y1={g.from}
                            y2={g.to}
                          />
                          {g.label && (
                            <text x={g.value + 5} y={g.from}>
                              {g.label}
                            </text>
                          )}
                        </g>
                      ) : (
                        <g key={i}>
                          <line
                            x1={g.from}
                            x2={g.to}
                            y1={g.value}
                            y2={g.value}
                          />
                          {g.label && (
                            <text x={g.from} y={g.value - 5}>
                              {g.label}
                            </text>
                          )}
                        </g>
                      ),
                    )}
                    {doc.nodes
                      .filter((n) => n.kind === "source" && n.attachment)
                      .map((n) => {
                        const b = doc.layout.nodes[n.id],
                          p = attachmentPosition(doc, n.attachment!);
                        if (!p) return null;
                        return (
                          <line
                            key={n.id}
                            className="source-leader"
                            x1={b.x + b.width / 2}
                            y1={b.y}
                            x2={p.x}
                            y2={p.y}
                          />
                        );
                      })}
                  </svg>
                </ViewportPortal>
              </ReactFlow>
              {!doc.nodes.length && (
                <div className="empty-hint">
                  {doc.status === "none" ? (
                    <>
                      <strong>none</strong>
                      <br />
                      Aucun ajout substantiel pour cette réponse.
                    </>
                  ) : (
                    <>Double-cliquez ici pour créer un bloc.</>
                  )}
                  <br />
                  {doc.status !== "none" &&
                    "Tirez un lien depuis un carré pour créer la suite."}
                </div>
              )}
              {!disabled &&
                (selected || selectedEdge || selection.length > 1) &&
                !editing && (
                  <FloatingToolbar
                    box={
                      selection.length
                        ? bounds(selection.map((id) => doc.layout.nodes[id]))
                        : (() => {
                            const e = doc.edges.find(
                              (e) => e.id === selectedEdge,
                            )!;
                            // Keep the toolbar outside the full route, including
                            // bends and Bezier control points, rather than only
                            // outside its midpoint where it could hide the line.
                            return bounds(
                              routePoints(doc, e).map((p) =>
                                defaultBox(p.x, p.y, 1, 1),
                              ),
                            );
                          })()
                    }
                    canvas={canvasRef}
                    compact={!!selectedEdge}
                    hidden={pointerHeld || moving || boxSelecting}
                  >
                    <button
                      className="menu-close"
                      aria-label="Fermer le menu de l’élément"
                      onClick={() => {
                        setSelection([]);
                        setSelectedEdge(null);
                      }}
                    >
                      ×
                    </button>
                    {selected &&
                      !["definition", "priority"].includes(selected.kind) && (
                        <button onClick={() => editNode(selected.id)}>
                          Texte
                        </button>
                      )}
                    <button
                      aria-label="Réglages"
                      title="Réglages du lien ou du bloc"
                      onClick={() => setInspector(!inspector)}
                    >
                      {selectedEdge ? (
                        <span aria-hidden="true">⚙︎</span>
                      ) : (
                        "Réglages"
                      )}
                    </button>
                    {selection.length > 0 && (
                      <button onClick={copySelection}>Copier</button>
                    )}
                    {(args.clipboard_available || clipboard.current) && (
                      <button onClick={paste}>Coller</button>
                    )}
                    {selection.length > 0 && (
                      <button
                        title="Dupliquer (copier puis coller)"
                        onClick={duplicateSelection}
                      >
                        Dupliquer
                      </button>
                    )}
                    <button
                      aria-label="Supprimer"
                      title="Supprimer le lien ou la sélection"
                      onClick={removeSelected}
                    >
                      {selectedEdge ? (
                        <svg
                          width="16"
                          height="16"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.6"
                          aria-hidden="true"
                        >
                          <path d="M4 6h16M9 6V3h6v3M6 6l1 15h10l1-15M10 10v7M14 10v7" />
                        </svg>
                      ) : (
                        "Supprimer"
                      )}
                    </button>
                    {selected &&
                      [
                        "coexistence",
                        "addition",
                        "definition",
                        "priority",
                      ].includes(selected.kind) &&
                      (!["definition", "priority"].includes(selected.kind) ||
                        doc.edges.filter(
                          (e) =>
                            e.kind === "membership" && e.target === selected.id,
                        ).length < 2) && (
                        <button
                          title="Tirer ensuite un trait d’un topic vers ce groupe ; → crée une cause du groupe, et ce mode ajoute seulement un membre."
                          onClick={() => setRelationKind("membership")}
                        >
                          Ajouter un membre
                        </button>
                      )}
                    {selectedEdge && (
                      <>
                        <label
                          className="edge-relation-picker"
                          title="Type de relation : ouvrir pour choisir"
                        >
                          <span aria-hidden="true">
                            {edgeLabel(
                              doc.edges.find((e) => e.id === selectedEdge)!,
                            ) ||
                              (doc.edges.find((e) => e.id === selectedEdge)!
                                .kind === "causal"
                                ? "→"
                                : "—")}
                            <small>▾</small>
                          </span>
                          <select
                            aria-label="Relation du lien"
                            value={
                              doc.edges.find((e) => e.id === selectedEdge)!
                                .kind === "priority"
                                ? doc.edges.find((e) => e.id === selectedEdge)!
                                    .dominant ===
                                  doc.edges.find((e) => e.id === selectedEdge)!
                                    .source
                                  ? ">"
                                  : "<"
                                : doc.edges.find((e) => e.id === selectedEdge)!
                                    .kind
                            }
                            onChange={(e) =>
                              applySymbol(
                                relations.find(
                                  ([kind]) => kind === e.target.value,
                                )?.[1] || e.target.value,
                              )
                            }
                          >
                            {relations.map(([kind, symbol, label]) => (
                              <option key={kind} value={kind}>
                                {symbol} {label.split(":")[0]}
                              </option>
                            ))}
                            <option value=">">&gt; Priorité au départ</option>
                            <option value="<">&lt; Priorité à l’arrivée</option>
                            {[
                              "coexistence",
                              "addition",
                              "definition",
                              "priority",
                            ].includes(
                              doc.nodes.find(
                                (n) =>
                                  n.id ===
                                  doc.edges.find((e) => e.id === selectedEdge)!
                                    .target,
                              )!.kind,
                            ) && (
                              <option value="membership">
                                Trait vers le groupe
                              </option>
                            )}
                          </select>
                        </label>
                        <button
                          aria-label="Inverser le lien"
                          title="Inverser le sens du lien"
                          onClick={() =>
                            mutate((d) => reverseRelation(d, selectedEdge))
                          }
                          disabled={
                            doc.edges.find((e) => e.id === selectedEdge)!
                              .kind === "membership"
                          }
                        >
                          ↔
                        </button>
                      </>
                    )}
                    {selectedEdge &&
                      [
                        "coexistence",
                        "addition",
                        "definition",
                        "priority",
                      ].includes(
                        doc.edges.find((e) => e.id === selectedEdge)!.kind,
                      ) && (
                        <button
                          aria-label="Relier à la relation"
                          title="Rendre cette relation ciblable par une flèche, en conservant ses deux sujets et sa priorité éventuelle."
                          onClick={() => {
                            let id = "";
                            mutate((d) => {
                              id = materializeGroup(d, selectedEdge);
                            });
                            setSelectedEdge(null);
                            setSelection([id]);
                          }}
                        >
                          <span aria-hidden="true">Relier</span>
                        </button>
                      )}
                    {selection.length > 1 && (
                      <>
                        <button onClick={() => align("center-y")}>
                          Aligner ↔
                        </button>
                        <button onClick={() => align("center-x")}>
                          Aligner ↕
                        </button>
                        <button onClick={() => align("distribute-x")}>
                          Espacer
                        </button>
                      </>
                    )}
                    {!review && (selected || selectedEdge) && (
                      <details
                        className="citation-menu"
                        key={selected?.id || selectedEdge!}
                      >
                        <summary
                          aria-label="Insérer une citation"
                          title="Insérer une citation du participant"
                        >
                          {selectedEdge ? "Citation" : "Insérer une citation"}
                          {doc.tracking!.objects[selected?.id || selectedEdge!]
                            ?.quote.text
                            ? " · ✓"
                            : ""}
                        </summary>
                        <EvidenceBox
                          key={selected?.id || selectedEdge!}
                          response={args.response || ""}
                          meta={
                            doc.tracking!.objects[selected?.id || selectedEdge!]
                          }
                          onChange={(value) =>
                            mutate((d) => {
                              d.tracking!.objects[
                                selected?.id || selectedEdge!
                              ] = value;
                            })
                          }
                        />
                      </details>
                    )}
                  </FloatingToolbar>
                )}
              {inspector && !disabled && (selected || selectedEdge) && (
                <aside
                  className="inspector-panel"
                  hidden={pointerHeld || moving || boxSelecting}
                  aria-label="Réglages de l’élément"
                >
                  <button
                    className="close-panel"
                    aria-label="Fermer les réglages"
                    onClick={() => {
                      if (!inspectorFlush.current || inspectorFlush.current())
                        setInspector(false);
                    }}
                  >
                    ×
                  </button>
                  {selected ? (
                    <NodeInspector
                      key={selected.id}
                      registerFlush={(fn) => {
                        inspectorFlush.current = fn;
                      }}
                      onDirty={(v) => {
                        setInspectorDirty(v);
                        if (review)
                          onReviewChange?.(clone(current.current), !v);
                      }}
                      node={selected}
                      box={doc.layout.nodes[selected.id]}
                      args={args}
                      doc={doc}
                      apply={(node, box) =>
                        mutate((d) => {
                          d.nodes = d.nodes.map((n) =>
                            n.id === node.id ? node : n,
                          );
                          if (node.kind === "source" && node.attachment)
                            attachSource(d, node, node.attachment);
                          d.layout.nodes[node.id] = box;
                        })
                      }
                    />
                  ) : (
                    <EdgeInspector
                      key={selectedEdge!}
                      registerFlush={(fn) => {
                        inspectorFlush.current = fn;
                      }}
                      onDirty={(v) => {
                        setInspectorDirty(v);
                        if (review)
                          onReviewChange?.(clone(current.current), !v);
                      }}
                      edge={doc.edges.find((e) => e.id === selectedEdge)!}
                      view={doc.layout.edges[selectedEdge!]}
                      doc={doc}
                      apply={(edge, view) =>
                        mutate((d) => {
                          d.edges = d.edges.map((e) =>
                            e.id === edge.id ? edge : e,
                          );
                          d.layout.edges[edge.id] = view;
                        })
                      }
                    />
                  )}
                  <button onClick={removeSelected}>
                    Supprimer cet élément
                  </button>
                </aside>
              )}
            </div>
            {!disabled && (
              <div className="canvas-caption">
                Lien :{" "}
                {relationKind === "causal"
                  ? "→ causal"
                  : relationKind === "definition"
                    ? "= sans pointe"
                    : relationKind === "coexistence"
                      ? "& sans pointe"
                      : relationKind === "addition"
                        ? "+ sans pointe"
                        : relationKind === "membership"
                          ? "— membre du groupe"
                          : relationKind === "priority"
                            ? prioritySource.current
                              ? "> sans pointe"
                              : "< sans pointe"
                            : "— sans pointe"}{" "}
                · Glisser sur le fond : sélectionner · Espace + glisser :
                déplacer la vue · Double-clic : créer · Maj + clic : ajouter à
                la sélection · ⌘/Ctrl C, V, Z
              </div>
            )}
          </div>
          {dictionary && !disabled && !review && (
            <section
              className="latex-panel dictionary-panel"
              aria-label="Lexique de codage"
            >
              <div className="panel-heading">
                <h3>Lexique</h3>
                <button
                  aria-label="Fermer le lexique"
                  onClick={() => setDictionary(false)}
                >
                  ×
                </button>
              </div>
              <label>
                Rechercher
                <input
                  aria-label="Rechercher dans le lexique"
                  value={dictionaryQuery}
                  onChange={(e) => setDictionaryQuery(e.target.value)}
                  placeholder="Code ou texte…"
                />
              </label>
              <div
                className="dictionary-tabs"
                role="group"
                aria-label="Éléments du lexique"
              >
                {(["topics", "subtopics", "scopes"] as const).map((kind) => (
                  <button
                    key={kind}
                    aria-pressed={dictionaryKind === kind}
                    onClick={() => setDictionaryKind(kind)}
                  >
                    {kind === "topics"
                      ? "Topics"
                      : kind === "subtopics"
                        ? "Sous-thèmes"
                        : "Portées"}
                  </button>
                ))}
              </div>
              <small>
                {dictionaryKind === "topics"
                  ? "Réutiliser dans le bloc sélectionné, ou créer un bloc."
                  : selected?.kind === "concept"
                    ? "Ajouter au bloc sélectionné."
                    : "Sélectionnez un topic pour lui ajouter cette précision."}
              </small>
              <div className="dictionary-results">
                {[
                  ...new Set(
                    dictionaryKind === "topics"
                      ? args.topics
                      : dictionaryKind === "scopes"
                        ? args.scopes
                        : Object.values(args.subtopics).flat(),
                  ),
                ]
                  .filter((value) => {
                    const q = dictionaryQuery
                      .toLowerCase()
                      .replaceAll("_", " ");
                    return [
                      value,
                      ...(dictionaryKind === "topics"
                        ? args.topic_labels?.[value] || []
                        : []),
                    ].some((s) =>
                      s.toLowerCase().replaceAll("_", " ").includes(q),
                    );
                  })
                  .sort((a, b) => a.localeCompare(b))
                  .map((value) => (
                    <button
                      key={value}
                      disabled={
                        dictionaryKind !== "topics" &&
                        selected?.kind !== "concept"
                      }
                      title={value}
                      onClick={() => {
                        if (dictionaryKind === "topics") {
                          if (selected?.kind === "concept")
                            mutate((d) => {
                              const n = d.nodes.find(
                                (n) => n.id === selected.id,
                              )!;
                              n.code = value;
                              n.label = value.replaceAll("_", " ");
                              d.layout.nodes[n.id].height = Math.max(
                                d.layout.nodes[n.id].height,
                                textHeight(n, d.layout.nodes[n.id].width),
                              );
                            });
                          else add("concept", value);
                        } else if (selected?.kind === "concept")
                          mutate((d) => {
                            const n = d.nodes.find(
                              (n) => n.id === selected.id,
                            )!;
                            const field =
                              dictionaryKind === "subtopics"
                                ? "subtopics"
                                : "scopes";
                            n[field] = [...new Set([...n[field], value])];
                            d.layout.nodes[n.id].height = Math.max(
                              d.layout.nodes[n.id].height,
                              textHeight(n, d.layout.nodes[n.id].width),
                            );
                          });
                      }}
                    >
                      {value.replaceAll("_", " ")}
                      <small>{value}</small>
                    </button>
                  ))}
              </div>
            </section>
          )}
          {latex && !disabled && !review && (
            <section className="latex-panel" aria-label="LaTeX du graphe">
              <div className="panel-heading">
                <h3>LaTeX</h3>
                <button
                  aria-label="Fermer LaTeX"
                  onClick={() => setLatex(false)}
                >
                  ×
                </button>
              </div>
              <p>
                {latestLatex
                  ? "Positions et ancrages de la version enregistrée."
                  : "Actualisation après l’enregistrement…"}
              </p>
              <div className="export-actions">
                <button disabled={busy} onClick={() => requestExport("tikz")}>
                  TikZ ↓
                </button>
                <button disabled={busy} onClick={() => requestExport("tex")}>
                  .tex ↓
                </button>
                <button
                  onClick={() =>
                    downloadText(
                      args.latex?.styles || "",
                      "narrative_styles.tex",
                    )
                  }
                >
                  Styles ↓
                </button>
              </div>
              <details open={!args.latex?.pdf}>
                <summary>Code TikZ</summary>
                <pre tabIndex={0}>
                  {latestLatex
                    ? args.latex?.tikz
                    : "Enregistrement du graphe en cours…"}
                </pre>
              </details>
              <button
                disabled={busy}
                onClick={() => transmit(current.current, "preview")}
              >
                Compiler l’aperçu PDF
              </button>
              {args.latex?.pdf && (
                <>
                  {(!args.latex.current || !latestLatex) && (
                    <p role="status">
                      Le PDF correspond à une version antérieure.
                    </p>
                  )}
                  {args.latex.preview && (
                    <img
                      className="publication-preview"
                      title="Aperçu LaTeX compilé"
                      alt="Figure rendue depuis le PDF LaTeX compilé"
                      src={"data:image/png;base64," + args.latex.preview}
                    />
                  )}
                  <button
                    disabled={busy || !args.latex.current || !latestLatex}
                    onClick={() => requestExport("pdf")}
                  >
                    PDF ↓
                  </button>
                </>
              )}
              <small>
                Le PDF compilé localement est la référence typographique.
              </small>
            </section>
          )}
        </div>
        {!disabled && (
          <nav aria-label="Navigation entre réponses">
            {review ? (
              <span>Vous pouvez modifier ce graphe avant de l’accepter.</span>
            ) : (
              <>
                <button
                  disabled={args.row === 0 || busy}
                  onClick={() => transmit(current.current, "previous")}
                >
                  ← Paire précédente
                </button>
                <span>
                  {args.row + 1} / {args.row_count}
                </span>
                <select
                  aria-label="État du codage"
                  value={doc.status}
                  onChange={(e) =>
                    mutate((d) => {
                      d.status = e.target.value as GraphDoc["status"];
                    })
                  }
                >
                  <option value="draft">Brouillon</option>
                  <option value="coded">Codé</option>
                  <option value="none">none</option>
                </select>
                <button
                  disabled={busy}
                  onClick={() => transmit(current.current, "validate")}
                  title="Valider et enregistrer ce codage"
                >
                  Enregistrer
                </button>
                <button
                  disabled={busy}
                  aria-pressed={enrichment}
                  onClick={() => setEnrichment(!enrichment)}
                >
                  Enrichissement
                </button>
                <button
                  disabled={busy || !previousDagSource}
                  title={
                    previousDagSource
                      ? `Copier ${previousDagSource.paths.length > 1 ? "les " + previousDagSource.paths.length + " DAGs" : "le DAG"} de la paire ${previousDagSource.order}, dernière paire précédente avec une figure. La figure actuelle sera remplacée ; cette action est annulable.`
                      : "Aucun DAG enregistré dans les questions précédentes de cet entretien."
                  }
                  onClick={() => {
                    if (previousDagSource)
                      transmit(current.current, "clone_previous", {
                        source_key: previousDagSource.key,
                        source_revision: previousDagSource.revision,
                      });
                  }}
                >
                  Reprendre le DAG précédent
                </button>
                <button
                  disabled={busy || !args.previous_sources?.length}
                  aria-haspopup="dialog"
                  aria-expanded={dagPicker}
                  onClick={() => {
                    setEnrichment(false);
                    setOptions(false);
                    setResumeError("");
                    setDagPicker(true);
                  }}
                >
                  Reprendre un autre DAG
                </button>
                <span className="toolbar-spacer" />
                <button
                  className="primary"
                  disabled={args.row >= args.row_count - 1 || busy}
                  onClick={() => transmit(current.current, "next")}
                >
                  Enregistrer et suivant →
                </button>
              </>
            )}
          </nav>
        )}
        {args.warnings?.length ? (
          <details className="validation-notes">
            <summary>{args.warnings.length} point(s) à vérifier</summary>
            {args.warnings.map((w) => (
              <p key={w}>{w}</p>
            ))}
          </details>
        ) : null}
        {dagPicker && !disabled && !review && (
          <DagPicker
            sources={args.previous_sources || []}
            doc={doc}
            busy={busy}
            error={
              resumeError ||
              (flightAction.current === "clone_selected" ? args.error : null)
            }
            close={() => setDagPicker(false)}
            submit={(extra) => {
              const snapshot = commitCurrent();
              if (!snapshot) {
                setResumeError(
                  "Terminez ou corrigez le texte en cours avant de reprendre un DAG.",
                );
                return;
              }
              setResumeError("");
              transmit(snapshot, "clone_selected", extra);
            }}
          />
        )}
        {enrichment && !disabled && !review && (
          <EnrichmentPanel
            args={args}
            doc={doc}
            busy={busy}
            pending={saving || inspectorDirty || !same(doc, args.document)}
            close={() => setEnrichment(false)}
            mutate={mutate}
            command={(action, extra) =>
              transmit(current.current, action, extra)
            }
          />
        )}
        {options && !disabled && (
          <section className="options-panel" aria-label="Options de codage">
            <div className="panel-heading">
              <h3>Options</h3>
              <button
                aria-label="Fermer les options"
                onClick={() => setOptions(false)}
              >
                ×
              </button>
            </div>
            {conflictRecovery.current && (
              <button onClick={() => download(conflictRecovery.current!)}>
                Exporter le brouillon récupéré
              </button>
            )}
            {!review && (
              <>
                {!!args.authors?.length && (
                  <label>
                    Codeur
                    <select
                      aria-label="Codeur actif"
                      value={args.author}
                      onChange={(e) =>
                        transmit(current.current, "switch_author", {
                          author: e.target.value,
                        })
                      }
                    >
                      {args.authors.map((a) => (
                        <option key={a}>{a}</option>
                      ))}
                    </select>
                  </label>
                )}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    setOptions(false);
                    transmit(current.current, "jump", {
                      row: Math.max(
                        0,
                        Math.min(args.row_count - 1, Number(jump) - 1),
                      ),
                    });
                  }}
                >
                  <label>
                    Aller à la paire
                    <input
                      aria-label="Numéro de réponse"
                      type="number"
                      min={1}
                      max={args.row_count}
                      value={jump}
                      onChange={(e) => setJump(e.target.value)}
                    />
                  </label>
                  <button>Ouvrir</button>
                </form>
                {!!args.clone_authors?.length && (
                  <label>
                    Reprendre un codeur
                    <select
                      aria-label="Reprendre un codeur"
                      value=""
                      onChange={(e) =>
                        transmit(current.current, "clone_coder", {
                          coder: e.target.value,
                        })
                      }
                    >
                      <option value="">Choisir…</option>
                      {args.clone_authors.map((c) => (
                        <option key={c}>{c}</option>
                      ))}
                    </select>
                  </label>
                )}
                {!!args.history?.length && (
                  <label>
                    Historique
                    <select
                      aria-label="Restaurer une révision"
                      value=""
                      onChange={(e) =>
                        transmit(current.current, "restore_revision", {
                          revision: Number(e.target.value),
                        })
                      }
                    >
                      <option value="">Restaurer une version…</option>
                      {args.history.map((h) => (
                        <option key={h.revision} value={h.revision}>
                          Version {h.revision} ·{" "}
                          {new Date(h.updated).toLocaleString()}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </>
            )}
            <details>
              <summary>Affichage et sélection</summary>
              <div className="button-grid">
                <button onClick={() => setGrid(!grid)} aria-pressed={grid}>
                  Grille
                </button>
                <button onClick={() => rf.fitView({ padding: 0.2 })}>
                  Recentrer
                </button>
                <button onClick={copySelection} disabled={!selection.length}>
                  Copier
                </button>
                <button
                  onClick={paste}
                  disabled={!args.clipboard_available && !clipboard.current}
                >
                  Coller
                </button>
              </div>
            </details>
            <details>
              <summary>DAGs distincts (;)</summary>
              <small>
                Les ensembles de blocs non reliés forment automatiquement des
                DAGs distincts. Les annotations de source | restent rattachées
                au DAG ou à l’objet choisi.
              </small>
              <select
                aria-label="DAG actif pour les sources"
                value={activePath}
                onChange={(e) => setActivePath(e.target.value)}
              >
                {doc.paths.map((p) => (
                  <option key={p.id} value={p.id}>
                    {dagLabel(doc, p.id)}
                  </option>
                ))}
              </select>
            </details>
            {!review && (
              <details>
                <summary>Fichiers et notation</summary>
                <div className="button-grid">
                  <button onClick={() => requestExport("json")}>
                    Exporter JSON
                  </button>
                  <label className="file-button">
                    Importer JSON
                    <input
                      aria-label="Importer un graphe JSON"
                      type="file"
                      accept=".json,application/json"
                      onChange={async (e) => {
                        const f = e.target.files?.[0];
                        if (!f) return;
                        if (f.size > 1000000) {
                          setMessage("Fichier supérieur à 1 Mo.");
                          return;
                        }
                        transmit(current.current, "import_json", {
                          import_json: await f.text(),
                        });
                        e.target.value = "";
                      }}
                    />
                  </label>
                </div>
                <textarea
                  aria-label="Notation à importer"
                  value={importText}
                  maxLength={100000}
                  onChange={(e) => setImportText(e.target.value)}
                  placeholder="climate_information --> worry"
                />
                <button
                  onClick={() =>
                    transmit(current.current, "import_sequence", {
                      import_text: importText,
                    })
                  }
                >
                  Importer la notation
                </button>
                <small>
                  La version actuelle et la notation originale restent dans
                  l’historique.
                </small>
              </details>
            )}
            <details>
              <summary>Aide</summary>
              <p>
                Tirez depuis un carré vers un bloc pour le relier, ou vers le
                vide pour créer un nouveau bloc. Les coins sont aussi des
                ancrages. Sélectionnez une flèche puis déplacez ses extrémités
                pour la reconnecter.
              </p>
              <p>
                Les symboles s’utilisent au clavier sur la toile ou dans la
                barre. topic(sous-thème)[portée] reste un seul bloc. Modifier le
                texte d’un bloc existant conserve son code canonique ; les
                réglages permettent de changer ce code explicitement.
              </p>
            </details>
          </section>
        )}
      </div>
      {!review && showProposal && pendingProposal && (
        <div
          className="proposal-backdrop"
          role="dialog"
          aria-modal="true"
          aria-label="Réviser la proposition IA"
          onKeyDown={(e) => {
            if (e.key === "Escape") setShowProposal(false);
            if (e.key === "Tab") {
              const controls = [
                ...e.currentTarget.querySelectorAll<HTMLElement>(
                  'button:not([disabled]), input, textarea, select, [tabindex="0"], summary',
                ),
              ].filter((el) => el.getClientRects().length > 0);
              const first = controls[0],
                last = controls.at(-1);
              if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last?.focus();
              } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first?.focus();
              }
            }
          }}
        >
          <section className="proposal-dialog" ref={proposalDialog}>
            <div className="panel-heading">
              <h3>Proposition IA · à relire</h3>
              <button
                aria-label="Fermer la proposition"
                onClick={() => setShowProposal(false)}
              >
                ×
              </button>
            </div>
            <p>{pendingProposal.summary}</p>
            {(message || args.ai_error) && (
              <div role="alert" className="proposal-error">
                {message || args.ai_error}
              </div>
            )}
            {!!pendingProposal.uncertainties.length && (
              <details open>
                <summary>Points d’incertitude</summary>
                {pendingProposal.uncertainties.map((v, i) => (
                  <p key={i}>{v}</p>
                ))}
              </details>
            )}
            <ReactFlowProvider>
              <Editor
                key={pendingProposal.id}
                args={{
                  ...args,
                  document: proposalDraft.current || pendingProposal.document,
                  document_key: "proposal_" + pendingProposal.id,
                  revision: 0,
                  ack: null,
                  error: null,
                  replace_token: "0",
                  title: "Proposition",
                  warnings: [],
                  ai_enabled: false,
                  read_only: false,
                }}
                onCommitReady={(fn) => {
                  proposalCommit.current = fn;
                }}
                onReviewChange={(d, valid) => {
                  proposalDraft.current = d;
                  setReviewValid(valid);
                }}
              />
            </ReactFlowProvider>
            <div className="proposal-actions">
              <details>
                <summary>Éléments d’appui · {pendingProposal.model}</summary>
                {pendingProposal.evidence.map((e, i) => (
                  <p key={i}>« {e.quote} »</p>
                ))}
              </details>
              <span className="toolbar-spacer" />
              <button
                disabled={busy}
                onClick={() =>
                  transmit(current.current, "ai_reject", {
                    proposal_id: pendingProposal.id,
                  })
                }
              >
                Refuser
              </button>
              <button
                className="primary"
                disabled={busy}
                onClick={() => {
                  const proposal = proposalCommit.current
                    ? proposalCommit.current()
                    : proposalDraft.current || pendingProposal.document;
                  if (!proposal) {
                    setMessage(
                      "Corrigez les champs signalés avant d’appliquer la proposition.",
                    );
                    return;
                  }
                  transmit(current.current, "ai_accept", {
                    proposal_id: pendingProposal.id,
                    proposal_document: proposal,
                  });
                }}
              >
                Appliquer la recommandation
              </button>
            </div>
          </section>
        </div>
      )}
    </Context.Provider>
  );
}

class EditorBoundary extends React.Component<
  { args: EditorArgs },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <div className="notice" role="alert">
          <p>
            L'éditeur a rencontré une erreur d'affichage. Votre dernière version
            enregistrée reste disponible.
          </p>
          <button
            onClick={() =>
              download(recoveryDocument || this.props.args.document)
            }
          >
            Exporter le brouillon JSON
          </button>
          <button onClick={() => window.location.reload()}>
            Recharger l'éditeur
          </button>
        </div>
      );
    return (
      <ReactFlowProvider>
        <Editor args={this.props.args} />
      </ReactFlowProvider>
    );
  }
}
const root = createRoot(document.getElementById("root")!);
root.render(<p className="loading">Chargement de l'éditeur…</p>);
Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, (event: Event) => {
  const data = (event as CustomEvent<RenderData>).detail;
  const args = data.args as EditorArgs;
  root.render(<EditorBoundary key={args.document_key} args={args} />);
});
Streamlit.setComponentReady();
Streamlit.setFrameHeight(860);
