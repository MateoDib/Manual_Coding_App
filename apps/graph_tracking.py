"""V3 provenance and connected-DAG boundaries, independent of figure geometry."""

from __future__ import annotations

import re
from copy import deepcopy

from graph_model import ID, GraphError

HASH = re.compile(r"[0-9a-f]{64}\Z")
FEATURE = re.compile(r"f_[0-9a-f]{64}\Z")
REASONS = {"withdrawn", "correction", "not_relevant"}


def _reference(ref, object_ref=False):
    keys = {"key", "revision", "path_id"} | ({"object_id"} if object_ref else set())
    if (
        not isinstance(ref, dict)
        or set(ref) != keys
        or not isinstance(ref["key"], str)
        or not HASH.fullmatch(ref["key"])
    ):
        raise GraphError("Référence d’origine invalide.")
    if type(ref["revision"]) is not int or ref["revision"] < 1:
        raise GraphError("Révision d’origine invalide.")
    for name in keys - {"key", "revision"}:
        if not isinstance(ref[name], str) or not ID.fullmatch(ref[name]):
            raise GraphError("Objet d’origine invalide.")


def new_record(origin="created", source=None):
    return {
        "origin": origin,
        "source": source,
        "review": "unreviewed",
        "quote": {"text": "", "start": None, "end": None},
    }


def empty_tracking(response_digest=""):
    return {
        "version": 3,
        "response_digest": response_digest,
        "parents": [],
        "objects": {},
        "dag_links": {},
        "removals": {},
    }


def validate_tracking(value, paths, objects=None):
    if (
        not isinstance(value, dict)
        or set(value)
        != {"version", "response_digest", "parents", "objects", "dag_links", "removals"}
        or value["version"] != 3
    ):
        raise GraphError("Ce document nécessite le suivi scientifique V3.")
    if not isinstance(value["response_digest"], str) or (
        value["response_digest"] and not HASH.fullmatch(value["response_digest"])
    ):
        raise GraphError("Version de la réponse invalide.")
    if not isinstance(value["parents"], list) or len(value["parents"]) > 150:
        raise GraphError("Trop de DAGs parents.")
    for p in value["parents"]:
        if not isinstance(p, dict) or set(p) != {
            "key",
            "pair",
            "revision",
            "digest",
            "semantic_digest",
            "path_ids",
            "method",
        }:
            raise GraphError("Référence de reprise invalide.")
        if p["method"] not in {"copy", "declared"}:
            raise GraphError("Méthode de reprise invalide.")
        if not all(
            isinstance(p[k], str) and HASH.fullmatch(p[k])
            for k in ["key", "digest", "semantic_digest"]
        ):
            raise GraphError("Empreinte de reprise invalide.")
        if (
            not isinstance(p["pair"], str)
            or not 0 < len(p["pair"]) <= 300
            or any(ord(c) < 32 for c in p["pair"])
        ):
            raise GraphError("Paire d’origine invalide.")
        if type(p["revision"]) is not int or p["revision"] < 1:
            raise GraphError("Révision d’origine invalide.")
        if (
            not isinstance(p["path_ids"], list)
            or not p["path_ids"]
            or len(p["path_ids"]) > 150
            or any(not isinstance(v, str) or not ID.fullmatch(v) for v in p["path_ids"])
        ):
            raise GraphError("DAGs d’origine invalides.")
    records = value["objects"]
    if (
        not isinstance(records, dict)
        or len(records) > 650
        or (objects is not None and set(records) != set(objects))
    ):
        raise GraphError(
            "Les occurrences et leur suivi ne correspondent pas au graphe."
        )
    for oid, record in records.items():
        if (
            not isinstance(oid, str)
            or not ID.fullmatch(oid)
            or not isinstance(record, dict)
            or set(record) != {"origin", "source", "review", "quote"}
        ):
            raise GraphError("Suivi d’une occurrence invalide.")
        if record["origin"] not in {"created", "copied", "unknown"} or record[
            "review"
        ] not in {"unreviewed", "expressed", "not_discussed", "withdrawn"}:
            raise GraphError("Origine ou attribution d’une occurrence invalide.")
        if record["source"] is not None:
            _reference(record["source"], True)
        if (record["origin"] == "copied") != (record["source"] is not None):
            raise GraphError("Une copie doit conserver sa référence exacte.")
        quote = record["quote"]
        if (
            not isinstance(quote, dict)
            or set(quote) != {"text", "start", "end"}
            or not isinstance(quote["text"], str)
            or len(quote["text"]) > 5000
            or any(ord(c) < 32 and c not in "\n\t\r" for c in quote["text"])
        ):
            raise GraphError("Citation invalide ou trop longue.")
        start, end = quote["start"], quote["end"]
        if not (start is None and end is None) and not (
            type(start) is int and type(end) is int and 0 <= start < end
        ):
            raise GraphError("Position de citation invalide.")
    links = value["dag_links"]
    if not isinstance(links, dict) or not set(links) <= paths:
        raise GraphError("Filiation des DAGs invalide.")
    for refs in links.values():
        if not isinstance(refs, list) or len(refs) > 150:
            raise GraphError("Trop d’origines pour un DAG.")
        for ref in refs:
            _reference(ref)
    if (
        not isinstance(value["removals"], dict)
        or len(value["removals"]) > 1000
        or any(
            not isinstance(k, str)
            or not re.fullmatch(r"r_[0-9a-f]{64}", k)
            or v not in REASONS
            for k, v in value["removals"].items()
        )
    ):
        raise GraphError("Motif de retrait invalide.")


