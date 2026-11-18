import { type GraphDoc, type GraphPath, type ObjectRecord } from "./types";

export function shortId(value: string) {
  let h = 2166136261;
  for (const c of value) h = Math.imul(h ^ c.charCodeAt(0), 16777619) >>> 0;
  return "d_" + h.toString(16).padStart(8, "0");
}
// Kept in parity with graph_tracking.normalize_paths. Connectivity is semantic;
// source annotations never merge two independent DAGs.
export const newRecord = (): ObjectRecord => ({
  origin: "created",
  source: null,
  review: "unreviewed",
  quote: { text: "", start: null, end: null },
});
export function normalizePaths(doc: GraphDoc, responseDigest = ""): GraphDoc {
  if (doc.tracking?.version !== 3)
    doc.tracking = {
      version: 3,
      response_digest: responseDigest,
      parents: [],
      objects: {},
      dag_links: {},
      removals: {},
    };

  const old = doc.paths;
  const vertices = new Set(
    doc.nodes.filter((n) => n.kind !== "source").map((n) => n.id),
  );
  const adjacent = new Map([...vertices].map((id) => [id, new Set<string>()]));
  for (const e of doc.edges)
    if (vertices.has(e.source) && vertices.has(e.target)) {
      adjacent.get(e.source)!.add(e.target);
      adjacent.get(e.target)!.add(e.source);
    }
  const unseen = new Set(vertices),
    components: Set<string>[] = [];
  while (unseen.size) {
    const stack = [[...unseen].sort()[0]],
      group = new Set<string>();
    while (stack.length) {
      const v = stack.pop()!;
      if (group.has(v)) continue;
      group.add(v);
      unseen.delete(v);
      stack.push(...[...adjacent.get(v)!].filter((id) => !group.has(id)));
    }
    components.push(group);
  }
  if (!components.length) components.push(new Set());
  const preferred = new Map(
    old.map((p) => {
      const scores = components.map((g) => [
        p.node_ids.filter((id) => g.has(id)).length,
        -Math.min(
          ...p.node_ids.map((id, i) => (g.has(id) ? i : 100000)),
          100000,
        ),
      ]);
      let best = 0;
      scores.forEach((score, i) => {
        if (
          score[0] > scores[best][0] ||
          (score[0] === scores[best][0] && score[1] > scores[best][1])
        )
          best = i;
      });
      return [p.id, best];
    }),
  );
  const occupied = new Set([...doc.nodes, ...doc.edges].map((v) => v.id)),
    used = new Set<string>();
  const paths: GraphPath[] = components.map((group, ci) => {
    const p = old.find(
      (p) =>
        !used.has(p.id) &&
        preferred.get(p.id) === ci &&
        (!group.size || p.node_ids.some((id) => group.has(id))),
    );
    let id = p?.id || shortId(group.size ? [...group].sort()[0] : "empty");
    const base = id;
    let index = 1;
    while (used.has(id) || (!p && occupied.has(id))) id = `${base}_${index++}`;
    used.add(id);
    return {
      id,
      label: p?.label || `DAG ${ci + 1}`,
      node_ids: [...group].sort(),
      edge_ids: doc.edges
        .filter((e) => group.has(e.source) && group.has(e.target))
        .map((e) => e.id),
    };
  });
  const order = new Map(old.map((p, i) => [p.id, i]));
  paths.sort(
    (a, b) =>
      (order.get(a.id) ?? old.length) - (order.get(b.id) ?? old.length) ||
      (a.id < b.id ? -1 : a.id > b.id ? 1 : 0),
  );
  const mapping = new Map(
    old.map((p) => [
      p.id,
      paths.some((q) => q.id === p.id)
        ? [p.id]
        : paths
            .filter((q) => p.node_ids.some((id) => q.node_ids.includes(id)))
            .map((q) => q.id),
    ]),
  );
  for (const n of doc.nodes)
    if (n.kind === "source") {
      const a = n.attachment;
      let targets: string[] = [];
      if (a?.kind === "path") {
        targets = mapping.get(a.id) || [];
        if (!targets.length && paths.length === 1) targets = [paths[0].id];
        if (targets.length === 1) a.id = targets[0];
        else {
          n.attachment = null;
          targets = [];
        }
      } else if (a)
        targets = paths
          .filter((p) =>
            (a.kind === "node" ? p.node_ids : p.edge_ids).includes(a.id),
          )
          .map((p) => p.id);
      for (const id of targets.length ? targets : [paths[0].id])
        paths.find((p) => p.id === id)!.node_ids.push(n.id);
    }
  doc.paths = paths;
  const tracking = doc.tracking;
  const known = new Set(Object.keys(tracking.objects));
  const previous = tracking.dag_links;
  tracking.dag_links = Object.fromEntries(
    paths.map((p) => {
      const refs = old
        .filter((q) =>
          q.node_ids.some((id) => known.has(id) && p.node_ids.includes(id)),
        )
        .flatMap((q) => previous[q.id] || []);
      const copied = [...p.node_ids, ...p.edge_ids]
        .map((id) => tracking.objects[id]?.source)
        .filter((r): r is NonNullable<typeof r> => !!r)
        .map((r) => ({ key: r.key, revision: r.revision, path_id: r.path_id }));
      let filtered = refs;
      if (copied.length) {
        const allowed = new Set(
          [
            ...copied,
            ...tracking.parents
              .filter((p) => p.method === "declared")
              .flatMap((p) =>
                p.path_ids.map((path_id) => ({
                  key: p.key,
                  revision: p.revision,
                  path_id,
                })),
              ),
          ].map((r) => `${r.key}:${r.revision}:${r.path_id}`),
        );
        filtered = [
          ...refs.filter((r) =>
            allowed.has(`${r.key}:${r.revision}:${r.path_id}`),
          ),
          ...copied,
        ];
      }
      const unique = new Map(
        filtered.map((r) => [`${r.key}:${r.revision}:${r.path_id}`, r]),
      );
      return [
        p.id,
        [...unique.entries()]
          .sort(
            ([, a], [, b]) =>
              (a.key < b.key ? -1 : a.key > b.key ? 1 : 0) ||
              a.revision - b.revision ||
              (a.path_id < b.path_id ? -1 : a.path_id > b.path_id ? 1 : 0),
          )
          .map(([, ref]) => ref),
      ];
    }),
  );
  tracking.objects = Object.fromEntries(
    [...doc.nodes, ...doc.edges]
      .map((obj) => [obj.id, tracking.objects[obj.id] || newRecord()])
      .sort(([a], [b]) =>
        String(a) < String(b) ? -1 : String(a) > String(b) ? 1 : 0,
      ),
  );
  return doc;
}

