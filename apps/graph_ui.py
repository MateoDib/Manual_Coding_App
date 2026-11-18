"""Shared Streamlit workflow for independent and harmonized visual coding."""

from __future__ import annotations

import base64
import hashlib
import os
import secrets
import sqlite3
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
from coding_utils import (
    HARMONIZED_COL,
    PRIVATE_OUTPUT_DIR,
    QUESTION_COL,
    RESPONSE_COL,
    coding_base_path,
    configured_author_names,
    configured_required_ending_nodes,
    preferred_author_name,
    topic_column_for_author,
)
from graph_evidence import text_digest
from graph_legacy import (
    import_sequence,
    legacy_projection,
    migration_document,
    split_items,
)
from graph_metrics import csv_archive, packed, workbook_bytes
from graph_model import (
    GraphError,
    document_digest,
    graph_warnings,
    load_document,
    semantic_equal,
    validate_document,
)
from graph_store import GraphStore, dataset_identity, document_key
from graph_tikz import (
    CompilationError,
    compile_pdf,
    pdf_preview_png,
    publication_bundle,
)
from graph_tracking import continue_from, continue_many, prepare
from graph_workflow import (
    previous_sources,
    selected_sources,
    validate_context,
)
from study_data import earlier_pairs, read_interviews

BUILD = Path(__file__).parent / "visual_component" / "build"
visual_component = (
    components.declare_component("narrative_visual_editor", path=str(BUILD))
    if BUILD.is_dir()
    else None
)


