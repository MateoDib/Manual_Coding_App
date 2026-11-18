"""V3 workflow helpers; no data files or metrics caches are created here."""

from __future__ import annotations

from graph_metrics import semantic_digest
from graph_model import GraphError, document_digest, validate_document
from graph_store import document_key
from graph_tracking import subset
from study_data import earlier_pairs


def previous_sources(canonical, pair, records):
    """All prior pairs of this interview, with identity-free graph thumbnails."""
    import hashlib

    records = {r["pair"]: r for r in records}
    result = []
    for _, row in earlier_pairs(canonical, pair).iterrows():
        source = records.get(str(row.pair_id_interview))
        doc = source["document"] if source else None
        dag_options = []
        if doc:
            for i, path in enumerate(doc["paths"]):
                names = [
                    n["code"]
                    for n in doc["nodes"]
                    if n["kind"] == "concept"
                    and n["id"] in path["node_ids"]
                    and n["code"]
                ]
                if not names:
                    continue
                graph = subset(doc, [path["id"]])
                # Neither raw provenance nor participant identifiers belong in
                # previews. The frontend draws this geometry directly as SVG.
                preview = {
                    k: graph[k]
                    for k in [
                        "schema_version",
                        "status",
                        "nodes",
                        "edges",
                        "paths",
                        "layout",
                    ]
                }
                if graph.get("editor"):
                    preview["editor"] = graph["editor"]
                preview["provenance"] = {
                    "original_text": "",
                    "import_warnings": [],
                    "import_reviewed": True,
                }
                dag_options.append(
                    {
                        "id": path["id"],
                        "label": "DAG " + str(i + 1),
                        "topics": list(dict.fromkeys(names)),
                        "preview": preview,
                    }
                )
        result.append(
            {
                "key": source["key"]
                if source
                else "uncoded_"
                + hashlib.sha256(str(row.pair_id_interview).encode()).hexdigest(),
                "order": int(row.pair_order_interview),
                "revision": source["revision"] if source else 0,
                "status": doc["status"] if doc else "missing",
                "question": str(row["question"]),
                "response": str(row["response"]),
                "paths": dag_options,
            }
        )
    return result


def selected_sources(event, choices, store):
    """Validate all displayed revisions before constructing a single replacement."""
    selected = event.get("selections")
    if selected is None:  # Older V2 clients can finish an already-open picker.
        selected = [
            {
                "source_key": event.get("source_key"),
                "path_ids": event.get("path_ids"),
                "revision": event.get("source_revision"),
            }
        ]
    if not isinstance(selected, list) or not 1 <= len(selected) <= 150:
        raise GraphError("Choisissez au moins un DAG à reprendre.")
    by_key = {choice["key"]: choice for choice in choices}
    seen, result = set(), []
    for item in selected:
        if not isinstance(item, dict) or set(item) - {
            "source_key",
            "path_ids",
            "revision",
        }:
            raise GraphError("Sélection de DAGs invalide.")
        key, paths = item.get("source_key"), item.get("path_ids")
        if not isinstance(key, str) or key in seen or key not in by_key:
            raise GraphError(
                "Les DAGs doivent provenir des questions précédentes du même entretien."
            )
        choice = by_key[key]
        if (
            not isinstance(paths, list)
            or not paths
            or len(paths) > 150
            or any(not isinstance(p, str) for p in paths)
            or len(set(paths)) != len(paths)
            or not set(paths) <= {p["id"] for p in choice["paths"]}
        ):
            raise GraphError(
                "Choisissez un ou plusieurs DAGs disponibles dans la paire sélectionnée."
            )
        revision = item.get("revision")
        if revision is not None and (
            type(revision) is not int or revision != choice["revision"]
        ):
            raise GraphError(
                "Une figure d’origine a été actualisée. Vérifiez les miniatures puis sélectionnez-la à nouveau."
            )
        source = store.get(key)
        if not source or source["revision"] != choice["revision"]:
            raise GraphError(
                "Une figure d’origine vient de changer. Rouvrez le sélecteur pour la vérifier."
            )
        seen.add(key)
        result.append((source, paths))
    return result


def validate_context(document, canonical, pair, store, dataset, author):
    doc = validate_document(document)
    t = doc.get("tracking")
    if not t:
        raise GraphError(
            "Le suivi V3 est absent. Rechargez le graphe avant de continuer."
        )
    allowed = {
        document_key(dataset, author, str(p.pair_id_interview))
        for _, p in earlier_pairs(canonical, pair).iterrows()
    }
    if author == "Harmonized":
        from coding_utils import configured_author_names

        allowed.update(
            document_key(dataset, coder, pair) for coder in configured_author_names()
        )
    for parent in t["parents"]:
        if parent["key"] not in allowed:
            raise GraphError(
                "Une reprise doit provenir du même entretien, du même codeur et d’une question antérieure."
            )
        current = store.get(parent["key"])
        if not current or current["pair"] != parent["pair"]:
            raise GraphError("Origine du DAG introuvable.")
        historical = store.historical_document(parent["key"], parent["revision"])
        if (
            document_digest(historical) != parent["digest"]
            or semantic_digest(subset(historical, parent["path_ids"]))
            != parent["semantic_digest"]
        ):
            raise GraphError("La référence du DAG d’origine est incohérente.")
    from graph_evidence import quote_valid, text_digest

    response = str(
        canonical.loc[
            canonical.pair_id_interview.astype(str).eq(pair), "response"
        ].iloc[0]
    )
    if t["response_digest"] != text_digest(response):
        raise GraphError("Le graphe ne correspond pas à cette version de la réponse.")
    parent_paths = {
        (p["key"], p["revision"], pid) for p in t["parents"] for pid in p["path_ids"]
    }
    for refs in t["dag_links"].values():
        if any(
            (r["key"], r["revision"], r["path_id"]) not in parent_paths for r in refs
        ):
            raise GraphError("Filiation de DAG sans source enregistrée.")
    node_ids = {n["id"] for n in doc["nodes"]}
    for oid, meta in t["objects"].items():
        ref = meta["source"]
        if ref:
            if (ref["key"], ref["revision"], ref["path_id"]) not in parent_paths:
                raise GraphError(
                    "Une occurrence copiée doit référencer une origine enregistrée."
                )
            old = store.historical_document(ref["key"], ref["revision"])
            path = next((p for p in old["paths"] if p["id"] == ref["path_id"]), None)
            if (
                not path
                or ref["object_id"]
                not in path["node_ids" if oid in node_ids else "edge_ids"]
            ):
                raise GraphError(
                    "Occurrence d’origine introuvable dans le DAG référencé."
                )
        q = meta["quote"]
        if q["start"] is not None and not quote_valid(meta, response):
            raise GraphError(
                "La position de la citation ne correspond pas au texte exact de cette réponse."
            )
        if meta["review"] in {"expressed", "withdrawn"} and not quote_valid(
            meta, response
        ):
            raise GraphError(
                "Une attribution à cette réponse nécessite une citation exacte."
            )
    return doc
