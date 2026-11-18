"""Conservative migration of the historical coding grammar.

Mixed operators are proposed for review, never silently adjudicated. Parentheses
and scopes are balanced with a stack, including nested qualifier expressions.
"""

from __future__ import annotations

import re
from collections import defaultdict

from graph_model import (
    GraphError,
    concept,
    edge_layout,
    empty_document,
    node_layout,
    validate_document,
)
from graph_relations import JUNCTION_KINDS

OPS = ("-->", "->", "=", ";", "+", "&", "<", ">", "|")


def tokenize(text: str) -> tuple[list[str], list[str]]:
    if len(text) > 100000:
        raise GraphError("Codage trop long.")
    terms, operators, stack, start, i = [], [], [], 0, 0
    while i < len(text):
        c = text[i]
        if c in "([":
            stack.append(c)
            if len(stack) > 12:
                raise GraphError("Imbrication trop profonde.")
        elif c in ")]":
            if not stack or stack.pop() != {")": "(", "]": "["}[c]:
                raise GraphError("Parenthèses ou crochets déséquilibrés.")
        elif c in "{}":
            raise GraphError(
                "Les accolades n'ont pas de sens défini dans ce coding scheme."
            )
        if not stack:
            op = next((op for op in OPS if text.startswith(op, i)), None)
            if op:
                terms.append(text[start:i].strip())
                operators.append("-->" if op == "->" else op)
                i += len(op)
                start = i
                continue
        i += 1
    if stack:
        raise GraphError("Parenthèses ou crochets déséquilibrés.")
    terms.append(text[start:].strip())
    return terms, operators


def split_items(text: str) -> list[str]:
    result, stack, start = [], [], 0
    for i, c in enumerate(text):
        if c in "([":
            stack.append(c)
        elif c in ")]":
            if not stack or stack.pop() != {")": "(", "]": "["}[c]:
                raise GraphError("Précisions déséquilibrées.")
        elif c == "," and not stack:
            if not text[start:i].strip():
                raise GraphError("Précision vide.")
            result.append(text[start:i].strip())
            start = i + 1
    if stack:
        raise GraphError("Précisions déséquilibrées.")
    if text[start:].strip():
        result.append(text[start:].strip())
    return result


def parse_topic(text: str) -> tuple[str, list[str], list[str]]:
    match = re.match(r"\s*([A-Za-z][A-Za-z0-9_ ]*)", text)
    if not match:
        raise GraphError("Un concept est vide ou mal formé.")
    code = re.sub(r"\s+", "_", match.group(1).strip().lower())
    i = match.end()
    annotations = {}
    while i < len(text):
        if text[i].isspace():
            i += 1
            continue
        opening = text[i]
        if opening not in "([" or opening in annotations:
            raise GraphError("Expression de concept non reconnue.")
        closing = ")" if opening == "(" else "]"
        depth, start = 1, i + 1
        i += 1
        while i < len(text) and depth:
            if text[i] == opening:
                depth += 1
            elif text[i] == closing:
                depth -= 1
            i += 1
        if depth:
            raise GraphError("Précision inachevée.")
        annotations[opening] = split_items(text[start : i - 1])
    return code, annotations.get("(", []), annotations.get("[", [])


