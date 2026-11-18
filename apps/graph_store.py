"""Private transactional graph revisions and normalized scientific views."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

from graph_model import GraphError, document_digest, validate_document


class RevisionConflict(GraphError):
    pass


def dataset_identity(frame) -> str:
    """Stable across row reordering or moving the input workbook."""
    if "pair_id_interview" not in frame:
        raise GraphError("Le fichier doit contenir pair_id_interview.")
    ids = frame["pair_id_interview"].fillna("").astype(str).str.strip()
    if ids.eq("").any() or ids.duplicated().any():
        raise GraphError("pair_id_interview doit être renseigné et unique.")
    namespace = os.environ.get("HANDCODING_STUDY_ID", "climate_anxiety_v3")
    return hashlib.sha256(namespace.encode()).hexdigest()[:24]


def document_key(dataset: str, author: str, pair: str) -> str:
    return hashlib.sha256(
        json.dumps([dataset, author, str(pair)], ensure_ascii=False).encode()
    ).hexdigest()


class GraphStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Reject symlinks so a configured private store cannot clobber another file.
        if self.path.is_symlink():
            raise GraphError(
                "Le stockage graphique ne doit pas être un lien symbolique."
            )
        descriptor = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        os.close(descriptor)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS documents (
                    key TEXT PRIMARY KEY, dataset TEXT NOT NULL, author TEXT NOT NULL,
                    pair TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL,
                    digest TEXT NOT NULL, updated TEXT NOT NULL, projection_revision INTEGER NOT NULL DEFAULT 0,
                    UNIQUE(dataset, author, pair));
                CREATE TABLE IF NOT EXISTS revisions (
                    key TEXT NOT NULL, revision INTEGER NOT NULL, payload TEXT NOT NULL,
                    digest TEXT NOT NULL, updated TEXT NOT NULL, PRIMARY KEY(key, revision));
                CREATE TABLE IF NOT EXISTS requests (
                    request_id TEXT PRIMARY KEY, key TEXT NOT NULL, digest TEXT NOT NULL, revision INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS coding_events (key TEXT NOT NULL, revision INTEGER NOT NULL, action TEXT NOT NULL, PRIMARY KEY(key,revision));
                CREATE TABLE IF NOT EXISTS study_info (dataset TEXT PRIMARY KEY, scheme_version TEXT NOT NULL, scheme_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS interview_pairs (dataset TEXT NOT NULL, pair_id TEXT NOT NULL, participant TEXT NOT NULL, interview_id TEXT NOT NULL, pair_order INTEGER NOT NULL, question TEXT NOT NULL, response TEXT NOT NULL, response_digest TEXT NOT NULL, PRIMARY KEY(dataset,pair_id));
                CREATE TABLE IF NOT EXISTS analysis_runs (dataset TEXT NOT NULL, author TEXT NOT NULL, version TEXT NOT NULL, signature TEXT NOT NULL, PRIMARY KEY(dataset,author));
                CREATE TABLE IF NOT EXISTS ai_proposals (
                    id TEXT PRIMARY KEY, key TEXT NOT NULL, base_digest TEXT NOT NULL,
                    status TEXT NOT NULL, payload TEXT, created TEXT NOT NULL,
                    decision_revision INTEGER);
            """)

    @contextmanager
    def connection(self):
        # Never create a replacement empty database when a removable vault or
        # its existing database becomes unavailable during an editing session.
        db = sqlite3.connect(
            "file:" + quote(str(self.path.resolve())) + "?mode=rw", uri=True, timeout=8
        )
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=8000")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def get(self, key: str) -> dict | None:
        with self.connection() as db:
            row = db.execute("SELECT * FROM documents WHERE key=?", (key,)).fetchone()
            if row is None:
                return None
            value = dict(row)
            value["document"] = validate_document(json.loads(value.pop("payload")))
            return value

    def list_documents(self, dataset, author=None):
        with self.connection() as db:
            sql = "SELECT * FROM documents WHERE dataset=?"
            params = [dataset]
            if author is not None:
                sql += " AND author=?"
                params.append(author)
            return [
                self._decode(row)
                for row in db.execute(sql + " ORDER BY pair,author", params)
            ]

    @staticmethod
    def _decode(row):
        value = dict(row)
        value["document"] = validate_document(json.loads(value.pop("payload")))
        return value

    def register_pairs(self, dataset, canonical):
        from coding_scheme import SCHEME, SCHEME_VERSION
        from graph_evidence import text_digest

        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            old = {
                row["pair_id"]: dict(row)
                for row in db.execute(
                    "SELECT * FROM interview_pairs WHERE dataset=?", (dataset,)
                )
            }
            if set(old) - set(canonical.pair_id_interview.astype(str)):
                raise GraphError(
                    "Des paires déjà enregistrées ont disparu du fichier interviews.csv."
                )
            for _, row in canonical.iterrows():
                values = (
                    dataset,
                    str(row.pair_id_interview),
                    str(row.PID),
                    str(row.get("interview_id", "")),
                    int(row.pair_order_interview),
                    str(row.question),
                    str(row.response),
                    text_digest(str(row.response)),
                )
                if (
                    values[1] in old
                    and tuple(
                        old[values[1]][k]
                        for k in [
                            "dataset",
                            "pair_id",
                            "participant",
                            "interview_id",
                            "pair_order",
                            "question",
                            "response",
                            "response_digest",
                        ]
                    )
                    != values
                ):
                    raise GraphError(
                        "Une paire existante a changé. Conservez la version source et vérifiez les codages avant une migration."
                    )
                db.execute(
                    "INSERT OR IGNORE INTO interview_pairs VALUES (?,?,?,?,?,?,?,?)",
                    values,
                )
            from scientific_schema import ensure_analysis_schema

            ensure_analysis_schema(db)
            if len(old) != len(canonical):
                db.execute("DELETE FROM analysis_runs WHERE dataset=?", (dataset,))
            scheme = db.execute(
                "SELECT scheme_version FROM study_info WHERE dataset=?", (dataset,)
            ).fetchone()
            if scheme and scheme["scheme_version"] != SCHEME_VERSION:
                raise GraphError(
                    "Le coding scheme enregistré diffère de cette version de l’application."
                )
            db.execute(
                "INSERT OR IGNORE INTO study_info VALUES (?,?,?)",
                (
                    dataset,
                    SCHEME_VERSION,
                    json.dumps(SCHEME, ensure_ascii=False, sort_keys=True),
                ),
            )

    @staticmethod
    def _canonical(db, dataset):
        import pandas as pd

        rows = [
            dict(r)
            for r in db.execute(
                "SELECT participant AS PID,interview_id,pair_id AS pair_id_interview,pair_order AS pair_order_interview,question,response FROM interview_pairs WHERE dataset=? ORDER BY participant,interview_id,pair_order",
                (dataset,),
            )
        ]
        return pd.DataFrame(
            rows,
            columns=[
                "PID",
                "interview_id",
                "pair_id_interview",
                "pair_order_interview",
                "question",
                "response",
            ],
        )

    @staticmethod
    def _reader(db):
        class Reader:
            def current_document(self, key):
                row = db.execute(
                    "SELECT * FROM documents WHERE key=?", (key,)
                ).fetchone()
                return GraphStore._decode(row) if row else None

            get = current_document

            def historical_document(self, key, revision):
                row = db.execute(
                    "SELECT payload FROM revisions WHERE key=? AND revision=?",
                    (key, revision),
                ).fetchone()
                if not row:
                    raise GraphError("Révision d’origine introuvable.")
                return validate_document(json.loads(row["payload"]))

        return Reader()

    def analysis_current(self, dataset, author):
        with self.connection() as db:
            row = db.execute(
                "SELECT version FROM analysis_runs WHERE dataset=? AND author=?",
                (dataset, author),
            ).fetchone()
            return bool(row and row["version"] == "3.0.0")

    def analyze_snapshot(self, dataset, author):
        from graph_metrics import analyze

        with self.connection() as db:
            db.execute("BEGIN")
            canonical = self._canonical(db, dataset)
            records = [
                self._decode(r)
                for r in db.execute(
                    "SELECT * FROM documents WHERE dataset=? AND author=? ORDER BY pair",
                    (dataset, author),
                )
            ]
            result = analyze(canonical, records, self._reader(db))
            return canonical, records, result

    def refresh_analysis(self, dataset, author):
        from graph_metrics import TABLE_COLUMNS, analyze
        from scientific_schema import ensure_analysis_schema

        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            ensure_analysis_schema(db)
            canonical = self._canonical(db, dataset)
            records = [
                self._decode(r)
                for r in db.execute(
                    "SELECT * FROM documents WHERE dataset=? AND author=? ORDER BY pair",
                    (dataset, author),
                )
            ]
            result = analyze(canonical, records, self._reader(db))
            for name, columns in TABLE_COLUMNS.items():
                db.execute(
                    "DELETE FROM analysis_" + name + " WHERE dataset=? AND author=?",
                    (dataset, author),
                )
                sql = (
                    "INSERT INTO analysis_"
                    + name
                    + " ("
                    + ",".join(["dataset", "author"] + columns)
                    + ") VALUES ("
                    + ",".join("?" for _ in range(len(columns) + 2))
                    + ")"
                )
                db.executemany(
                    sql,
                    [
                        (dataset, author, *[r.get(c) for c in columns])
                        for r in result[name]
                    ],
                )
            signature = hashlib.sha256(
                json.dumps([(r["key"], r["revision"]) for r in records]).encode()
            ).hexdigest()
            db.execute(
                "INSERT INTO analysis_runs VALUES (?,?,?,?) ON CONFLICT(dataset,author) DO UPDATE SET version=excluded.version,signature=excluded.signature",
                (dataset, author, "3.0.0", signature),
            )
            db.execute(
                "UPDATE documents SET projection_revision=revision WHERE dataset=? AND author=?",
                (dataset, author),
            )
        return result

    def save(
        self,
        dataset: str,
        author: str,
        pair: str,
        document: dict,
        expected_revision: int,
        request_id: str,
        *,
        proposal_id: str | None = None,
        reviewed_current_digest: str | None = None,
        action: str = "save",
    ) -> int:
        doc = validate_document(document)
        if not isinstance(action, str) or len(action) > 64:
            raise GraphError("Action de codage invalide.")
        if type(expected_revision) is not int or expected_revision < 0:
            raise GraphError("Révision invalide.")
        if not isinstance(request_id, str) or not 8 <= len(request_id) <= 100:
            raise GraphError("Identifiant de sauvegarde invalide.")
        key = document_key(dataset, author, pair)
        digest = document_digest(doc)
        payload = json.dumps(doc, ensure_ascii=False, sort_keys=True, allow_nan=False)
        now = datetime.now(UTC).isoformat()
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            from graph_workflow import validate_context

            canonical = self._canonical(db, dataset)
            if canonical.empty or str(pair) not in set(
                canonical.pair_id_interview.astype(str)
            ):
                raise GraphError(
                    "Enregistrez la source de cet entretien avant de sauvegarder le codage."
                )
            validate_context(
                doc, canonical, str(pair), self._reader(db), dataset, author
            )
            repeated = db.execute(
                "SELECT * FROM requests WHERE request_id=?", (request_id,)
            ).fetchone()
            if repeated:
                if repeated["key"] != key or repeated["digest"] != digest:
                    raise RevisionConflict(
                        "Une requête de sauvegarde a été réutilisée avec un contenu différent."
                    )
                return repeated["revision"]
            current = db.execute(
                "SELECT revision,digest,payload FROM documents WHERE key=?", (key,)
            ).fetchone()
            revision = current["revision"] if current else 0
            current_digest = (
                document_digest(json.loads(current["payload"])) if current else None
            )
            if proposal_id is not None:
                proposal = db.execute(
                    "SELECT status,base_digest FROM ai_proposals WHERE id=? AND key=?",
                    (proposal_id, key),
                ).fetchone()
                if not proposal or proposal["status"] != "pending":
                    raise GraphError(
                        "Cette proposition a déjà été traitée ou n’est plus disponible."
                    )
                if reviewed_current_digest is not None:
                    if current is None or reviewed_current_digest != current_digest:
                        raise RevisionConflict(
                            "Le graphe affiché a changé dans une autre session. Rechargez-le avant d'appliquer la proposition."
                        )
                elif current is None or proposal["base_digest"] not in {
                    current["digest"],
                    current_digest,
                }:
                    raise RevisionConflict(
                        "Le graphe a changé depuis la demande IA. Conservez vos modifications et demandez une nouvelle proposition."
                    )
            if revision != expected_revision and (
                current is None or current_digest != digest
            ):
                raise RevisionConflict(
                    "Ce graphe a été modifié dans une autre session. Exportez votre brouillon JSON puis rechargez la version enregistrée."
                )
            if current is None or current_digest != digest:
                revision += 1
                db.execute(
                    """INSERT INTO documents(key,dataset,author,pair,revision,payload,digest,updated)
                              VALUES (?,?,?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET
                              revision=excluded.revision,payload=excluded.payload,digest=excluded.digest,updated=excluded.updated""",
                    (key, dataset, author, str(pair), revision, payload, digest, now),
                )
                db.execute(
                    "INSERT INTO revisions VALUES (?,?,?,?,?)",
                    (key, revision, payload, digest, now),
                )
                db.execute("DELETE FROM analysis_runs WHERE dataset=?", (dataset,))
                db.execute(
                    "INSERT INTO coding_events VALUES (?,?,?)", (key, revision, action)
                )
            db.execute(
                "INSERT INTO requests VALUES (?,?,?,?)",
                (request_id, key, digest, revision),
            )
            if proposal_id is not None:
                db.execute(
                    "UPDATE ai_proposals SET status='accepted',decision_revision=? WHERE id=? AND key=?",
                    (revision, proposal_id, key),
                )
            return revision

    def publish(self, key: str, write_projection) -> None:
        """Serialize projections with graph writers, without rolling back a saved graph.

        A projection failure leaves projection_revision behind revision. A later
        retry regenerates from the current authoritative document.
        """
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT revision,payload FROM documents WHERE key=?", (key,)
            ).fetchone()
            if row is None:
                raise GraphError("Graphe introuvable.")
            write_projection(json.loads(row["payload"]), row["revision"])
            db.execute(
                "UPDATE documents SET projection_revision=? WHERE key=?",
                (row["revision"], key),
            )

    def history(self, key: str) -> list[dict]:
        with self.connection() as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT revision,updated,digest FROM revisions WHERE key=? ORDER BY revision DESC",
                    (key,),
                )
            ]

    def historical_document(self, key: str, revision: int) -> dict:
        with self.connection() as db:
            row = db.execute(
                "SELECT payload FROM revisions WHERE key=? AND revision=?",
                (key, revision),
            ).fetchone()
            if row is None:
                raise GraphError("Révision introuvable.")
            return validate_document(json.loads(row["payload"]))

    def claim_proposal(self, key: str, request: str, digest: str) -> bool:
        """Persist the attempt before crossing the network; never replay it."""
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            result = db.execute(
                "INSERT OR IGNORE INTO ai_proposals(id,key,base_digest,status,created) VALUES (?,?,?,'started',?)",
                (request, key, digest, datetime.now(UTC).isoformat()),
            )
            if result.rowcount == 1:
                db.execute(
                    "UPDATE ai_proposals SET status='superseded' WHERE key=? AND id!=? AND status IN ('started','pending')",
                    (key, request),
                )
            return result.rowcount == 1

    def complete_proposal(self, key: str, request: str, payload: dict | None):
        if payload is not None:
            validate_document(payload["document"])
        with self.connection() as db:
            db.execute(
                "UPDATE ai_proposals SET status=?,payload=? WHERE id=? AND key=? AND status='started'",
                (
                    "pending" if payload else "failed",
                    json.dumps(payload, ensure_ascii=False) if payload else None,
                    request,
                    key,
                ),
            )

    def proposal(self, key: str, request: str | None = None) -> dict | None:
        with self.connection() as db:
            row = db.execute(
                "SELECT * FROM ai_proposals WHERE key=?"
                + (" AND id=?" if request else " AND status='pending'")
                + " ORDER BY created DESC LIMIT 1",
                (key, request) if request else (key,),
            ).fetchone()
            if row is None or row["payload"] is None:
                return None
            result = dict(row)
            result.update(json.loads(result.pop("payload")))
            result["document"] = validate_document(result["document"])
            return result

    def decide_proposal(self, key: str, request: str, decision: str, revision: int):
        if decision not in {"accepted", "rejected"}:
            raise GraphError("Décision IA invalide.")
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            changed = db.execute(
                "UPDATE ai_proposals SET status=?,decision_revision=? WHERE id=? AND key=? AND status='pending'",
                (decision, revision, request, key),
            ).rowcount
            if not changed:
                existing = db.execute(
                    "SELECT status,decision_revision FROM ai_proposals WHERE id=? AND key=?",
                    (request, key),
                ).fetchone()
                if not existing or existing["status"] != decision:
                    raise GraphError(
                        "Cette proposition a déjà été traitée ou n’est plus disponible."
                    )