def ai_enabled() -> bool:
    return os.environ.get("HANDCODING_AI_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def earlier_for_ai(canonical, pair, frame, column, store, dataset, author):
    coded = frame.set_index("pair_id_interview")
    result = []
    for _, item in earlier_pairs(canonical, pair).iterrows():
        source = store.get(document_key(dataset, author, str(item.pair_id_interview)))
        graph = (
            source["document"]
            if source
            else migration_document(
                str(coded.loc[str(item.pair_id_interview)].get(column, ""))
            )
        )
        result.append(
            {
                "question": str(item[QUESTION_COL]),
                "response": str(item[RESPONSE_COL]),
                "document": graph,
            }
        )
    return result


def load_workspace(harmonization, author, canonical):
    # SQLite is authoritative in V3. Workbooks are generated only on demand.
    output = PRIVATE_OUTPUT_DIR / "database" / "visual_coding.sqlite3"
    column = HARMONIZED_COL if harmonization else topic_column_for_author(author)
    frame = canonical.copy()
    frame[column] = ""
    return frame, output, column


def write_projection(store, key, output, canonical, column, author):
    saved = store.get(key)
    store.refresh_analysis(saved["dataset"], author)
    st.session_state.pop("metrics_zip_" + author, None)


def _save(store, dataset, author, pair, doc, base, request, action="save"):
    return store.save(dataset, author, pair, doc, base, request, action=action)


def _handle_event(
    event,
    store,
    dataset,
    author,
    pair,
    key,
    output,
    canonical,
    column,
    state,
    ai_context_factory=None,
):
    if not isinstance(event, dict) or event.get("request_id") == state.get("ack"):
        return False
    if (
        state.get("client_session")
        and event.get("client_session") != state["client_session"]
    ):
        # A widget can retain its last command across a server/session restart.
        # Never replay that old acceptance/navigation against the new session.
        return False
    request = event.get("request_id")
    if not isinstance(request, str):
        return False
    try:
        if event.get("document_key") != key:
            raise GraphError("La sauvegarde ne correspond pas à la paire affichée.")
        allowed_actions = {
            "save",
            "validate",
            "next",
            "previous",
            "jump",
            "preview",
            "import_json",
            "import_sequence",
            "switch_author",
            "clone_previous",
            "clone_selected",
            "new_graph",
            "clone_coder",
            "restore_revision",
            "ai_request",
            "ai_accept",
            "ai_reject",
            "copy_selection",
            "paste_selection",
            "duplicate_selection",
        }
        action = event.get("action")
        if action not in allowed_actions:
            raise GraphError("Action inconnue.")
        if action.startswith("ai_") and not ai_enabled():
            raise GraphError("L’assistance IA est désactivée.")
        doc = validate_context(
            event.get("document"), canonical, pair, store, dataset, author
        )
        revision = _save(
            store,
            dataset,
            author,
            pair,
            doc,
            event.get("base_revision"),
            request,
            action="save",
        )
        state["selection_after_replace"] = None
        if action in {"copy_selection", "paste_selection", "duplicate_selection"}:
            from graph_clipboard import paste_selection, selected_nodes

            clip_key = document_key(dataset, author, "selection_clipboard")
            if action in {"copy_selection", "duplicate_selection"}:
                source = store.get(key)
                ids = selected_nodes(source["document"], event.get("node_ids"))
                clip = {"key": key, "revision": source["revision"], "node_ids": ids}
                if action == "copy_selection":
                    st.session_state[clip_key] = clip
            else:
                clip = st.session_state.get(clip_key)
                if not clip:
                    raise GraphError("Copiez d’abord une sélection de ce codeur.")
                source = store.get(clip["key"])
                if (
                    not source
                    or source["dataset"] != dataset
                    or source["author"] != author
                ):
                    raise GraphError("La sélection copiée n’est plus disponible.")
                source["document"] = store.historical_document(
                    clip["key"], clip["revision"]
                )
                source["revision"] = clip["revision"]
            if action != "copy_selection":
                inherited = source["pair"] in set(
                    earlier_pairs(canonical, pair).pair_id_interview.astype(str)
                )
                at = event.get("at")
                if action == "duplicate_selection" and at is None:
                    boxes = [
                        source["document"]["layout"]["nodes"][oid]
                        for oid in clip["node_ids"]
                    ]
                    at = {
                        "x": (
                            min(b["x"] for b in boxes)
                            + max(b["x"] + b["width"] for b in boxes)
                        )
                        / 2
                        + 35,
                        "y": (
                            min(b["y"] for b in boxes)
                            + max(b["y"] + b["height"] for b in boxes)
                        )
                        / 2
                        + 35,
                    }
                replacement, added = paste_selection(
                    doc, source, clip["node_ids"], at, inherited=inherited
                )
                validate_context(replacement, canonical, pair, store, dataset, author)
                revision = store.save(
                    dataset,
                    author,
                    pair,
                    replacement,
                    revision,
                    request + "-paste",
                    action=action,
                )
                state["replace"] = request
                state["selection_after_replace"] = added
        if action in {"validate", "next"}:
            candidate = prepare(doc)
            if candidate["status"] != "none":
                candidate["status"] = "coded"
            warnings = graph_warnings(candidate)
            if candidate["status"] == "none":
                warnings = [
                    w for w in warnings if not w.startswith("Le statut « aucun ajout »")
                ]
            if warnings:
                raise GraphError(
                    "Codage sauvegardé en brouillon. Vérifiez les points signalés avant validation, ou choisissez none si aucun ajout : "
                    + warnings[0]
                )
            revision = _save(
                store,
                dataset,
                author,
                pair,
                candidate,
                revision,
                request + "-validated",
                action="validate",
            )
            doc = candidate
            state["replace"] = request
        if action in ("import_json", "import_sequence"):
            if action == "import_json":
                content = event.get("import_json")
                if not isinstance(content, str):
                    raise GraphError("Fichier d'import invalide.")
                imported = load_document(content)
            else:
                content = event.get("import_text")
                if not isinstance(content, str):
                    raise GraphError("Notation d'import invalide.")
                imported = import_sequence(content)
            if (
                imported.get("tracking", {}).get("response_digest")
                != doc["tracking"]["response_digest"]
            ):
                imported.pop("tracking", None)
            imported = prepare(
                imported,
                key,
                response_digest=doc["tracking"]["response_digest"],
                origin="unknown",
            )
            validate_context(imported, canonical, pair, store, dataset, author)
            revision = _save(
                store,
                dataset,
                author,
                pair,
                imported,
                revision,
                request + "-import",
                action=action,
            )
            state["replace"] = request
        if action == "ai_request":
            from graph_ai import recommend

            if ai_context_factory is None:
                raise GraphError("Le contexte de codage n’est pas disponible.")
            context = ai_context_factory()
            if store.claim_proposal(key, request, document_digest(doc)):
                try:
                    with st.spinner("Préparation de la proposition IA…"):
                        proposal = recommend(context)
                    store.complete_proposal(key, request, proposal)
                except Exception:
                    store.complete_proposal(key, request, None)
                    raise
            state["ai_error"] = None
        if action in {"ai_accept", "ai_reject"}:
            proposal_id = event.get("proposal_id")
            if not isinstance(proposal_id, str):
                raise GraphError("Proposition IA inconnue.")
            proposal = store.proposal(key, proposal_id)
            expected = "accepted" if action == "ai_accept" else "rejected"
            if not proposal or proposal["status"] not in {"pending", expected}:
                raise GraphError("Cette proposition a déjà été traitée.")
            if proposal["status"] == expected:
                revision = store.get(key)["revision"]
                if action == "ai_accept":
                    state["replace"] = request
            elif action == "ai_reject":
                store.decide_proposal(key, proposal_id, "rejected", revision)
            else:
                replacement = validate_document(event.get("proposal_document"))
                replacement.pop("tracking", None)
                replacement = prepare(
                    replacement,
                    key,
                    response_digest=doc["tracking"]["response_digest"],
                    origin="unknown",
                )
                validate_context(replacement, canonical, pair, store, dataset, author)
                # Accepted suggestions are human-reviewed; provenance remains
                # linked to the immutable local AI audit record, without identity.
                replacement["provenance"]["parent"] = "ai:" + proposal_id
                revision = store.save(
                    dataset,
                    author,
                    pair,
                    replacement,
                    revision,
                    request + "-accept",
                    proposal_id=proposal_id,
                    reviewed_current_digest=document_digest(doc),
                    action="ai_accept",
                )
                state["replace"] = request
            state["ai_decision"] = {
                "id": proposal_id,
                "status": "accepted" if action == "ai_accept" else "rejected",
                "request_id": request,
            }
            state["ai_error"] = None
        if action in ("clone_previous", "clone_coder", "restore_revision"):
            if action == "restore_revision":
                chosen = event.get("revision")
                if type(chosen) is not int:
                    raise GraphError("Révision à restaurer invalide.")
                replacement = store.historical_document(key, chosen)
            elif action == "clone_coder":
                coder = event.get("coder")
                if author != "Harmonized" or coder not in configured_author_names():
                    raise GraphError(
                        "Ce codage individuel n'est pas disponible pour l'harmonisation."
                    )
                source = store.get(document_key(dataset, coder, pair))
                if not source or not source["document"]["nodes"]:
                    raise GraphError(
                        "Aucun DAG enregistré pour ce codeur dans cette paire."
                    )
                replacement = continue_from(
                    doc, source, [p["id"] for p in source["document"]["paths"]]
                )
                replacement["provenance"]["parent"] = f"coder:{coder};pair:{pair}"
            else:
                sources = previous_sources(
                    canonical, pair, store.list_documents(dataset, author)
                )
                sources = [source for source in sources if source["paths"]]
                if not sources:
                    raise GraphError(
                        "Aucun DAG précédent exploitable dans cet entretien."
                    )
                latest = sources[-1]
                if event.get("source_key") is not None and (
                    type(event.get("source_revision")) is not int
                    or event.get("source_key") != latest["key"]
                    or event.get("source_revision") != latest["revision"]
                ):
                    raise GraphError(
                        "Le DAG précédent a changé. Vérifiez la paire d’origine avant de reprendre."
                    )
                source = store.get(latest["key"])
                if not source or source["revision"] != latest["revision"]:
                    raise GraphError(
                        "Le DAG précédent vient de changer. Réessayez après vérification."
                    )
                replacement = continue_from(
                    doc, source, [p["id"] for p in sources[-1]["paths"]]
                )
            replacement = prepare(
                replacement,
                key,
                response_digest=doc["tracking"]["response_digest"],
            )
            validate_context(replacement, canonical, pair, store, dataset, author)
            revision = _save(
                store,
                dataset,
                author,
                pair,
                replacement,
                revision,
                request + "-replace",
                action=action,
            )
            state["replace"] = request
        if action in {"clone_selected", "new_graph"}:
            if action == "new_graph":
                from graph_model import empty_document

                replacement = prepare(
                    empty_document(),
                    key,
                    response_digest=doc["tracking"]["response_digest"],
                )
            else:
                choices = previous_sources(
                    canonical, pair, store.list_documents(dataset, author)
                )
                selections = selected_sources(event, choices, store)
                if (
                    type(event.get("append", False)) is not bool
                    or type(event.get("origin_only", False)) is not bool
                ):
                    raise GraphError("Mode de reprise invalide.")
                replacement = continue_many(
                    doc,
                    selections,
                    append=event.get("append", False),
                    origin_only=event.get("origin_only", False),
                )
            validate_context(replacement, canonical, pair, store, dataset, author)
            revision = _save(
                store,
                dataset,
                author,
                pair,
                replacement,
                revision,
                request + "-v3",
                action=action,
            )
            state["replace"] = request
        state.update(ack=request, error=None, revision=revision)
        try:
            write_projection(store, key, output, canonical, column, author)
            state["projection_error"] = None
        except (OSError, ValueError, GraphError) as exc:
            state["projection_error"] = (
                "Graphe enregistré ; les tables scientifiques restent à actualiser. "
                + str(exc)
            )
            # Navigation waits until the projection is repaired or retried.
            return True
        if action == "preview":
            state["preview_requested"] = True
        if action == "switch_author":
            target_author = event.get("author")
            if target_author not in configured_author_names():
                raise GraphError("Auteur inconnu.")
            st.session_state["visual_author"] = target_author
        if action in ("next", "previous", "jump"):
            row = st.session_state.get("visual_row", 0)
            target = (
                (row + 1 if action == "next" else row - 1)
                if action != "jump"
                else event.get("row")
            )
            if type(target) is not int:
                raise GraphError("Numéro de réponse invalide.")
            st.session_state["visual_row"] = max(0, min(len(canonical) - 1, target))
        return True
    except (GraphError, OSError, ValueError, TypeError, sqlite3.Error) as exc:
        state.update(ack=request, error=str(exc))
        if event.get("action", "").startswith("ai_"):
            state["ai_error"] = str(exc)
        return True


def run_workspace(harmonization: bool = False):
    st.set_page_config(
        page_title="Harmonisation V3" if harmonization else "Codage V3",
        layout="wide",
    )
    st.html("""<style>
    .stMainBlockContainer {padding: .7rem 1rem 1rem; max-width: 100%;}
    [data-testid="stHeader"] {height: 0; visibility: hidden;}
    [data-testid="stMainBlockContainer"] > div {gap: .35rem;}
    </style>""")
    if visual_component is None:
        st.error(
            "Le composant précompilé est absent. Suivez la construction décrite dans README.md."
        )
        st.stop()
    try:
        authors = configured_author_names()
        author = (
            "Harmonized"
            if harmonization
            else st.session_state.get("visual_author", preferred_author_name(authors))
        )
        if not harmonization and author not in authors:
            author = authors[0]
        canonical = read_interviews(coding_base_path())
        dataset = dataset_identity(canonical)
        frame, output, column = load_workspace(harmonization, author, canonical)
        database = Path(
            os.environ.get(
                "HANDCODING_GRAPH_DB",
                str(PRIVATE_OUTPUT_DIR / "database" / "visual_coding.sqlite3"),
            )
        ).expanduser()
        public_root = Path(__file__).resolve().parents[1]
        if database.resolve().is_relative_to(
            public_root
        ) and not database.resolve().is_relative_to(public_root / "outputs"):
            raise GraphError(
                "Placez la base privée dans le sous-dossier outputs de l’application."
            )
        store = GraphStore(database)
        store.register_pairs(dataset, canonical)
        existing = store.list_documents(dataset, author)
        if existing and not store.analysis_current(dataset, author):
            store.refresh_analysis(dataset, author)
        for item in existing:
            status, text, _ = legacy_projection(item["document"])
            frame.loc[frame.pair_id_interview.astype(str).eq(item["pair"]), column] = (
                text
            )
    except (OSError, ValueError, GraphError, sqlite3.Error) as exc:
        st.error(str(exc))
        st.info(
            "Configurez PILOT_ANALYSIS_DIR avec un dossier privé contenant interviews.csv."
        )
        st.stop()
    if canonical.empty:
        st.info("La base ne contient aucune question-réponse.")
        st.stop()
    current_row = max(
        0, min(len(canonical) - 1, int(st.session_state.get("visual_row", 0)))
    )
    st.session_state["visual_row"] = current_row
    row = canonical.iloc[current_row]
    pair = str(row.pair_id_interview)
    key = document_key(dataset, author, pair)
    state = st.session_state.setdefault(
        "graph_state_" + key, {"ack": None, "error": None, "replace": "0"}
    )
    state["client_session"] = st.session_state.setdefault(
        "visual_client_session", secrets.token_urlsafe(24)
    )
    saved = store.get(key)
    from graph_model import empty_document

    document = prepare(
        saved["document"] if saved else empty_document(),
        key,
        response_digest=text_digest(str(row[RESPONSE_COL])),
    )
    revision = saved["revision"] if saved else 0
    source_docs = []
    if harmonization:
        for coder in authors:
            source_saved = store.get(document_key(dataset, coder, pair))
            if source_saved:
                source_docs.append((coder, source_saved["document"]))
    records = store.list_documents(dataset, author)
    sources = previous_sources(canonical, pair, records)
    _, records, analysis = store.analyze_snapshot(dataset, author)
    # Unsaved empty pairs still receive a useful, explicitly provisional panel.
    if pair not in analysis["details"]:
        raise GraphError("Suivi de la paire introuvable.")
    topics, subtopics, scopes = [], {}, []
    topic_labels = {}
    for item in store.list_documents(dataset):
        for node in item["document"]["nodes"]:
            if node["code"] and node["kind"] == "concept":
                topics.append(node["code"])
                subtopics[node["code"]] = sorted(
                    set(subtopics.get(node["code"], [])) | set(node["subtopics"])
                )
                scopes.extend(node["scopes"])
                if node["label"]:
                    topic_labels.setdefault(node["code"], set()).add(node["label"])
    topics = sorted(set(topics))
    scope_terms = set()
    for value in scopes:
        try:
            scope_terms.update(split_items(value))
        except GraphError:
            # Preserve an old malformed spelling for review; it must not stop
            # coding or make the entire stored vocabulary disappear.
            scope_terms.add(value)
    scopes = sorted(scope_terms)
    if state.get("projection_error"):
        st.warning(state["projection_error"])
        if st.button("Réactualiser les tables scientifiques"):
            try:
                write_projection(store, key, output, canonical, column, author)
                state["projection_error"] = None
                st.rerun()
            except (GraphError, OSError, ValueError) as exc:
                st.error(str(exc))
    digest = document_digest(document)
    if state.pop("preview_requested", False):
        try:
            with st.spinner("Compilation LaTeX locale…"):
                pdf = compile_pdf(document)
                png = pdf_preview_png(pdf)
            st.session_state["pdf_" + key] = (digest, pdf, png)
        except (CompilationError, OSError) as exc:
            state["error"] = str(exc)
    preview = st.session_state.get("pdf_" + key)
    use_ai = ai_enabled()
    ai_args = {}
    if use_ai:
        from graph_ai import DEFAULT_MODEL

        proposal = store.proposal(key)
        # The frozen audit context stays server-side. The review UI receives
        # only its graph and human-readable supporting information.
        visible_proposal = (
            {
                k: proposal[k]
                for k in (
                    "id",
                    "document",
                    "summary",
                    "uncertainties",
                    "evidence",
                    "model",
                    "status",
                    "base_digest",
                )
            }
            if proposal
            else None
        )
        ai_args = dict(
            ai_enabled=True,
            ai_ready=bool(os.environ.get("OPENAI_API_KEY", "").strip()),
            ai_model=os.environ.get("HANDCODING_AI_MODEL", DEFAULT_MODEL),
            ai_proposal=visible_proposal,
            ai_error=state.get("ai_error"),
            ai_decision=state.get("ai_decision"),
        )

    def ai_context_factory():
        from graph_ai import build_context

        return build_context(
            question=str(row[QUESTION_COL]),
            response=str(row[RESPONSE_COL]),
            vocabulary={
                "topics": sorted(set(topics) - {"none"}),
                "subtopics": subtopics,
                "scopes": scopes,
            },
            earlier=earlier_for_ai(
                canonical, pair, frame, column, store, dataset, author
            ),
        )

    event = visual_component(
        document=document,
        document_key=key,
        client_session=state["client_session"],
        revision=revision,
        ack=state.get("ack"),
        error=state.get("error"),
        replace_token=state["replace"],
        selection_after_replace=state.get("selection_after_replace"),
        clipboard_available=bool(
            st.session_state.get(document_key(dataset, author, "selection_clipboard"))
        ),
        topics=sorted(set(topics) - {"none"}),
        subtopics=subtopics,
        scopes=scopes,
        topic_labels={code: sorted(labels) for code, labels in topic_labels.items()},
        ending_nodes=configured_required_ending_nodes(),
        row=current_row,
        row_count=len(canonical),
        title=("Harmonisation" if harmonization else "Codage")
        + f" Climate Anxiety V3 · {author}",
        question=str(row[QUESTION_COL]),
        response=str(row[RESPONSE_COL]),
        response_digest=text_digest(str(row[RESPONSE_COL])),
        author=author,
        authors=[] if harmonization else list(authors),
        clone_authors=[coder for coder, _ in source_docs],
        history=store.history(key),
        can_clone_previous=any(source["paths"] for source in sources),
        previous_sources=sources,
        enrichment=analysis["details"][pair],
        read_only=False,
        warnings=graph_warnings(document),
        latex={
            **publication_bundle(document, revision, key),
            "pdf": base64.b64encode(preview[1]).decode("ascii") if preview else None,
            "preview": base64.b64encode(preview[2]).decode("ascii")
            if preview and len(preview) > 2
            else None,
            "current": bool(preview and preview[0] == digest),
        },
        **ai_args,
        key="visual_" + key,
        default=None,
    )
    if _handle_event(
        event,
        store,
        dataset,
        author,
        pair,
        key,
        output,
        canonical,
        column,
        state,
        ai_context_factory=ai_context_factory if use_ai else None,
    ):
        st.rerun()
    signature = hashlib.sha256(
        packed(
            {
                "revisions": [(r["key"], r["revision"]) for r in records],
                "pairs": list(canonical.pair_id_interview.astype(str)),
            }
        ).encode()
    ).hexdigest()
    with st.expander("Exporter les données scientifiques", expanded=False):
        st.caption(
            "SQLite conserve les codages et leurs révisions. Les exports sont créés uniquement à votre demande et portent sur les versions enregistrées du codeur actif."
        )
        if st.button(
            "Exporter le codage dans mon dossier", key="prepare_metrics_" + author
        ):
            st.session_state["metrics_zip_" + author] = (
                signature,
                csv_archive(analysis),
                workbook_bytes(analysis, canonical=canonical, records=records),
            )
            from app_config import atomic_write, slug

            local_export = PRIVATE_OUTPUT_DIR / "coding" / slug(author) / "coding.xlsx"
            atomic_write(local_export, st.session_state["metrics_zip_" + author][2])
            st.success("Classeur enregistré : " + str(local_export))
        archive = st.session_state.get("metrics_zip_" + author)
        if archive and archive[0] == signature:
            st.download_button(
                "Classeur de codage",
                data=archive[2],
                file_name="coding_v3_" + author + ".xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                on_click="ignore",
            )
            st.download_button(
                "Tables CSV",
                data=archive[1],
                file_name="coding_v3_" + author + ".zip",
                mime="application/zip",
                on_click="ignore",
            )
    if harmonization:
        with st.expander("Comparer les codages individuels", expanded=False):
            for coder, source in source_docs:
                equal = semantic_equal(document, source)
                st.write(f"**{coder}**")
                st.caption(
                    "Même structure sémantique (mise en page ignorée)."
                    if equal
                    else "Structure différente."
                    if equal is False
                    else "Comparaison complexe : examen manuel nécessaire."
                )
                visual_component(
                    document=source,
                    document_key=f"read_{key}_{coder}",
                    revision=0,
                    ack=None,
                    error=None,
                    replace_token="0",
                    topics=[],
                    subtopics={},
                    scopes=[],
                    ending_nodes=[],
                    row=current_row,
                    row_count=len(canonical),
                    title=f"Codage {coder}",
                    read_only=True,
                    key=f"read_{key}_{coder}",
                    default=None,
                )