def import_sequence(text: str) -> dict:
    doc = empty_document()
    doc["provenance"]["original_text"] = text
    if not text.strip():
        return doc
    if text.strip().lower() == "none":
        doc["status"] = "none"
        return doc
    terms, ops = tokenize(text)
    segments, start = [], 0
    for i, op in enumerate(ops):
        if op == ";":
            segments.append((terms[start : i + 1], ops[start:i]))
            start = i + 1
    segments.append((terms[start:], ops[start:]))
    doc["paths"] = []
    serial = 0

    def new_id(prefix):
        nonlocal serial
        serial += 1
        if serial > 650:
            raise GraphError("Ancien codage trop grand pour une migration automatique.")
        return f"{prefix}{serial}"

    for path_i, (parts, relations) in enumerate(segments):
        path = {
            "id": f"p{path_i + 1}",
            "label": f"Chemin {path_i + 1}",
            "node_ids": [],
            "edge_ids": [],
        }
        doc["paths"].append(path)

        def add_node(text, kind="concept"):
            code, subs, scopes = parse_topic(text)
            n = concept(new_id("n"), code)
            n.update(kind=kind, subtopics=subs, scopes=scopes)
            if kind == "source":
                n["attachment"] = {"kind": "path", "id": path["id"]}
            doc["nodes"].append(n)
            path["node_ids"].append(n["id"])
            doc["layout"]["nodes"][n["id"]] = node_layout()
            return n["id"]

        def add_edge(source, target, kind, dominant=None):
            eid = new_id("e")
            doc["edges"].append(
                {
                    "id": eid,
                    "source": source,
                    "target": target,
                    "kind": kind,
                    "dominant": dominant,
                }
            )
            path["edge_ids"].append(eid)
            doc["layout"]["edges"][eid] = edge_layout()

        source_start = next((i for i, v in enumerate(relations) if v == "|"), None)
        sources = []
        if source_start is not None:
            if any(v != "|" for v in relations[source_start:]):
                raise GraphError(
                    "La portée de la source est ambiguë : placer la source à la fin du chemin."
                )
            sources = parts[source_start + 1 :]
            parts, relations = parts[: source_start + 1], relations[:source_start]
        ids = [add_node(term) for term in parts]
        if any(op in ("+", "&") for op in relations) and len(set(relations)) > 1:
            doc["provenance"]["import_warnings"].append(
                f"Chemin {path_i + 1} : opérateurs mixtes ; vérifier quels éléments appartiennent au groupe."
            )
        # Group equal-precedence +/& runs left-to-right; interpretation must be
        # approved explicitly for mixed historical expressions.
        i = 0
        while i < len(relations):
            if relations[i] in ("+", "&"):
                op = relations[i]
                gid = new_id("g")
                group = concept(gid, "", op)
                group["kind"] = "addition" if op == "+" else "coexistence"
                doc["nodes"].append(group)
                path["node_ids"].append(gid)
                doc["layout"]["nodes"][gid] = node_layout(width=28, height=28)
                add_edge(ids[i], gid, "membership")
                add_edge(ids[i + 1], gid, "membership")
                ids[i : i + 2] = [gid]
                relations.pop(i)
            else:
                i += 1
        for i, op in enumerate(relations):
            kind = {
                "-->": "causal",
                "=": "definition",
                "<": "priority",
                ">": "priority",
            }.get(op)
            if kind is None:
                raise GraphError("Opérateur non reconnu.")
            dominant = (
                (ids[i + 1] if op == "<" else ids[i]) if kind == "priority" else None
            )
            add_edge(ids[i], ids[i + 1], kind, dominant)
        incoming = defaultdict(list)
        for e in doc["edges"]:
            if e["kind"] == "membership":
                incoming[e["target"]].append(e["source"])

        def position(nid, x, y):
            members = incoming[nid]
            if not members:
                doc["layout"]["nodes"][nid].update(x=x, y=y)
                return x + 210
            end = max(position(m, x, y + j * 105) for j, m in enumerate(members))
            doc["layout"]["nodes"][nid].update(
                x=end, y=y + (len(members) - 1) * 52 + 18
            )
            return end + 90

        x, y = 0, path_i * 280
        for nid in ids:
            x = position(nid, x, y)
        for j, source in enumerate(sources):
            nid = add_node(source, "source")
            doc["layout"]["nodes"][nid].update(x=0, y=y + 175 + j * 75)
    doc["status"] = "coded"
    doc["provenance"]["import_reviewed"] = not doc["provenance"]["import_warnings"]
    return validate_document(doc)


def migration_document(text: str) -> dict:
    """Preserve unsupported input as a reviewable draft, never erase it."""
    try:
        return import_sequence(text)
    except GraphError as exc:
        doc = empty_document()
        doc["provenance"].update(
            original_text=text[:100000],
            import_reviewed=False,
            import_warnings=[str(exc)],
        )
        return doc


def topic_token(node: dict) -> str:
    text = node["code"]
    if node["subtopics"]:
        text += " (" + ", ".join(node["subtopics"]) + ")"
    if node["scopes"]:
        text += "[" + ", ".join(node["scopes"]) + "]"
    return text


