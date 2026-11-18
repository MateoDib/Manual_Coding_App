"""Versioned, presentation-independent narrative graph contract.

All files imported from the browser pass this validator before persistence or
TeX generation. Unknown versions/fields fail explicitly rather than degrading.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections import defaultdict

from graph_relations import BINARY_KINDS, JUNCTION_KINDS, member_ids

SCHEMA_VERSION = 1
MAX_BYTES = 1_000_000
MAX_NODES = 150
MAX_EDGES = 500
PORTS = {
    "left",
    "right",
    "top",
    "bottom",
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
}
KINDS = {"concept", "source"} | JUNCTION_KINDS
EDGE_KINDS = {
    "causal",
    "definition",
    "priority",
    "membership",
    "coexistence",
    "addition",
    "link",
}
ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
CODE = re.compile(r"[a-z][a-z0-9_]{0,159}\Z")


class GraphError(ValueError):
    """A document violates the supported graph contract."""


def empty_document() -> dict:
    return {
        "schema_version": 1,
        "status": "draft",
        "nodes": [],
        "edges": [],
        "paths": [{"id": "p1", "label": "DAG 1", "node_ids": [], "edge_ids": []}],
        "layout": {"nodes": {}, "edges": {}},
        "provenance": {
            "original_text": "",
            "import_warnings": [],
            "import_reviewed": True,
        },
    }


def concept(node_id: str, code: str, label: str | None = None) -> dict:
    return {
        "id": node_id,
        "kind": "concept",
        "code": code,
        "label": label if label is not None else code.replace("_", " ").capitalize(),
        "subtopics": [],
        "scopes": [],
        "attachment": None,
    }


def node_layout(
    x: float = 0, y: float = 0, width: float = 168, height: float = 64
) -> dict:
    return {"x": x, "y": y, "width": width, "height": height, "locked": False}


def edge_layout() -> dict:
    return {
        "source_port": "right",
        "target_port": "left",
        "route": "straight",
        "points": [],
        "label_t": 0.5,
        "label_dx": 0,
        "label_dy": 0,
    }


def _keys(value, required, optional=()):
    if (
        not isinstance(value, dict)
        or not set(required) <= value.keys()
        or value.keys() - set(required) - set(optional)
    ):
        raise GraphError("Champs manquants ou inconnus dans le document graphique.")


def _text(value, limit=2000):
    if (
        not isinstance(value, str)
        or len(value) > limit
        or any(ord(c) < 32 and c not in "\n\t" for c in value)
    ):
        raise GraphError("Texte invalide ou trop long.")


def _id(value):
    if not isinstance(value, str) or not ID.fullmatch(value):
        raise GraphError("Identifiant graphique invalide.")


def _number(value, low=-100000, high=100000):
    if (
        type(value) not in (int, float)
        or not math.isfinite(value)
        or not low <= value <= high
    ):
        raise GraphError("Coordonnée ou dimension invalide.")


def _texts(values, limit=50):
    if not isinstance(values, list) or len(values) > limit:
        raise GraphError("Liste de précisions invalide.")
    for value in values:
        _text(value, 500)


def _validate_document(document: dict) -> dict:
    """Validate structure, references and limits; return an independent copy."""
    try:
        size = len(json.dumps(document, ensure_ascii=False, allow_nan=False).encode())
    except (ValueError, TypeError, RecursionError) as exc:
        raise GraphError("Document JSON invalide.") from exc
    if size > MAX_BYTES:
        raise GraphError("Document trop volumineux (maximum 1 Mo).")
    _keys(
        document,
        {"schema_version", "status", "nodes", "edges", "paths", "layout", "provenance"},
        {"editor", "tracking"},
    )
    if (
        type(document["schema_version"]) is not int
        or document["schema_version"] != SCHEMA_VERSION
    ):
        raise GraphError("Version du document non prise en charge.")
    if document["status"] not in ("draft", "coded", "none"):
        raise GraphError("Statut inconnu.")
    for key, limit in (("nodes", MAX_NODES), ("edges", MAX_EDGES), ("paths", 150)):
        if not isinstance(document[key], list) or len(document[key]) > limit:
            raise GraphError("Graphe trop grand ou liste invalide.")
    nodes, edges, paths = document["nodes"], document["edges"], document["paths"]
    all_objects = nodes + edges + paths
    ids = []
    for obj in all_objects:
        if not isinstance(obj, dict):
            raise GraphError("Objet graphique invalide.")
        _id(obj.get("id"))
        ids.append(obj["id"])
    if len(set(ids)) != len(ids):
        raise GraphError("Identifiants graphiques dupliqués.")
    by_id = {n["id"]: n for n in nodes}
    if "editor" in document:
        _keys(document["editor"], {"node_text"})
        drafts = document["editor"]["node_text"]
        if not isinstance(drafts, dict) or not drafts.keys() <= by_id.keys():
            raise GraphError("Textes de brouillon rattachés à des blocs inconnus.")
        for value in drafts.values():
            _text(value, 2000)
    edge_ids = {e["id"] for e in edges}
    path_ids = {p["id"] for p in paths}
    if not paths:
        raise GraphError("Au moins un chemin narratif est nécessaire.")
    for n in nodes:
        _keys(
            n,
            {"id", "kind", "code", "label", "subtopics", "scopes", "attachment"},
            {"dominant"},
        )
        if n["kind"] not in KINDS:
            raise GraphError("Type de concept inconnu.")
        dominant = n.get("dominant")
        if dominant is not None and (
            n["kind"] != "priority"
            or dominant not in member_ids(document, n["id"])
            or dominant not in by_id
        ):
            raise GraphError(
                "La priorité doit désigner un des sujets reliés à cette relation."
            )
        if n["kind"] in BINARY_KINDS and (n["code"] or n["subtopics"] or n["scopes"]):
            raise GraphError(
                "Une relation = ou de priorité ne porte pas de code de topic ni de qualifications."
            )
        _text(n["code"], 160)
        if n["kind"] == "concept" and n["code"] == "none":
            raise GraphError(
                "Utilisez l'état « aucun ajout » plutôt qu'un concept none."
            )
        if n["code"] and not CODE.fullmatch(n["code"]):
            raise GraphError(
                "Les codes utilisent des lettres minuscules, chiffres et underscores."
            )
        _text(n["label"])
        _texts(n["subtopics"])
        _texts(n["scopes"])
        a = n["attachment"]
        if a is not None:
            _keys(a, {"kind", "id"})
            targets = {"node": set(by_id), "edge": edge_ids, "path": path_ids}
            if (
                n["kind"] != "source"
                or a["kind"] not in targets
                or a["id"] not in targets[a["kind"]]
                or a["id"] == n["id"]
                or (
                    a["kind"] == "node"
                    and by_id.get(a["id"], {}).get("kind") == "source"
                )
            ):
                raise GraphError("La cible d'une source est invalide.")
    for e in edges:
        _keys(e, {"id", "kind", "source", "target", "dominant"})
        if (
            e["kind"] not in EDGE_KINDS
            or e["source"] not in by_id
            or e["target"] not in by_id
        ):
            raise GraphError("Relation ou extrémité inconnue.")
        if (
            by_id[e["source"]]["kind"] == "source"
            or by_id[e["target"]]["kind"] == "source"
        ):
            raise GraphError("Une source est une annotation, pas une cause.")
        if (
            e["kind"] == "membership"
            and by_id[e["target"]]["kind"] not in JUNCTION_KINDS
        ):
            raise GraphError(
                "Un opérande doit aboutir à une relation &, +, = ou de priorité."
            )
        if e["kind"] == "priority":
            if e["dominant"] not in (e["source"], e["target"]):
                raise GraphError("La priorité doit désigner l'un des deux concepts.")
        elif e["dominant"] is not None:
            raise GraphError("Une dominance est réservée aux relations de priorité.")
    for p in paths:
        _keys(p, {"id", "label", "node_ids", "edge_ids"})
        _text(p["label"], 160)
        for key, allowed in (("node_ids", set(by_id)), ("edge_ids", edge_ids)):
            values = p[key]
            if (
                not isinstance(values, list)
                or len(values) != len(set(values))
                or not set(values) <= allowed
            ):
                raise GraphError("Référence ou doublon dans un chemin narratif.")
        for e in edges:
            if e["id"] in p["edge_ids"] and not {e["source"], e["target"]} <= set(
                p["node_ids"]
            ):
                raise GraphError(
                    "Les extrémités d'une relation doivent appartenir à son chemin."
                )
    assigned_nodes = {v for p in paths for v in p["node_ids"]}
    assigned_edges = {v for p in paths for v in p["edge_ids"]}
    if assigned_nodes != set(by_id) or assigned_edges != edge_ids:
        raise GraphError("Chaque objet doit appartenir à un chemin narratif.")
    _keys(document["layout"], {"nodes", "edges"})
    nl, el = document["layout"]["nodes"], document["layout"]["edges"]
    if (
        not isinstance(nl, dict)
        or not isinstance(el, dict)
        or set(nl) != set(by_id)
        or set(el) != edge_ids
    ):
        raise GraphError("La disposition ne correspond pas aux objets du graphe.")
    for v in nl.values():
        _keys(v, {"x", "y", "width", "height", "locked"})
        _number(v["x"])
        _number(v["y"])
        _number(v["width"], 18, 1200)
        _number(v["height"], 18, 1200)
        if type(v["locked"]) is not bool:
            raise GraphError("Verrouillage invalide.")
    for v in el.values():
        _keys(
            v,
            {
                "source_port",
                "target_port",
                "route",
                "points",
                "label_t",
                "label_dx",
                "label_dy",
            },
            {"stroke"},
        )
        if v.get("stroke", "solid") not in {"solid", "dashed", "dotted"}:
            raise GraphError("Style de trait inconnu.")
        if (
            v["source_port"] not in PORTS
            or v["target_port"] not in PORTS
            or v["route"] not in ("straight", "orthogonal", "bezier")
        ):
            raise GraphError("Tracé ou ancrage inconnu.")
        if (
            not isinstance(v["points"], list)
            or len(v["points"]) > 8
            or (v["route"] == "bezier" and len(v["points"]) not in (0, 2))
        ):
            raise GraphError("Points de passage invalides.")
        for point in v["points"]:
            _keys(point, {"x", "y"})
            _number(point["x"])
            _number(point["y"])
        _number(v["label_t"], 0, 1)
        _number(v["label_dx"], -2000, 2000)
        _number(v["label_dy"], -2000, 2000)
    _keys(
        document["provenance"],
        {"original_text", "import_warnings", "import_reviewed"},
        {"parent"},
    )
    _text(document["provenance"]["original_text"], 100000)
    _texts(document["provenance"]["import_warnings"], 100)
    if type(document["provenance"]["import_reviewed"]) is not bool:
        raise GraphError("Statut de vérification d'import invalide.")
    if "parent" in document["provenance"]:
        _text(document["provenance"]["parent"], 500)
    if "tracking" in document:
        from graph_tracking import validate_tracking

        validate_tracking(document["tracking"], path_ids, set(by_id) | edge_ids)
    return copy.deepcopy(document)


def validate_document(document: dict) -> dict:
    try:
        return _validate_document(document)
    except (KeyError, TypeError, AttributeError, RecursionError, OverflowError) as exc:
        raise GraphError("Types ou structure du document graphique invalides.") from exc


def load_document(data: bytes | str) -> dict:
    if len(data) > MAX_BYTES:
        raise GraphError("Fichier trop volumineux (maximum 1 Mo).")

    def pairs(items):
        out = {}
        for k, v in items:
            if k in out:
                raise GraphError("Clés JSON dupliquées.")
            out[k] = v
        return out

    try:
        return validate_document(json.loads(data, object_pairs_hook=pairs))
    except (json.JSONDecodeError, UnicodeError, RecursionError, TypeError) as exc:
        raise GraphError("Fichier JSON invalide.") from exc


def document_digest(doc: dict) -> str:
    # JSON in the browser round-trips 10.0 as 10. These represent the same
    # geometry and must not invalidate a recommendation or cause a conflict.
    def normalized(value):
        if isinstance(value, dict):
            return {k: normalized(v) for k, v in value.items()}
        if isinstance(value, list):
            return [normalized(v) for v in value]
        if type(value) is float and value.is_integer():
            return int(value)
        return value

    return hashlib.sha256(
        json.dumps(
            normalized(doc), sort_keys=True, ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def graph_warnings(doc: dict) -> list[str]:
    warnings = []
    if doc["status"] == "coded" and not doc["nodes"]:
        warnings.append(
            "La figure est vide : utilisez none si cette réponse n’ajoute aucune information."
        )
    if doc.get("editor", {}).get("node_text"):
        warnings.append(
            "Un texte de bloc est encore incomplet ou à corriger. Il est conservé comme brouillon."
        )
    nodes = {n["id"]: n for n in doc["nodes"]}
    incoming = defaultdict(list)
    adjacency = defaultdict(list)
    for e in doc["edges"]:
        if e["kind"] == "link":
            warnings.append(
                "Un trait simple entre topics reste à qualifier avec une relation du coding scheme."
            )
        if e["kind"] == "membership":
            incoming[e["target"]].append(e["source"])
        if e["kind"] in ("causal", "membership"):
            adjacency[e["source"]].append(e["target"])
    for n in nodes.values():
        if n["kind"] in ("concept", "source") and not n["code"]:
            warnings.append(
                "Un concept ou une source n'a pas encore de code canonique."
            )
        members = set(incoming[n["id"]])
        if n["kind"] in JUNCTION_KINDS and len(members) < 2:
            warnings.append("Une relation ciblable contient moins de deux sujets.")
        if n["kind"] in BINARY_KINDS and len(members) != 2:
            warnings.append(
                "Une relation = ou de priorité doit relier exactement deux sujets."
            )
        if n["kind"] == "priority" and n.get("dominant") not in members:
            warnings.append(
                "Choisissez le sujet prioritaire dans les réglages de la relation."
            )
        if n["kind"] == "source" and n["attachment"] is None:
            warnings.append("Une source n'est attachée à aucun objet ou chemin.")
        elif n["kind"] == "source":
            target = n["attachment"]
            owners = {p["id"] for p in doc["paths"] if n["id"] in p["node_ids"]}
            targets = {
                p["id"]
                for p in doc["paths"]
                if (
                    p["id"] == target["id"]
                    if target["kind"] == "path"
                    else target["id"]
                    in p["node_ids" if target["kind"] == "node" else "edge_ids"]
                )
            }
            if owners != targets:
                warnings.append(
                    "Le rattachement d'une source à ses DAGs doit être vérifié dans ses réglages."
                )
            if target["kind"] == "path" and not any(
                v in nodes and nodes[v]["kind"] != "source"
                for p in doc["paths"]
                if p["id"] == target["id"]
                for v in p["node_ids"]
            ):
                warnings.append("Le DAG d'une source ne contient encore aucun topic.")
    colors = {}

    def visit(node):
        if colors.get(node) == 1:
            return True
        if colors.get(node) == 2:
            return False
        colors[node] = 1
        if any(visit(target) for target in adjacency[node]):
            return True
        colors[node] = 2
        return False

    if any(visit(n) for n in nodes):
        warnings.append(
            "La structure causale contient un cycle : ce brouillon n'est pas un DAG."
        )
    if doc["status"] == "none" and nodes:
        warnings.append(
            "Le statut « aucun ajout » conserve un graphe cumulatif ; il n'efface pas le précédent."
        )
    if not doc["provenance"]["import_reviewed"]:
        warnings.append(
            "L'interprétation de l'ancien codage doit être vérifiée avant publication."
        )
    return sorted(set(warnings))


def semantic_equal(first, second, budget_seconds=1.5):
    from graph_comparison import same_graph

    return same_graph(first, second, budget_seconds)