export function invalidateChangedEvidence(before: GraphDoc, after: GraphDoc) {
  const nodeSignature = (
    doc: GraphDoc,
    id: string,
    seen = new Set<string>(),
  ): unknown => {
    const n = doc.nodes.find((n) => n.id === id);
    if (!n) return null;
    if (seen.has(id)) return "cycle";
    const next = new Set([...seen, id]);
    let attachment: unknown = n.attachment;
    if (n.kind === "source" && n.attachment) {
      const a = n.attachment;
      if (a.kind === "node") attachment = nodeSignature(doc, a.id, next);
      if (a.kind === "edge") attachment = edgeSignature(doc, a.id, next);
      if (a.kind === "path") {
        const p = doc.paths.find((p) => p.id === a.id);
        attachment = p
          ? [
              p.node_ids
                .filter(
                  (id) => doc.nodes.find((n) => n.id === id)?.kind !== "source",
                )
                .map((id) => [id, nodeSignature(doc, id, next)]),
              p.edge_ids.map((id) => edgeSignature(doc, id, next)),
            ]
          : null;
      }
    }
    return [
      n.kind,
      n.code,
      [...new Set(n.subtopics)].sort(),
      [...new Set(n.scopes)].sort(),
      attachment,
      n.kind === "priority" ? (n.dominant ?? null) : null,
      ["addition", "coexistence", "definition", "priority"].includes(n.kind)
        ? doc.edges
            .filter((e) => e.kind === "membership" && e.target === id)
            .map((e) => e.source)
            .sort()
            .map((id) => nodeSignature(doc, id, next))
        : null,
    ];
  };
  const edgeSignature = (
    doc: GraphDoc,
    id: string,
    seen = new Set<string>(),
  ): unknown => {
    const e = doc.edges.find((e) => e.id === id);
    if (!e) return null;
    let endpoints = [e.source, e.target];
    if (["definition", "coexistence", "addition", "link"].includes(e.kind))
      endpoints.sort();
    if (e.kind === "priority")
      endpoints = [e.dominant!, e.dominant === e.source ? e.target : e.source];
    return [
      e.kind,
      ...endpoints,
      endpoints.map((id) => nodeSignature(doc, id, seen)),
    ];
  };
  const signature = (doc: GraphDoc, id: string) =>
    doc.edges.some((e) => e.id === id)
      ? edgeSignature(doc, id)
      : nodeSignature(doc, id);
  const beforeIds = new Set(
    [...before.nodes, ...before.edges].map((o) => o.id),
  );
  const afterIds = new Set([...after.nodes, ...after.edges].map((o) => o.id));
  let changed =
    beforeIds.size !== afterIds.size ||
    [...beforeIds].some((id) => !afterIds.has(id));
  for (const obj of [...after.nodes, ...after.edges]) {
    const meta = after.tracking?.objects[obj.id];
    if (
      meta &&
      before.tracking?.objects[obj.id] &&
      JSON.stringify(signature(before, obj.id)) !==
        JSON.stringify(signature(after, obj.id))
    ) {
      meta.review = "unreviewed";
      changed = true;
    }
  }
  return changed;
}