def legacy_projection(doc: dict) -> tuple[str, str, str]:
    """Return (status, text, reason). JSON remains the lossless master.

    Compatible means every relation/annotation has a historical expression;
    historical text cannot encode instance identity or presentation.
    """
    if doc["status"] == "none":
        return "compatible", "none", ""
    if doc.get("editor", {}).get("node_text"):
        return "review_required", "", "Un texte de bloc reste à terminer."
    if not doc["provenance"]["import_reviewed"]:
        return "review_required", "", "L'ancien codage nécessite une vérification."
    if doc["status"] == "none":
        return "compatible", "none", ""
    nodes = {n["id"]: n for n in doc["nodes"]}
    by_edge = {e["id"]: e for e in doc["edges"]}
    incoming = defaultdict(list)
    for e in doc["edges"]:
        if e["kind"] == "membership":
            incoming[e["target"]].append(e["source"])

    def term(nid, active=None):
        active = set() if active is None else set(active)
        if nid in active:
            raise GraphError("Groupe cyclique.")
        active.add(nid)
        n = nodes[nid]
        if n["kind"] == "concept":
            if not n["code"]:
                raise GraphError("Concept sans code.")
            return topic_token(n)
        if n["kind"] not in JUNCTION_KINDS or len(incoming[nid]) < 2:
            raise GraphError("Groupe incomplet.")
        if any(nodes[m]["kind"] in JUNCTION_KINDS for m in incoming[nid]):
            raise GraphError("Les groupes imbriqués nécessitent le format graphique.")
        members = sorted(incoming[nid])
        if n["kind"] in {"definition", "priority"} and len(members) != 2:
            raise GraphError("Une relation binaire requiert exactement deux sujets.")
        if n["kind"] == "priority":
            if n.get("dominant") not in members:
                raise GraphError("Sujet prioritaire non renseigné.")
            members.sort(key=lambda oid: oid != n["dominant"])
        op = {"coexistence": "&", "addition": "+", "definition": "=", "priority": ">"}[
            n["kind"]
        ]
        return (" " + op + " ").join(term(m, active) for m in members)

    expressions = []
    try:
        for path in doc["paths"]:
            edges = [
                by_edge[eid]
                for eid in path["edge_ids"]
                if by_edge[eid]["kind"] != "membership"
            ]
            if any(e["kind"] == "link" for e in edges):
                raise GraphError("Un trait simple reste à qualifier.")
            if len(edges) > 1 and any(
                e["kind"] in {"coexistence", "addition"} for e in edges
            ):
                raise GraphError(
                    "Une coexistence ou addition binaire avec d'autres relations nécessite le graphe pour éviter une lecture causale ambiguë."
                )
            excluded = {m for nid in path["node_ids"] for m in incoming[nid]}
            if any(e["source"] in excluded or e["target"] in excluded for e in edges):
                raise GraphError(
                    "Un membre de groupe possède une relation indépendante dans le même chemin."
                )
            if any(nodes[e["target"]]["kind"] in JUNCTION_KINDS for e in edges):
                raise GraphError(
                    "Une relation aboutit à un groupe : la notation historique est ambiguë."
                )
            outgoing = defaultdict(list)
            for e in edges:
                outgoing[e["source"]].append(e)
            roots = sorted(
                set(path["node_ids"]) - {e["target"] for e in edges} - excluded
            )
            roots = [r for r in roots if nodes[r]["kind"] != "source"]
            seen_edges = set()

            def walk(nid, text, active):
                if nid in active:
                    raise GraphError("Chemin cyclique.")
                if len(expressions) > 200:
                    raise GraphError("Trop de chemins pour une projection textuelle.")
                if not outgoing[nid]:
                    return [text]
                result = []
                for e in sorted(outgoing[nid], key=lambda e: e["id"]):
                    seen_edges.add(e["id"])
                    op = {
                        "causal": "-->",
                        "definition": "=",
                        "coexistence": "&",
                        "addition": "+",
                    }.get(e["kind"])
                    if e["kind"] == "priority":
                        op = ">" if e["dominant"] == e["source"] else "<"
                    result.extend(
                        walk(
                            e["target"],
                            text + " " + op + " " + term(e["target"]),
                            active | {nid},
                        )
                    )
                    if len(result) > 200:
                        raise GraphError(
                            "Trop de chemins pour une projection textuelle."
                        )
                return result

            path_expressions = []
            for root in roots:
                path_expressions.extend(walk(root, term(root), set()))
            if seen_edges != {e["id"] for e in edges}:
                raise GraphError("La structure nécessite le format graphique.")
            for n in doc["nodes"]:
                if n["kind"] != "source":
                    continue
                attachment = n["attachment"]
                if attachment is None or attachment["kind"] != "path":
                    raise GraphError(
                        "Une source attachée à un concept ou lien nécessite le format graphique."
                    )
                if attachment["id"] == path["id"]:
                    if not n["code"]:
                        raise GraphError("Source sans code.")
                    path_expressions = [
                        x + " | " + topic_token(n) for x in path_expressions
                    ]
            expressions.extend(path_expressions)
        return "compatible", "; ".join(expressions), ""
    except GraphError as exc:
        return "requires_graph", "", str(exc)
