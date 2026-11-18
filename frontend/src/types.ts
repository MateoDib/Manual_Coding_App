export type JunctionKind =
  "coexistence" | "addition" | "definition" | "priority";
export type Kind = "concept" | "source" | JunctionKind;
export const junctionKinds: JunctionKind[] = [
  "coexistence",
  "addition",
  "definition",
  "priority",
];
export const isJunction = (kind: string): kind is JunctionKind =>
  junctionKinds.includes(kind as JunctionKind);
export type Port =
  | "left"
  | "right"
  | "top"
  | "bottom"
  | "top-left"
  | "top-right"
  | "bottom-left"
  | "bottom-right";
export const ports: Port[] = [
  "left",
  "right",
  "top",
  "bottom",
  "top-left",
  "top-right",
  "bottom-left",
  "bottom-right",
];
export const portLabels: Record<Port, string> = {
  left: "Gauche",
  right: "Droite",
  top: "Haut",
  bottom: "Bas",
  "top-left": "Coin supérieur gauche",
  "top-right": "Coin supérieur droit",
  "bottom-left": "Coin inférieur gauche",
  "bottom-right": "Coin inférieur droit",
};
export type Point = { x: number; y: number };
export type Box = Point & { width: number; height: number; locked: boolean };
export type GraphNode = {
  id: string;
  kind: Kind;
  code: string;
  label: string;
  subtopics: string[];
  scopes: string[];
  attachment: { kind: "node" | "edge" | "path"; id: string } | null;
  dominant?: string | null;
};
export type GraphEdge = {
  id: string;
  kind:
    | "causal"
    | "definition"
    | "priority"
    | "membership"
    | "coexistence"
    | "addition"
    | "link";
  source: string;
  target: string;
  dominant: string | null;
};
export type EdgeView = {
  source_port: Port;
  target_port: Port;
  route: "straight" | "orthogonal" | "bezier";
  points: Point[];
  label_t: number;
  label_dx: number;
  label_dy: number;
  stroke?: "solid" | "dashed" | "dotted";
};
export type GraphPath = {
  id: string;
  label: string;
  node_ids: string[];
  edge_ids: string[];
};
export type SourceRef = { key: string; revision: number; path_id: string };
export type ObjectRecord = {
  origin: "created" | "copied" | "unknown";
  source: (SourceRef & { object_id: string }) | null;
  review: "unreviewed" | "expressed" | "not_discussed" | "withdrawn";
  quote: { text: string; start: number | null; end: number | null };
};
export type Tracking = {
  version: 3;
  response_digest: string;
  parents: {
    key: string;
    pair: string;
    revision: number;
    digest: string;
    semantic_digest: string;
    path_ids: string[];
    method: "copy" | "declared";
  }[];
  objects: Record<string, ObjectRecord>;
  dag_links: Record<string, SourceRef[]>;
  removals: Record<string, "withdrawn" | "correction" | "not_relevant">;
};
export type Enrichment = {
  counts: Record<
    string,
    {
      total: number;
      occurrences: number;
      new: number;
      inherited: number;
      expressed: number;
    }
  >;
  dag_count: number;
  history_complete: boolean;
  issues: string[];
  dags: {
    dag_id: string;
    dag_number: number;
    origin: string;
    comparison: string;
  }[];
  removed: { removal_key: string; label: string; reason: string }[];
};
export type PreviousSource = {
  key: string;
  order: number;
  revision: number;
  status: string;
  question: string;
  response: string;
  paths: { id: string; label: string; topics: string[]; preview: GraphDoc }[];
};
export type GraphDoc = {
  schema_version: 1;
  tracking?: Tracking;
  editor?: { node_text: Record<string, string> };
  status: "draft" | "coded" | "none";
  nodes: GraphNode[];
  edges: GraphEdge[];
  paths: GraphPath[];
  layout: { nodes: Record<string, Box>; edges: Record<string, EdgeView> };
  provenance: {
    original_text: string;
    import_warnings: string[];
    import_reviewed: boolean;
    parent?: string;
  };
};
export type EditorArgs = {
  document: GraphDoc;
  document_key: string;
  client_session?: string;
  revision: number;
  ack: string | null;
  error: string | null;
  replace_token: string;
  clipboard_available?: boolean;
  selection_after_replace?: string[];
  topics: string[];
  subtopics: Record<string, string[]>;
  scopes: string[];
  topic_labels?: Record<string, string[]>;
  ending_nodes: string[];
  row: number;
  row_count: number;
  read_only?: boolean;
  title: string;
  author?: string;
  authors?: string[];
  clone_authors?: string[];
  history?: { revision: number; updated: string; digest?: string }[];
  can_clone_previous?: boolean;
  previous_sources?: PreviousSource[];
  enrichment?: Enrichment;
  question?: string;
  response?: string;
  response_digest?: string;
  phase?: string;
  warnings?: string[];
  latex?: {
    digest: string;
    revision: number;
    document_key: string;
    tikz: string;
    standalone: string;
    styles: string;
    pdf: string | null;
    preview?: string | null;
    current: boolean;
  };
  ai_enabled?: boolean;
  ai_ready?: boolean;
  ai_model?: string;
  ai_error?: string | null;
  ai_decision?: { id: string; status: string; request_id: string } | null;
  ai_proposal?: {
    id: string;
    document: GraphDoc;
    summary: string;
    uncertainties: string[];
    evidence: { object_id: string; quote: string }[];
    model: string;
    status: string;
    base_digest: string;
  } | null;
};
export const clone = <T>(v: T): T => structuredClone(v);
export const uid = (prefix = "n") =>
  prefix + crypto.randomUUID().replaceAll("-", "");
export const defaultBox = (x = 0, y = 0, width = 168, height = 64): Box => ({
  x,
  y,
  width,
  height,
  locked: false,
});
export const defaultEdgeView = (): EdgeView => ({
  source_port: "right",
  target_port: "left",
  route: "straight",
  points: [],
  label_t: 0.5,
  label_dx: 0,
  label_dy: 0,
  stroke: "solid",
});
export const newNode = (code = "", kind: Kind = "concept"): GraphNode => ({
  id: uid(),
  kind,
  code,
  label: code.replaceAll("_", " "),
  subtopics: [],
  scopes: [],
  attachment: null,
});

export function junctionSymbol(doc: GraphDoc, node: GraphNode): string {
  if (node.kind !== "priority")
    return (
      (
        { coexistence: "&", addition: "+", definition: "=" } as Record<
          string,
          string
        >
      )[node.kind] || ""
    );
  const members = [
    ...new Set(
      doc.edges
        .filter((e) => e.kind === "membership" && e.target === node.id)
        .map((e) => e.source),
    ),
  ];
  if (
    !node.dominant ||
    !members.includes(node.dominant) ||
    members.length !== 2
  )
    return node.label === "<" ? "<" : ">";
  const other = members.find((id) => id !== node.dominant)!,
    a = doc.layout.nodes[node.dominant],
    b = doc.layout.nodes[other],
    dx = a.x + a.width / 2 - b.x - b.width / 2;
  return Math.abs(dx) > 1e-6
    ? dx < 0
      ? ">"
      : "<"
    : a.y + a.height / 2 <= b.y + b.height / 2
      ? ">"
      : "<";
}
