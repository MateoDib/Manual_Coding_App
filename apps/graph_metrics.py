"""Reproducible longitudinal metrics, derived only from current graph revisions.

No geometry, display spelling, participant metadata or model output enters a
semantic feature key. Group consequences remain group consequences.
"""

from __future__ import annotations

import hashlib
import io
import json
import zipfile
from collections import defaultdict

import pandas as pd
from graph_model import graph_warnings
from graph_relations import JUNCTION_KINDS
from graph_tracking import prepare, subset

KINDS = (
    "topic",
    "subtopic",
    "scope",
    "source",
    "source_attachment",
    "group",
    "relation",
)
SYMMETRIC = {"definition", "coexistence", "addition", "link"}


def packed(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def feature_key(value):
    return "f_" + hashlib.sha256(packed(value).encode()).hexdigest()


def features(document):
    """Unique semantic features plus occurrence IDs and owning DAGs."""
    doc = prepare(document)
    nodes = {n["id"]: n for n in doc["nodes"]}
    owners = defaultdict(set)
    for p in doc["paths"]:
        for oid in p["node_ids"] + p["edge_ids"]:
            owners[oid].add(p["id"])

    binary_groups = {}
    for n in doc["nodes"]:
        if (
            n["kind"] not in JUNCTION_KINDS
            or n["code"]
            or n["subtopics"]
            or n["scopes"]
        ):
            continue
        related = [e for e in doc["edges"] if n["id"] in (e["source"], e["target"])]
        members = [
            e for e in related if e["kind"] == "membership" and e["target"] == n["id"]
        ]
        ids = {n["id"], *[e["id"] for e in related]}
        attached = any(
            node["attachment"] and node["attachment"]["id"] in ids
            for node in doc["nodes"]
        )
        if (
            len(related) == len(members) == 2
            and len({e["source"] for e in members}) == 2
            and not attached
            and (
                n["kind"] != "priority"
                or n.get("dominant") in {e["source"] for e in members}
            )
        ):
            binary_groups[n["id"]] = members
    endpoint_cache, group_values = {}, {}

    def endpoint(nid, visited=frozenset(), qualified=True):
        n = nodes[nid]
        if n["kind"] == "concept":
            value = {"type": "topic", "code": n["code"]}
            if qualified:
                value.update(
                    subtopics=sorted(set(n["subtopics"])),
                    scopes=sorted(set(n["scopes"])),
                )
            return value
        if nid in visited:
            return {"type": "invalid_group_cycle"}
        cache_key = (nid, qualified)
        if cache_key not in endpoint_cache:
            members = [
                endpoint(e["source"], visited | {nid}, qualified)
                for e in doc["edges"]
                if e["target"] == nid and e["kind"] == "membership"
            ]
            value = {
                "type": n["kind"],
                "members": sorted({packed(m): m for m in members}.values(), key=packed),
            }
            if n["kind"] == "priority":
                winner = n.get("dominant")
                value["dominant"] = (
                    endpoint(winner, visited | {nid}, qualified)
                    if winner in nodes
                    else None
                )
            group_values[cache_key] = value
            # Nested groups reference their own definition instead of expanding
            # exponentially. Their full direct membership is a separate feature.
            endpoint_cache[cache_key] = {
                "type": n["kind"],
                "group_key": feature_key({"kind": "group", **value}),
            }
            if n["kind"] == "priority":
                endpoint_cache[cache_key]["dominant"] = value["dominant"]
        return endpoint_cache[cache_key]

    result = {}

    def add(kind, value, oid, label=None, references=None, **extra):
        payload = {"kind": kind, **value}
        key = feature_key(payload)
        if key not in result:
            result[key] = {
                "key": key,
                "kind": kind,
                "value": payload,
                "label": label or packed(value),
                "object_ids": [],
                "path_ids": [],
                "occurrences": 0,
                "references": {},
                **extra,
            }
        row = result[key]
        if references is not None:
            row["references"][oid] = references
        row["occurrences"] += 1
        row["object_ids"].append(oid)
        row["path_ids"] = sorted(set(row["path_ids"]) | owners[oid])
        return key

    for n in doc["nodes"]:
        if n["kind"] == "concept" and n["code"]:
            add("topic", {"code": n["code"]}, n["id"], n["code"])
            for s in set(n["subtopics"]):
                add(
                    "subtopic",
                    {"topic": n["code"], "text": s},
                    n["id"],
                    f"{n['code']} ({s})",
                )
            for s in set(n["scopes"]):
                add(
                    "scope",
                    {"topic": n["code"], "text": s},
                    n["id"],
                    f"{n['code']} [{s}]",
                )
        elif n["kind"] in JUNCTION_KINDS and n["id"] not in binary_groups:
            endpoint(n["id"])
            endpoint(n["id"], qualified=False)
            value = group_values[(n["id"], True)]
            topic_value = {"kind": "group", **group_values[(n["id"], False)]}
            add(
                "group",
                value,
                n["id"],
                {
                    "coexistence": "&",
                    "addition": "+",
                    "definition": "=",
                    "priority": ">",
                }[n["kind"]]
                + " "
                + packed(value["members"]),
                topic_group_key=feature_key(topic_value),
                topic_group_value=topic_value,
            )
        elif n["kind"] == "source" and n["code"]:
            add("source", {"code": n["code"]}, n["id"], "| " + n["code"])

    def relation(e, qualified=True):
        a, b = (
            endpoint(e["source"], qualified=qualified),
            endpoint(e["target"], qualified=qualified),
        )
        if e["kind"] in SYMMETRIC and packed(a) > packed(b):
            a, b = b, a
        if e["kind"] == "priority" and e["dominant"] == e["target"]:
            a, b = b, a
        return {
            "relation": e["kind"],
            "source": a,
            "target": b,
            "directed": e["kind"] not in SYMMETRIC,
        }

    def add_relation(e, oid):
        value = relation(e)
        a, b = e["source"], e["target"]
        if e["kind"] in SYMMETRIC and packed(endpoint(a)) > packed(endpoint(b)):
            a, b = b, a
        if e["kind"] == "priority" and e["dominant"] == e["target"]:
            a, b = b, a
        add(
            "relation",
            value,
            oid,
            references={"source_id": a, "target_id": b},
            topic_relation_key=feature_key({"kind": "relation", **relation(e, False)}),
            topic_value={"kind": "relation", **relation(e, False)},
        )

    for e in doc["edges"]:
        if e["kind"] == "membership" and e["target"] in binary_groups:
            continue
        add_relation(e, e["id"])
    for gid, members in binary_groups.items():
        add_relation(
            {
                "kind": nodes[gid]["kind"],
                "source": members[0]["source"],
                "target": members[1]["source"],
                "dominant": nodes[gid].get("dominant")
                if nodes[gid]["kind"] == "priority"
                else None,
            },
            gid,
        )

    for n in doc["nodes"]:
        a = n["attachment"]
        if n["kind"] != "source" or not n["code"] or not a:
            continue
        if a["kind"] == "node":
            target = endpoint(a["id"])
        elif a["kind"] == "edge":
            target = relation(next(e for e in doc["edges"] if e["id"] == a["id"]))
        else:
            p = next(p for p in doc["paths"] if p["id"] == a["id"])
            target = {
                "type": "dag",
                "nodes": sorted(
                    [
                        endpoint(i)
                        for i in p["node_ids"]
                        if nodes[i]["kind"] != "source"
                    ],
                    key=packed,
                ),
                "relations": sorted(
                    [relation(e) for e in doc["edges"] if e["id"] in p["edge_ids"]],
                    key=packed,
                ),
            }
        add(
            "source_attachment",
            {"source": n["code"], "target_kind": a["kind"], "target": target},
            n["id"],
        )
    return result


def semantic_digest(document):
    # Identity-sensitive topology fingerprint for a frozen source revision.
    # Equality between drawings is ALWAYS checked by typed graph isomorphism.
    doc = prepare(document)
    value = {
        "nodes": sorted(doc["nodes"], key=lambda n: n["id"]),
        "edges": sorted(doc["edges"], key=lambda e: e["id"]),
        "paths": sorted(doc["paths"], key=lambda p: p["id"]),
    }
    for node in value["nodes"]:
        node.pop("label", None)
        if node.get("dominant") is None:
            node.pop("dominant", None)
    return hashlib.sha256(packed(value).encode()).hexdigest()


# Scalar, named columns are the analysis interface. JSON is reserved for the
# complete semantic endpoints of groups and immutable before/after values.
PAIR_COLUMNS = [
    "participant",
    "interview_id",
    "pair_id",
    "pair_order",
    "revision",
    "status",
    "coding_valid",
    "history_complete",
    "lineage_valid",
    "n_dags",
    "n_topics",
    "n_occurrences",
    "n_new_topics",
    "n_subtopics",
    "n_new_subtopics",
    "n_scopes",
    "n_new_scopes",
    "n_relations",
    "n_new_relations",
    "n_expressed_topics",
    "n_expressed_relations",
    "issues",
]
DAG_COLUMNS = [
    "pair_id",
    "dag_id",
    "dag_number",
    "origin",
    "comparison",
    "matched_pair",
    "matched_dag",
    "terminal",
    "n_topics",
    "n_relations",
]
PARENT_COLUMNS = [
    "pair_id",
    "dag_id",
    "parent_pair",
    "parent_author",
    "parent_dag",
    "parent_revision",
    "basis",
]
OCCURRENCE_COLUMNS = [
    "participant",
    "interview_id",
    "pair_id",
    "pair_order",
    "revision",
    "dag_id",
    "object_id",
    "kind",
    "code",
    "subtopic",
    "scope",
    "feature_key",
    "value_json",
    "origin",
    "source_pair",
    "source_author",
    "source_dag",
    "source_revision",
    "source_object",
    "source_change",
    "seen_before",
    "history_complete",
    "review",
    "expressed",
    "quote",
    "quote_start",
    "quote_end",
    "relation_type",
    "source_id",
    "target_id",
    "source_code",
    "target_code",
    "topic_relation_key",
    "topic_value_json",
]
CHANGE_COLUMNS = [
    "pair_id",
    "dag_id",
    "source_pair",
    "source_author",
    "source_dag",
    "source_revision",
    "source_object",
    "object_id",
    "kind",
    "change",
    "reason",
    "before_json",
    "after_json",
    "removal_key",
]
FREQUENCY_COLUMNS = [
    "level",
    "relation_key",
    "relation_type",
    "source_code",
    "target_code",
    "value_json",
    "n_participants",
    "n_complete_participants",
    "n_final_participants",
    "n_expressed_pairs",
    "n_snapshot_pairs",
]
TABLE_COLUMNS = {
    "pairs": PAIR_COLUMNS,
    "dags": DAG_COLUMNS,
    "dag_parents": PARENT_COLUMNS,
    "occurrences": OCCURRENCE_COLUMNS,
    "changes": CHANGE_COLUMNS,
    "frequencies": FREQUENCY_COLUMNS,
}


def _parent_same(doc, source, oid, record):
    oldid = record["source"]["object_id"]
    current = next((o for o in doc["nodes"] + doc["edges"] if o["id"] == oid), None)
    old = next((o for o in source["nodes"] + source["edges"] if o["id"] == oldid), None)
    if current is None or old is None:
        return False
    if "source" not in current:

        def attributes(node):
            value = {
                k: v
                for k, v in node.items()
                if k not in {"id", "label", "attachment", "dominant"}
            }
            value["subtopics"] = sorted(set(value["subtopics"]))
            value["scopes"] = sorted(set(value["scopes"]))
            return value

        same = attributes(current) == attributes(old)
        if same and current["kind"] in JUNCTION_KINDS:
            members = [
                e["source"]
                for e in doc["edges"]
                if e["target"] == oid and e["kind"] == "membership"
            ]
            old_members = {
                e["source"]
                for e in source["edges"]
                if e["target"] == oldid and e["kind"] == "membership"
            }
            mapped = []
            for member in members:
                ref = doc["tracking"]["objects"][member]["source"]
                if not ref or any(
                    ref[k] != record["source"][k] for k in ["key", "revision"]
                ):
                    return False
                mapped.append(ref["object_id"])
            same = set(mapped) == old_members
        if same and current["kind"] == "priority":
            winner = current.get("dominant")
            ref = doc["tracking"]["objects"].get(winner, {}).get("source")
            same = bool(
                ref
                and ref["key"] == record["source"]["key"]
                and ref["revision"] == record["source"]["revision"]
                and ref["object_id"] == old.get("dominant")
            )
        return same
    if current["kind"] != old["kind"]:
        return False
    mapped = []
    for endpoint in ["source", "target"]:
        target = doc["tracking"]["objects"][current[endpoint]].get("source")
        if not target or any(
            target[k] != record["source"][k] for k in ["key", "revision"]
        ):
            return False
        mapped.append(target["object_id"])
    if current["kind"] in SYMMETRIC or current["kind"] == "priority":
        if set(mapped) != {old["source"], old["target"]}:
            return False
    elif mapped != [old["source"], old["target"]]:
        return False
    if current["kind"] == "priority":
        dominant = doc["tracking"]["objects"][current["dominant"]].get("source")
        if not dominant or dominant["object_id"] != old["dominant"]:
            return False

    return True


def _issues(doc):
    return [
        w
        for w in graph_warnings(doc)
        if not (doc["status"] == "none" and w.startswith("Le statut « aucun ajout »"))
    ]


def analyze(canonical, records, store=None):
    import time

    from graph_comparison import same_graph, structural_relation
    from graph_evidence import quote_valid, source_token

    by_pair = {r["pair"]: r for r in records if r}
    lookup = {r["key"]: r for r in records if r}
    history_cache = {}
    features_cache = {}

    def historical(key, revision):
        cache = (key, revision)
        if cache not in history_cache:
            if store:
                history_cache[cache] = store.historical_document(key, revision)
            else:
                row = lookup.get(key)
                if not row or row["revision"] != revision:
                    raise ValueError("Source revision unavailable")
                history_cache[cache] = row["document"]
        return history_cache[cache]

    tables = {name: [] for name in TABLE_COLUMNS}
    details = {}
    seen_by = {}
    history_ok = {}
    previous_dags = {}
    final_tips = {}
    deadline = time.monotonic() + 3
    grouping = ["PID"] + (["interview_id"] if "interview_id" in canonical else [])
    ordered = canonical.sort_values(grouping + ["pair_order_interview"], kind="stable")
    for _, row in ordered.iterrows():
        pair = str(row.pair_id_interview)
        person = str(row.PID)
        interview = str(row.get("interview_id", ""))
        group = (person, interview)
        seen = seen_by.setdefault(group, set())
        complete = history_ok.get(group, True)
        record = by_pair.get(pair)
        doc = prepare(record["document"], record["key"]) if record else None
        fs = features(doc) if doc else {}
        active = set(fs) if doc and doc["status"] != "none" else set()
        status = doc["status"] if doc else "missing"
        issues = _issues(doc) if doc else ["Paire non codée."]
        coding_valid = bool(doc and status in {"coded", "none"} and not issues)
        if status == "draft":
            issues.append("Codage en brouillon.")
        lineage_valid = True
        tracking = (
            doc["tracking"]
            if doc
            else {"parents": [], "objects": {}, "dag_links": {}, "removals": {}}
        )
        old_graphs = {}
        source_pairs = {}
        source_authors = {}
        for parent in tracking["parents"]:
            try:
                old = historical(parent["key"], parent["revision"])
                old_graphs[(parent["key"], parent["revision"])] = old
                source_pairs[parent["key"]] = parent["pair"]
                latest = lookup.get(parent["key"])
                if latest is None and store is not None:
                    getter = getattr(store, "current_document", None) or getattr(
                        store, "get", None
                    )
                    if getter:
                        latest = getter(parent["key"])
                source_authors[parent["key"]] = latest["author"] if latest else ""
                if (
                    not latest
                    or same_graph(
                        subset(old, parent["path_ids"]),
                        subset(latest["document"], parent["path_ids"]),
                        0.08,
                        False,
                    )
                    is not True
                ):
                    issues.append("Une origine a changé ou reste à vérifier.")
                    lineage_valid = False
            except (ValueError, KeyError, StopIteration):
                issues.append("Une origine est indisponible.")
                lineage_valid = False
        owners = (
            {
                oid: p["id"]
                for p in doc["paths"]
                for oid in p["node_ids"] + p["edge_ids"]
            }
            if doc
            else {}
        )
        objects = {o["id"]: o for o in doc["nodes"] + doc["edges"]} if doc else {}
        pair_occ = []
        object_changes = {}
        live_sources = set()
        for key, f in fs.items():
            for oid in f["object_ids"]:
                meta = tracking["objects"][oid]
                ref = meta["source"]
                old = None
                oldfeatures = {}
                same = True
                if ref:
                    live_sources.add((ref["key"], ref["revision"], ref["object_id"]))
                    try:
                        old = historical(ref["key"], ref["revision"])
                        source_key = (ref["key"], ref["revision"])
                        if source_key not in features_cache:
                            features_cache[source_key] = features(old)
                        oldfeatures = features_cache[source_key]
                        same = _parent_same(doc, old, oid, meta)
                    except (ValueError, KeyError, StopIteration):
                        same = False
                        lineage_valid = False
                baseline = bool(
                    ref
                    and key in oldfeatures
                    and ref["object_id"] in oldfeatures[key]["object_ids"]
                )
                change = (
                    ("unchanged" if baseline and same else "modified")
                    if ref
                    else "not_applicable"
                )
                if ref and change == "modified":
                    object_changes[oid] = (ref, old)
                value = f["value"]
                is_relation = f["kind"] == "relation"
                endpoint_a = value.get("source", {}) if is_relation else {}
                endpoint_b = value.get("target", {}) if is_relation else {}
                q = meta["quote"]
                valid_quote = quote_valid(meta, str(row["response"]))
                expressed = bool(
                    status != "none" and meta["review"] == "expressed" and valid_quote
                )
                entry = {
                    "participant": person,
                    "interview_id": interview,
                    "pair_id": pair,
                    "pair_order": int(row.pair_order_interview),
                    "revision": record["revision"],
                    "dag_id": owners[oid],
                    "object_id": oid,
                    "kind": f["kind"],
                    "code": value.get("code", value.get("topic", "")),
                    "subtopic": value.get("text", "")
                    if f["kind"] == "subtopic"
                    else "",
                    "scope": value.get("text", "") if f["kind"] == "scope" else "",
                    "feature_key": key,
                    "value_json": packed(value),
                    "origin": meta["origin"],
                    "source_pair": source_pairs.get(ref["key"], "") if ref else "",
                    "source_author": source_authors.get(ref["key"], "") if ref else "",
                    "source_dag": ref["path_id"] if ref else "",
                    "source_revision": ref["revision"] if ref else 0,
                    "source_object": ref["object_id"] if ref else "",
                    "source_change": change,
                    "seen_before": key in seen,
                    "history_complete": complete,
                    "review": meta["review"],
                    "expressed": expressed,
                    "quote": q["text"],
                    "quote_start": q["start"],
                    "quote_end": q["end"],
                    "relation_type": value.get("relation", ""),
                    "source_id": f.get("references", {})
                    .get(oid, {})
                    .get("source_id", objects[oid].get("source", "")),
                    "target_id": f.get("references", {})
                    .get(oid, {})
                    .get("target_id", objects[oid].get("target", "")),
                    "source_code": endpoint_a.get("code", endpoint_a.get("type", "")),
                    "target_code": endpoint_b.get("code", endpoint_b.get("type", "")),
                    "topic_relation_key": f.get("topic_relation_key", ""),
                    "topic_value_json": packed(f["topic_value"])
                    if "topic_value" in f
                    else "",
                }
                pair_occ.append(entry)
        tables["occurrences"].extend(pair_occ)
        # Mechanical changes are tracked by source occurrence, never by a shared
        # concept key in a different DAG. Absence is not a belief withdrawal.
        removed = []
        for parent in tracking["parents"]:
            old = old_graphs.get((parent["key"], parent["revision"]))
            if old is None:
                continue
            selected = subset(old, parent["path_ids"])
            selected_features = features(selected)
            old_objects = {o["id"]: o for o in selected["nodes"] + selected["edges"]}
            copied_any = any(
                k == parent["key"] and r == parent["revision"]
                for k, r, _ in live_sources
            )
            for oid, obj in old_objects.items():
                if (parent["key"], parent["revision"], oid) in live_sources:
                    continue
                source_path = next(
                    p["id"]
                    for p in selected["paths"]
                    if oid in p["node_ids"] + p["edge_ids"]
                )
                ref = {
                    "key": parent["key"],
                    "revision": parent["revision"],
                    "path_id": source_path,
                    "object_id": oid,
                }
                token = source_token(ref)
                # For a manually reconstructed declaration only semantic losses
                # are proposed; matching concepts elsewhere cannot mask a loss.
                if parent.get("method") == "declared" and not copied_any:
                    relevant = [
                        p["id"]
                        for p in doc["paths"]
                        if any(
                            r == {k: ref[k] for k in ["key", "revision", "path_id"]}
                            for r in tracking["dag_links"].get(p["id"], [])
                        )
                    ]
                    candidates = [v for v in pair_occ if v["dag_id"] in relevant]
                    old_keys = {
                        k
                        for k, f in selected_features.items()
                        if oid in f["object_ids"]
                    }
                    if old_keys and old_keys <= {v["feature_key"] for v in candidates}:
                        continue
                reason = tracking["removals"].get(token, "unspecified")
                change_row = {
                    "pair_id": pair,
                    "dag_id": "",
                    "source_pair": parent["pair"],
                    "source_author": source_authors.get(parent["key"], ""),
                    "source_dag": source_path,
                    "source_revision": parent["revision"],
                    "source_object": oid,
                    "object_id": "",
                    "kind": obj["kind"],
                    "change": "removed",
                    "reason": reason,
                    "before_json": packed(obj),
                    "after_json": "",
                    "removal_key": token,
                }
                tables["changes"].append(change_row)
                removed.append(
                    {**change_row, "label": obj.get("code") or obj.get("kind")}
                )
        for oid, (ref, old) in object_changes.items():
            before = (
                next(
                    (
                        o
                        for o in old["nodes"] + old["edges"]
                        if o["id"] == ref["object_id"]
                    ),
                    {},
                )
                if old
                else {}
            )
            tables["changes"].append(
                {
                    "pair_id": pair,
                    "dag_id": owners[oid],
                    "source_pair": source_pairs.get(ref["key"], ""),
                    "source_author": source_authors.get(ref["key"], ""),
                    "source_dag": ref["path_id"],
                    "source_revision": ref["revision"],
                    "source_object": ref["object_id"],
                    "object_id": oid,
                    "kind": objects[oid]["kind"],
                    "change": "modified",
                    "reason": "",
                    "before_json": packed(before),
                    "after_json": packed(objects[oid]),
                    "removal_key": "",
                }
            )
        dag_rows = []
        new_dags = []
        for index, path in enumerate(doc["paths"] if doc else []):
            members = [
                n
                for n in doc["nodes"]
                if n["id"] in path["node_ids"] and n["kind"] != "source"
            ]
            if not members:
                continue
            origins = {
                tracking["objects"][oid]["origin"]
                for oid in path["node_ids"] + path["edge_ids"]
            }
            refs = tracking["dag_links"].get(path["id"], [])
            origin = (
                "mixed"
                if "copied" in origins and "created" in origins
                else "continued"
                if refs or "copied" in origins
                else "unknown"
                if "unknown" in origins
                else "new"
            )
            graph = subset(doc, [path["id"]])
            current_keys = {k for k, f in fs.items() if path["id"] in f["path_ids"]}
            best = ("new", "", "")
            rank = {
                "new": 0,
                "overlap": 1,
                "undetermined": 2,
                "extension": 3,
                "subgraph": 4,
                "identical": 5,
            }
            for prev in reversed(previous_dags.get(group, [])):
                if not (current_keys & prev["keys"]):
                    continue
                relation = (
                    structural_relation(graph, prev["graph"], 0.05)
                    if time.monotonic() < deadline
                    else "undetermined"
                )
                if relation == "different":
                    relation = "overlap"
                if rank[relation] > rank[best[0]]:
                    best = (relation, prev["pair"], prev["dag"])
                if relation == "identical":
                    break
            for ref in refs:
                parent_pair = source_pairs.get(ref["key"], "")
                tables["dag_parents"].append(
                    {
                        "pair_id": pair,
                        "dag_id": path["id"],
                        "parent_pair": parent_pair,
                        "parent_author": source_authors.get(ref["key"], ""),
                        "parent_dag": ref["path_id"],
                        "parent_revision": ref["revision"],
                        "basis": "declared",
                    }
                )
            if not refs and best[0] in {"identical", "subgraph", "extension"}:
                tables["dag_parents"].append(
                    {
                        "pair_id": pair,
                        "dag_id": path["id"],
                        "parent_pair": best[1],
                        "parent_author": record["author"],
                        "parent_dag": best[2],
                        "parent_revision": by_pair[best[1]]["revision"],
                        "basis": "semantic_comparison",
                    }
                )
            dag_row = {
                "pair_id": pair,
                "dag_id": path["id"],
                "dag_number": index + 1,
                "origin": origin,
                "comparison": best[0],
                "matched_pair": best[1],
                "matched_dag": best[2],
                "n_topics": len(
                    {
                        v["feature_key"]
                        for v in pair_occ
                        if v["dag_id"] == path["id"] and v["kind"] == "topic"
                    }
                ),
                "n_relations": len(
                    [e for e in doc["edges"] if e["id"] in path["edge_ids"]]
                ),
            }
            dag_rows.append(dag_row)
            if coding_valid and status == "coded":
                new_dags.append(
                    {
                        "pair": pair,
                        "dag": path["id"],
                        "graph": graph,
                        "keys": current_keys,
                    }
                )
                if lineage_valid:
                    for ref in refs:
                        parent_pair = source_pairs.get(ref["key"], "")
                        final_tips.pop((parent_pair, ref["path_id"]), None)
                    final_tips[(pair, path["id"])] = current_keys
        previous_dags.setdefault(group, []).extend(new_dags)
        tables["dags"].extend(dag_rows)

        def count(kind, new=False):
            return len(
                {
                    v["feature_key"]
                    for v in pair_occ
                    if v["kind"] == kind
                    and (
                        not new
                        or (v["feature_key"] in active and v["feature_key"] not in seen)
                    )
                }
            )

        pair_row = {
            "participant": person,
            "interview_id": interview,
            "pair_id": pair,
            "pair_order": int(row.pair_order_interview),
            "revision": record["revision"] if record else 0,
            "status": status,
            "coding_valid": coding_valid,
            "history_complete": complete,
            "lineage_valid": lineage_valid,
            "n_dags": len(dag_rows),
            "n_topics": count("topic"),
            "n_occurrences": len([n for n in doc["nodes"] if n["kind"] == "concept"])
            if doc
            else 0,
            "n_new_topics": count("topic", True),
            "n_subtopics": count("subtopic"),
            "n_new_subtopics": count("subtopic", True),
            "n_scopes": count("scope"),
            "n_new_scopes": count("scope", True),
            "n_relations": count("relation"),
            "n_new_relations": count("relation", True),
            "n_expressed_topics": len(
                {
                    v["feature_key"]
                    for v in pair_occ
                    if v["kind"] == "topic" and v["expressed"]
                }
            ),
            "n_expressed_relations": len(
                {
                    v["feature_key"]
                    for v in pair_occ
                    if v["kind"] == "relation" and v["expressed"]
                }
            ),
            "issues": " | ".join(dict.fromkeys(issues)),
        }
        tables["pairs"].append(pair_row)
        counts = {}
        for kind in KINDS:
            present = [v for v in pair_occ if v["kind"] == kind]
            counts[kind] = {
                "total": len({v["feature_key"] for v in present}),
                "occurrences": len(present),
                "new": count(kind, True),
                "inherited": len(
                    {v["object_id"] for v in present if v["origin"] == "copied"}
                ),
                "expressed": len({v["feature_key"] for v in present if v["expressed"]}),
            }
        details[pair] = {
            "counts": counts,
            "dags": dag_rows,
            "dag_count": len(dag_rows),
            "history_complete": complete,
            "issues": list(dict.fromkeys(issues)),
            "removed": removed,
        }
        if status != "none":
            seen.update(active)
        history_ok[group] = complete and coding_valid
    valid_pairs = {
        r["pair_id"]
        for r in tables["pairs"]
        if r["coding_valid"] and r["status"] == "coded"
    }
    complete_people = {str(v) for v in canonical.PID} - {
        r["participant"] for r in tables["pairs"] if not r["coding_valid"]
    }
    for row in tables["dags"]:
        row["terminal"] = (row["pair_id"], row["dag_id"]) in final_tips
    tables["frequencies"] = aggregate(
        tables["occurrences"], valid_pairs, complete_people, final_tips
    )
    tables["details"] = details
    tables["final_tips"] = final_tips
    return tables


def aggregate(occurrences, valid_pairs, complete_people, final_tips):
    groups = {}
    for row in occurrences:
        if (
            row["kind"] != "relation"
            or row["pair_id"] not in valid_pairs
            or row["review"] == "withdrawn"
        ):
            continue
        for level, key, value in [
            ("qualified", row["feature_key"], row["value_json"]),
            ("topic", row["topic_relation_key"], row["topic_value_json"]),
        ]:
            if not key:
                continue
            g = groups.setdefault(
                (level, key),
                {
                    "value_json": value,
                    "people": set(),
                    "expressed": set(),
                    "final": set(),
                    "snapshots": set(),
                },
            )
            g["people"].add(row["participant"])
            if (row["pair_id"], row["dag_id"]) in final_tips:
                g["final"].add(row["participant"])
            g["snapshots"].add((row["participant"], row["pair_id"]))
            if row["expressed"]:
                g["expressed"].add((row["participant"], row["pair_id"]))
    result = []
    for (level, key), g in sorted(groups.items()):
        v = json.loads(g["value_json"])
        a, b = v["source"], v["target"]
        result.append(
            {
                "level": level,
                "relation_key": key,
                "relation_type": v["relation"],
                "source_code": a.get("code", a.get("type", "")),
                "target_code": b.get("code", b.get("type", "")),
                "value_json": g["value_json"],
                "n_participants": len(g["people"]),
                "n_complete_participants": len(g["people"] & complete_people),
                "n_final_participants": len(g["final"]),
                "n_expressed_pairs": len(g["expressed"]),
                "n_snapshot_pairs": len(g["snapshots"]),
            }
        )
    return result


def table_for(analysis, name):
    return pd.DataFrame(analysis[name], columns=TABLE_COLUMNS[name])


def workbook_tables(analysis):
    occurrences = table_for(analysis, "occurrences")
    topics = occurrences.loc[
        occurrences.kind.eq("topic"),
        [
            "participant",
            "pair_id",
            "pair_order",
            "dag_id",
            "object_id",
            "code",
            "origin",
            "source_pair",
            "source_author",
            "source_dag",
            "source_object",
            "source_change",
            "seen_before",
            "review",
            "expressed",
            "quote",
        ],
    ]
    qualifications = occurrences.loc[
        occurrences.kind.isin(["subtopic", "scope"]),
        [
            "participant",
            "pair_id",
            "dag_id",
            "object_id",
            "kind",
            "code",
            "subtopic",
            "scope",
            "seen_before",
            "expressed",
        ],
    ]
    relations = occurrences.loc[
        occurrences.kind.eq("relation"),
        [
            "participant",
            "pair_id",
            "dag_id",
            "object_id",
            "relation_type",
            "source_code",
            "target_code",
            "source_id",
            "target_id",
            "origin",
            "source_pair",
            "source_author",
            "source_change",
            "seen_before",
            "expressed",
            "quote",
            "value_json",
        ],
    ]
    return {
        "pairs": table_for(analysis, "pairs"),
        "dags": table_for(analysis, "dags"),
        "topics": topics,
        "qualifications": qualifications,
        "groups": occurrences.loc[
            occurrences.kind.eq("group"),
            [
                "participant",
                "pair_id",
                "dag_id",
                "object_id",
                "feature_key",
                "value_json",
                "origin",
                "source_pair",
                "source_change",
                "quote",
            ],
        ],
        "relations": relations,
        "changes": table_for(analysis, "changes"),
        "frequencies": table_for(analysis, "frequencies"),
    }


def workbook_bytes(analysis, canonical=None, records=None):
    import tempfile
    from pathlib import Path

    from graph_store import atomic_workbook

    tables = workbook_tables(analysis)
    if canonical is not None:
        source = canonical[["pair_id_interview", "question", "response"]].rename(
            columns={"pair_id_interview": "pair_id"}
        )
        tables["pairs"] = tables["pairs"].merge(
            source, on="pair_id", how="left", validate="one_to_one"
        )
    if records is not None:
        from graph_legacy import legacy_projection

        codes = {r["pair"]: legacy_projection(r["document"])[1] for r in records}
        tables["pairs"]["coding_text"] = (
            tables["pairs"]["pair_id"].map(codes).fillna("")
        )
    with tempfile.TemporaryDirectory(prefix="coding-export-") as folder:
        path = Path(folder) / "coding.xlsx"
        atomic_workbook(tables.pop("pairs"), path, tables)
        return path.read_bytes()


def csv_archive(analysis):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in TABLE_COLUMNS:
            frame = table_for(analysis, name)
            for col in frame.select_dtypes(include="object"):
                frame[col] = frame[col].map(
                    lambda s: (
                        "'" + s
                        if isinstance(s, str)
                        and s.lstrip().startswith(("=", "+", "-", "@", "\t", "\r"))
                        else s
                    )
                )
            archive.writestr(
                name + ".csv", frame.to_csv(index=False).encode("utf-8-sig")
            )
    return buffer.getvalue()