def atomic_workbook(frame, path: Path, sheets=None) -> None:
    """Use literal Excel cells (never formulas) and atomic replacement."""
    from openpyxl import Workbook

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise GraphError("Le classeur de sortie ne doit pas être un lien symbolique.")
    descriptor, name = tempfile.mkstemp(
        prefix=".graph-export-", suffix=".xlsx", dir=path.parent
    )
    try:
        os.chmod(name, 0o600)
        os.close(descriptor)
        book = Workbook()
        sheet = book.active
        long_text = []

        def put(row, col, value):
            import pandas as pd

            if value is None or (
                not isinstance(value, (dict, list)) and pd.isna(value)
            ):
                value = None
            if isinstance(value, str):
                if len(value) > 32767:
                    token = "__long_text_" + str(len(long_text) + 1) + "__"
                    long_text.append((sheet.title, row, col, token, value))
                    value = token
                cell = sheet.cell(row, col, value)
                cell.data_type = (
                    "s"  # Protect transcript and labels against formula injection.
                )
            else:
                sheet.cell(row, col, value)

        sheet.title = "coding"
        for title, table in [("coding", frame), *(sheets or {}).items()]:
            if title != "coding":
                sheet = book.create_sheet(title)
            sheet.freeze_panes = "A2"
            for j, col in enumerate(table.columns, 1):
                put(1, j, str(col))
            for i, row in enumerate(table.itertuples(index=False, name=None), 2):
                for j, value in enumerate(row, 1):
                    put(i, j, value)
            if len(table.columns):
                sheet.auto_filter.ref = sheet.dimensions
        if long_text:
            sheet = book.create_sheet("long_text")
            for j, title in enumerate(
                ["sheet", "row", "column", "token", "part", "text"], 1
            ):
                put(1, j, title)
            row_number = 2
            for title, row, col, token, value in long_text:
                for part, start in enumerate(range(0, len(value), 32000), 1):
                    for j, item in enumerate(
                        [title, row, col, token, part, value[start : start + 32000]], 1
                    ):
                        put(row_number, j, item)
                    row_number += 1
            sheet.freeze_panes = "A2"
        book.save(name)
        with open(name, "rb") as handle:
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
