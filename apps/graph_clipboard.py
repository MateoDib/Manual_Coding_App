"""Copy selected occurrences without losing groups, evidence scope or history."""

import math
from copy import deepcopy

from graph_model import GraphError, empty_document, validate_document
from graph_relations import JUNCTION_KINDS
from graph_tracking import continue_from, new_record, prepare


def selected_nodes(document, node_ids):
    nodes = {n["id"]: n for n in document["nodes"]}
    if (
        not isinstance(node_ids, list)
        or not node_ids
        or len(node_ids) > 150
        or any(not isinstance(v, str) or v not in nodes for v in node_ids)
    ):
        raise GraphError("Sélectionnez au moins un bloc à copier.")
    selected = set(node_ids)
    explicit = set(selected)
    while True:
        before = set(selected)
        # A complete set of selected operands includes its connecting junction,
        # even if the small symbol lies just outside the selection rectangle.
        for node in nodes.values():
            if node["kind"] in JUNCTION_KINDS:
                members = {
                    e["source"]
                    for e in document["edges"]
                    if e["kind"] == "membership" and e["target"] == node["id"]
                }
                if len(members) >= 2 and members <= explicit:
                    selected.add(node["id"])
        for oid in list(selected):
            node = nodes[oid]
            if node["kind"] in JUNCTION_KINDS:
                selected.update(
                    e["source"]
                    for e in document["edges"]
                    if e["kind"] == "membership" and e["target"] == oid
                )
            target = node.get("attachment")
            if target:
                if target["kind"] == "node":
                    selected.add(target["id"])
                elif target["kind"] == "edge":
                    edge = next(e for e in document["edges"] if e["id"] == target["id"])
                    selected.update([edge["source"], edge["target"]])
                else:
                    path = next(p for p in document["paths"] if p["id"] == target["id"])
                    selected.update(path["node_ids"])
        if selected == before:
            return sorted(selected)


def paste_selection(current, source, node_ids, at, *, inherited):
    ids = set(selected_nodes(source["document"], node_ids))
    paths = [p["id"] for p in source["document"]["paths"] if ids & set(p["node_ids"])]
    blank = prepare(
        empty_document(), response_digest=current["tracking"]["response_digest"]
    )
    fragment = continue_from(blank, source, paths)
    keep_nodes = {
        n["id"]
        for n in fragment["nodes"]
        if fragment["tracking"]["objects"][n["id"]]["source"]["object_id"] in ids
    }
    keep_edges = {
        e["id"]
        for e in fragment["edges"]
        if e["source"] in keep_nodes and e["target"] in keep_nodes
    }
    fragment["nodes"] = [n for n in fragment["nodes"] if n["id"] in keep_nodes]
    fragment["edges"] = [e for e in fragment["edges"] if e["id"] in keep_edges]
    for kind, keep in [("nodes", keep_nodes), ("edges", keep_edges)]:
        fragment["layout"][kind] = {
            k: v for k, v in fragment["layout"][kind].items() if k in keep
        }
    for p in fragment["paths"]:
        p["node_ids"] = [v for v in p["node_ids"] if v in keep_nodes]
        p["edge_ids"] = [v for v in p["edge_ids"] if v in keep_edges]
    if "editor" in fragment:
        fragment["editor"]["node_text"] = {
            k: v for k, v in fragment["editor"]["node_text"].items() if k in keep_nodes
        }
    if not inherited:
        fragment["tracking"]["parents"] = []
        fragment["tracking"]["dag_links"] = {p["id"]: [] for p in fragment["paths"]}
        fragment["tracking"]["objects"] = {
            oid: new_record() for oid in keep_nodes | keep_edges
        }
    fragment = prepare(fragment)
    if (
        not isinstance(at, dict)
        or set(at) != {"x", "y"}
        or any(
            type(v) not in (float, int) or not math.isfinite(v) or abs(v) > 90000
            for v in at.values()
        )
    ):
        raise GraphError("Emplacement du collage invalide.")
    boxes = list(fragment["layout"]["nodes"].values())
    dx = (
        at["x"]
        - (min(b["x"] for b in boxes) + max(b["x"] + b["width"] for b in boxes)) / 2
    )
    dy = (
        at["y"]
        - (min(b["y"] for b in boxes) + max(b["y"] + b["height"] for b in boxes)) / 2
    )
    for b in boxes:
        b.update(x=b["x"] + dx, y=b["y"] + dy, locked=False)
    for v in fragment["layout"]["edges"].values():
        for point in v["points"]:
            point.update(x=point["x"] + dx, y=point["y"] + dy)
    result = prepare(current)
    for kind in ["nodes", "edges", "paths"]:
        result[kind].extend(fragment[kind])
    for kind in ["nodes", "edges"]:
        result["layout"][kind].update(fragment["layout"][kind])
    if fragment.get("editor"):
        result.setdefault("editor", {"node_text": {}})["node_text"].update(
            fragment["editor"]["node_text"]
        )
    for p in fragment["tracking"]["parents"]:
        previous = next(
            (
                v
                for v in result["tracking"]["parents"]
                if v["key"] == p["key"] and v["revision"] == p["revision"]
            ),
            None,
        )
        if previous:
            from graph_metrics import semantic_digest
            from graph_tracking import subset

            previous["path_ids"] = sorted(
                set(previous["path_ids"]) | set(p["path_ids"])
            )
            previous["semantic_digest"] = semantic_digest(
                subset(source["document"], previous["path_ids"])
            )
        else:
            result["tracking"]["parents"].append(deepcopy(p))
    result["tracking"]["objects"].update(fragment["tracking"]["objects"])
    result["tracking"]["dag_links"].update(fragment["tracking"]["dag_links"])
    result["provenance"]["parent"] = (
        "clipboard:" + source["key"] + ":" + str(source["revision"])
    )
    result["status"] = "draft"
    return validate_document(prepare(result)), sorted(keep_nodes)