def short_id(value):
    h = 2166136261
    for c in value:
        h = ((h ^ ord(c)) * 16777619) & 0xFFFFFFFF
    return "d_" + format(h, "08x")


def normalize_paths(document):
    """Each connected non-source component is a DAG; sources never join DAGs."""
    doc = deepcopy(document)
    old = doc["paths"]
    nodes = {n["id"]: n for n in doc["nodes"]}
    vertices = {k for k, n in nodes.items() if n["kind"] != "source"}
    adjacency = {k: set() for k in vertices}
    for e in doc["edges"]:
        if e["source"] in vertices and e["target"] in vertices:
            adjacency[e["source"]].add(e["target"])
            adjacency[e["target"]].add(e["source"])
    components = []
    unseen = set(vertices)
    while unseen:
        start = min(unseen)
        stack = [start]
        group = set()
        while stack:
            v = stack.pop()
            if v in group:
                continue
            group.add(v)
            unseen.discard(v)
            stack.extend(adjacency[v] - group)
        components.append(group)
    if not components:
        components = [set()]
    preferred = {}
    for p in old:
        scores = [
            (
                len(group & set(p["node_ids"])),
                -min(
                    (i for i, v in enumerate(p["node_ids"]) if v in group),
                    default=100000,
                ),
            )
            for group in components
        ]
        preferred[p["id"]] = max(range(len(components)), key=lambda i: scores[i])
    occupied = set(nodes) | {e["id"] for e in doc["edges"]}
    used = set()
    paths = []
    for component_index, group in enumerate(components):
        candidates = [
            p
            for p in old
            if p["id"] not in used
            and preferred[p["id"]] == component_index
            and (group & set(p["node_ids"]) or not group)
        ]
        candidate = candidates[0] if candidates else None
        pid = (
            candidate["id"] if candidate else short_id(min(group) if group else "empty")
        )
        base = pid
        index = 1
        while pid in used or (pid in occupied and not candidate):
            pid = f"{base}_{index}"
            index += 1
        used.add(pid)
        paths.append(
            {
                "id": pid,
                "label": candidate["label"] if candidate else f"DAG {len(paths) + 1}",
                "node_ids": sorted(group),
                "edge_ids": [
                    e["id"]
                    for e in doc["edges"]
                    if e["source"] in group and e["target"] in group
                ],
            }
        )
    old_order = {p["id"]: i for i, p in enumerate(old)}
    paths.sort(key=lambda p: (old_order.get(p["id"], len(old)), p["id"]))
    mapping = {
        p["id"]: (
            [p["id"]]
            if any(q["id"] == p["id"] for q in paths)
            else [q["id"] for q in paths if set(p["node_ids"]) & set(q["node_ids"])]
        )
        for p in old
    }
    by_path = {p["id"]: p for p in paths}
    for n in nodes.values():
        if n["kind"] != "source":
            continue
        a = n["attachment"]
        targets = []
        if a:
            if a["kind"] == "path":
                targets = mapping.get(a["id"], [])
                if not targets and len(paths) == 1:
                    targets = [paths[0]["id"]]
                if len(targets) == 1:
                    a["id"] = targets[0]
                else:
                    n["attachment"] = None
                    targets = []
            else:
                key = "node_ids" if a["kind"] == "node" else "edge_ids"
                targets = [p["id"] for p in paths if a["id"] in p[key]]
        for pid in targets or [paths[0]["id"]]:
            by_path[pid]["node_ids"].append(n["id"])
    doc["paths"] = paths
    if "tracking" in doc:
        tracking = doc["tracking"]
        known = set(tracking["objects"])
        old_links = tracking["dag_links"]
        new_links = {}
        for path in paths:
            refs = []
            for previous in old:
                # A freshly typed disconnected block has been temporarily added
                # to the active path by the editor. It must not inherit that path.
                if set(previous["node_ids"]) & set(path["node_ids"]) & known:
                    refs.extend(old_links.get(previous["id"], []))
            copied = []
            for oid in path["node_ids"] + path["edge_ids"]:
                source = tracking["objects"].get(oid, {}).get("source")
                if source:
                    copied.append(
                        {k: source[k] for k in ["key", "revision", "path_id"]}
                    )
            if copied:
                direct = {(r["key"], r["revision"], r["path_id"]) for r in copied}
                declared = {
                    (p["key"], p["revision"], pid)
                    for p in tracking["parents"]
                    if p["method"] == "declared"
                    for pid in p["path_ids"]
                }
                refs = [
                    r
                    for r in refs
                    if (r["key"], r["revision"], r["path_id"]) in direct | declared
                ]
                refs.extend(copied)
            unique = {(r["key"], r["revision"], r["path_id"]): r for r in refs}
            new_links[path["id"]] = [unique[k] for k in sorted(unique)]
        tracking["dag_links"] = new_links
        ids = set(nodes) | {e["id"] for e in doc["edges"]}
        tracking["objects"] = {
            oid: tracking["objects"].get(oid, new_record()) for oid in sorted(ids)
        }

    return doc


