"""Bounded typed graph comparisons; geometry and displayed wording are ignored."""

from __future__ import annotations

import copy
import time
from collections import Counter

import networkx as nx
from graph_relations import JUNCTION_KINDS


def typed_graph(doc, include_status=True):
    doc = copy.deepcopy(doc)
    # A standalone two-member junction and a labelled binary relation have
    # the same meaning. A junction with a consequence is kept explicitly:
    # it cannot be replaced by a link starting from one of its operands.
    for group in list(doc["nodes"]):
        if group["kind"] not in JUNCTION_KINDS:
            continue
        if (
            group["code"]
            or group["subtopics"]
            or group["scopes"]
            or group["attachment"]
        ):
            continue
        members = [
            e
            for e in doc["edges"]
            if e["target"] == group["id"] and e["kind"] == "membership"
        ]
        related = [e for e in doc["edges"] if group["id"] in (e["source"], e["target"])]
        if (
            len(members) != 2
            or len(related) != 2
            or len({e["source"] for e in members}) != 2
            or (
                group["kind"] == "priority"
                and group.get("dominant") not in {e["source"] for e in members}
            )
        ):
            continue
        old_ids = {group["id"], *(e["id"] for e in members)}
        if any(
            n["attachment"] and n["attachment"]["id"] in old_ids for n in doc["nodes"]
        ):
            continue
        affected = [p for p in doc["paths"] if group["id"] in p["node_ids"]]
        if any(not {e["id"] for e in members} <= set(p["edge_ids"]) for p in affected):
            continue
        doc["nodes"] = [n for n in doc["nodes"] if n["id"] != group["id"]]
        doc["edges"] = [e for e in doc["edges"] if e["id"] not in old_ids]
        doc["edges"].append(
            {
                "id": group["id"],
                "kind": group["kind"],
                "source": members[0]["source"],
                "target": members[1]["source"],
                "dominant": group.get("dominant")
                if group["kind"] == "priority"
                else None,
            }
        )
        for path in affected:
            path["node_ids"] = [v for v in path["node_ids"] if v != group["id"]]
            path["edge_ids"] = [v for v in path["edge_ids"] if v not in old_ids] + [
                group["id"]
            ]
    g = nx.DiGraph()
    g.add_node(
        ("status",),
        value=(
            "status",
            "none" if include_status and doc["status"] == "none" else "graph",
        ),
    )
    references = {n["id"]: ("node", n["id"]) for n in doc["nodes"]}
    references.update({e["id"]: ("edge", e["id"]) for e in doc["edges"]})
    references.update({p["id"]: ("path", p["id"]) for p in doc["paths"]})
    for n in doc["nodes"]:
        value = (
            "node",
            n["kind"],
            n["code"],
            tuple(sorted(n["subtopics"])),
            tuple(sorted(n["scopes"])),
        )
        g.add_node(references[n["id"]], value=value)
        if n["kind"] == "priority" and n.get("dominant") in references:
            g.add_edge(references[n["id"]], references[n["dominant"]], role="dominant")
    for e in doc["edges"]:
        g.add_node(references[e["id"]], value=("relation", e["kind"]))
        if e["kind"] == "priority":
            dominated = e["target"] if e["dominant"] == e["source"] else e["source"]
            g.add_edge(references[e["id"]], references[e["dominant"]], role="dominant")
            g.add_edge(references[dominated], references[e["id"]], role="dominated")
        elif e["kind"] in {"coexistence", "addition", "definition", "link"}:
            # These binary relations are symmetric; reversing the drawing
            # must not create a disagreement in research coding.
            for endpoint in (e["source"], e["target"]):
                g.add_edge(references[e["id"]], references[endpoint], role="operand")
        else:
            g.add_edge(references[e["source"]], references[e["id"]], role="source")
            g.add_edge(references[e["id"]], references[e["target"]], role="target")
    for p in doc["paths"]:
        g.add_node(references[p["id"]], value=("path",))
        for value in p["node_ids"] + p["edge_ids"]:
            g.add_edge(references[p["id"]], references[value], role="contains")
    for n in doc["nodes"]:
        if n["attachment"]:
            g.add_edge(
                references[n["id"]],
                references[n["attachment"]["id"]],
                role="annotates",
            )
    return g


def _matcher(first, second, deadline):
    class Bounded(nx.algorithms.isomorphism.DiGraphMatcher):
        def semantic_feasibility(self, a, b):
            if time.monotonic() > deadline:
                raise TimeoutError
            return super().semantic_feasibility(a, b)

        def candidate_pairs_iter(self):
            for pair in super().candidate_pairs_iter():
                if time.monotonic() > deadline:
                    raise TimeoutError
                yield pair

    return Bounded(
        first,
        second,
        node_match=lambda a, b: a["value"] == b["value"],
        edge_match=lambda a, b: a["role"] == b["role"],
    )


def same_graph(first, second, budget_seconds=1.5, include_status=True):
    if any(
        d.get("editor", {}).get("node_text")
        or any(e["kind"] == "link" for e in d["edges"])
        for d in (first, second)
    ):
        return None
    deadline = time.monotonic() + budget_seconds
    a, b = typed_graph(first, include_status), typed_graph(second, include_status)
    if Counter(n["value"] for _, n in a.nodes(data=True)) != Counter(
        n["value"] for _, n in b.nodes(data=True)
    ):
        return False
    try:
        return _matcher(a, b, deadline).is_isomorphic()
    except TimeoutError:
        return None


def structural_relation(current, previous, budget_seconds=0.08):
    if any(
        d.get("editor", {}).get("node_text")
        or any(e["kind"] == "link" for e in d["edges"])
        for d in (current, previous)
    ):
        return "undetermined"
    deadline = time.monotonic() + budget_seconds
    a, b = typed_graph(current, False), typed_graph(previous, False)
    ca, cb = (Counter(n["value"] for _, n in g.nodes(data=True)) for g in (a, b))
    try:
        if ca == cb and _matcher(a, b, deadline).is_isomorphic():
            return "identical"
        if ca <= cb and _matcher(b, a, deadline).subgraph_is_monomorphic():
            return "subgraph"
        if cb <= ca and _matcher(a, b, deadline).subgraph_is_monomorphic():
            return "extension"
        return "different"
    except TimeoutError:
        return "undetermined"