def prepare(document, key="", legacy=False, response_digest=None, origin="created"):
    doc = deepcopy(document)
    if doc.get("tracking", {}).get("version") != 3:
        doc["tracking"] = empty_tracking(response_digest or "")
        doc["tracking"]["objects"] = {
            obj["id"]: new_record("unknown" if legacy else origin)
            for obj in doc["nodes"] + doc["edges"]
        }
    if response_digest is not None:
        doc["tracking"]["response_digest"] = response_digest
    return normalize_paths(doc)


def subset(document, path_ids):
    doc = deepcopy(document)
    selected = [p for p in doc["paths"] if p["id"] in path_ids]
    if not selected:
        raise GraphError("Choisissez au moins un DAG à reprendre.")
    ids = {v for p in selected for v in p["node_ids"]}
    edges = {v for p in selected for v in p["edge_ids"]}
    doc["nodes"] = [n for n in doc["nodes"] if n["id"] in ids]
    doc["edges"] = [e for e in doc["edges"] if e["id"] in edges]
    doc["paths"] = selected
    doc["layout"]["nodes"] = {
        k: v for k, v in doc["layout"]["nodes"].items() if k in ids
    }
    doc["layout"]["edges"] = {
        k: v for k, v in doc["layout"]["edges"].items() if k in edges
    }
    for n in doc["nodes"]:
        a = n["attachment"]
        if a and a["id"] not in ids | edges | set(path_ids):
            n["attachment"] = None
    if "editor" in doc:
        doc["editor"]["node_text"] = {
            k: v for k, v in doc["editor"]["node_text"].items() if k in ids
        }
    if "tracking" in doc:
        tracking = doc["tracking"]
        tracking["objects"] = {
            k: v for k, v in tracking["objects"].items() if k in ids | edges
        }
        tracking["dag_links"] = {
            k: v for k, v in tracking["dag_links"].items() if k in path_ids
        }

    return doc


def continue_from(current, source, path_ids, *, append=False, origin_only=False):
    """Freeze source occurrences; evidence is never copied to a new response."""
    import uuid

    from graph_metrics import semantic_digest
    from graph_model import document_digest

    original = prepare(source["document"], source["key"])
    chosen = subset(original, path_ids)
    parent = {
        "key": source["key"],
        "pair": source["pair"],
        "revision": source["revision"],
        "digest": document_digest(source["document"]),
        "semantic_digest": semantic_digest(chosen),
        "path_ids": list(path_ids),
        "method": "declared" if origin_only else "copy",
    }
    if origin_only:
        doc = prepare(current)
        doc["tracking"]["parents"] = [parent]
        refs = [
            {"key": source["key"], "revision": source["revision"], "path_id": pid}
            for pid in path_ids
        ]
        # An origin-only declaration must be tied to a structurally matching DAG.
        from graph_comparison import structural_relation

        for path in doc["paths"]:
            matches = [
                ref
                for ref in refs
                if structural_relation(
                    subset(doc, [path["id"]]), subset(original, [ref["path_id"]])
                )
                in {"identical", "subgraph"}
            ]
            if matches:
                doc["tracking"]["dag_links"][path["id"]] = matches
        if not any(doc["tracking"]["dag_links"].values()):
            raise GraphError(
                "Aucun DAG actuel ne correspond aux origines choisies. Reprenez une copie ou choisissez une origine correspondante."
            )
        return doc
    doc = (
        prepare(current)
        if append
        else prepare(
            __import__("graph_model").empty_document(),
            response_digest=current.get("tracking", {}).get("response_digest", ""),
        )
    )
    ids = {
        obj["id"]: "v" + uuid.uuid4().hex
        for obj in chosen["nodes"] + chosen["edges"] + chosen["paths"]
    }
    offset = (
        (
            max(
                (v["x"] + v["width"] for v in doc["layout"]["nodes"].values()),
                default=-160,
            )
            + 160
            - min((v["x"] for v in chosen["layout"]["nodes"].values()), default=0)
        )
        if append
        else 0
    )
    owners = {
        oid: p["id"] for p in chosen["paths"] for oid in p["node_ids"] + p["edge_ids"]
    }
    for kind in ["nodes", "edges"]:
        for obj in chosen[kind]:
            old = obj["id"]
            obj["id"] = ids[old]
            if kind == "nodes":
                if obj["attachment"]:
                    obj["attachment"]["id"] = ids[obj["attachment"]["id"]]
                if obj.get("dominant"):
                    obj["dominant"] = ids[obj["dominant"]]
            else:
                obj.update(
                    source=ids[obj["source"]],
                    target=ids[obj["target"]],
                    dominant=ids[obj["dominant"]] if obj["dominant"] else None,
                )
            doc["tracking"]["objects"][obj["id"]] = new_record(
                "copied",
                {
                    "key": source["key"],
                    "revision": source["revision"],
                    "path_id": owners[old],
                    "object_id": old,
                },
            )
        for old, view in chosen["layout"][kind].items():
            view = deepcopy(view)
            if kind == "nodes":
                view["x"] += offset
            else:
                for point in view["points"]:
                    point["x"] += offset
            doc["layout"][kind][ids[old]] = view
        doc[kind].extend(chosen[kind])
    for path in chosen["paths"]:
        old = path["id"]
        path.update(
            id=ids[old],
            node_ids=[ids[i] for i in path["node_ids"]],
            edge_ids=[ids[i] for i in path["edge_ids"]],
        )
        doc["paths"].append(path)
        doc["tracking"]["dag_links"][path["id"]] = [
            {"key": source["key"], "revision": source["revision"], "path_id": old}
        ]
    if chosen.get("editor"):
        doc.setdefault("editor", {"node_text": {}})["node_text"].update(
            {ids[k]: v for k, v in chosen["editor"]["node_text"].items()}
        )
    prior = next(
        (
            p
            for p in doc["tracking"]["parents"]
            if p["key"] == parent["key"] and p["revision"] == parent["revision"]
        ),
        None,
    )
    if prior:
        combined = sorted(set(prior["path_ids"]) | set(path_ids))
        prior.update(
            path_ids=combined,
            semantic_digest=semantic_digest(subset(original, combined)),
        )
    else:
        doc["tracking"]["parents"].append(parent)
    doc["status"] = "draft"
    doc["provenance"]["parent"] = "previous:" + source["pair"]
    return prepare(doc)


def continue_many(current, selections, *, append=False, origin_only=False):
    if not selections:
        raise GraphError("Choisissez au moins un DAG à reprendre.")
    if origin_only:
        doc = prepare(current)
        parents = []
        links = {p["id"]: [] for p in doc["paths"]}
        for source, paths in selections:
            linked = continue_from(current, source, paths, origin_only=True)
            parents.extend(linked["tracking"]["parents"])
            for pid, refs in linked["tracking"]["dag_links"].items():
                links[pid].extend(refs)
        doc["tracking"].update(parents=parents, dag_links=links)
        return doc
    doc = current
    for i, (source, paths) in enumerate(selections):
        doc = continue_from(doc, source, paths, append=append or i > 0)
    return doc
