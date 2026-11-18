"""Private local settings shared by setup, coding, harmonization and statistics.

The .env file is data: it is never sourced or executed by a shell.
"""

from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path

DEFAULTS = {
    "HANDCODING_AUTHORS": "AuthorX,AuthorY,AuthorZ",
    "HANDCODING_AUTHOR": "AuthorX",
    "HANDCODING_AI_ENABLED": "0",
    "HANDCODING_AI_MODEL": "gpt-6.1-sol",
    "HANDCODING_CODING_PORT": "8541",
    "HANDCODING_HARMONIZATION_PORT": "8542",
    "OPENAI_API_KEY": "",
}
COMMENTS = {
    "HANDCODING_AUTHORS": "Noms des codeurs, séparés par des virgules. Un changement de nom ne renomme pas les anciens codages.",
    "HANDCODING_AUTHOR": "Codeur sélectionné par défaut ; doit appartenir à la liste ci-dessus.",
    "HANDCODING_AI_ENABLED": "1 affiche l’assistance IA à la demande ; 0 la désactive. Aucun appel au démarrage.",
    "HANDCODING_AI_MODEL": "Modèle utilisé pour les recommandations IA.",
    "HANDCODING_CODING_PORT": "Port local du codage.",
    "HANDCODING_HARMONIZATION_PORT": "Port local de l’harmonisation ; différent de celui du codage.",
    "OPENAI_API_KEY": "Clé privée facultative. Vide : utiliser celle de l’environnement du Mac. Ne jamais publier ce fichier.",
}


def slug(name):
    return re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_") or "AuthorX"


def validate(values):
    authors = [v.strip() for v in values["HANDCODING_AUTHORS"].split(",") if v.strip()]
    if not authors or len(authors) > 50:
        raise ValueError("Indiquez entre 1 et 50 codeurs, séparés par des virgules.")
    if any(
        len(n) > 64 or not n.isprintable() or n.casefold() == "harmonized"
        for n in authors
    ):
        raise ValueError(
            "Les noms doivent être lisibles, de 64 caractères maximum. Harmonized est réservé."
        )
    if len({slug(n).casefold() for n in authors}) != len(authors):
        raise ValueError(
            "Deux noms de codeur produisent le même nom de dossier. Différenciez-les."
        )
    if values["HANDCODING_AUTHOR"] not in authors:
        raise ValueError("Choisissez le codeur par défaut dans la liste des codeurs.")
    if values["HANDCODING_AI_ENABLED"] not in {"0", "1"}:
        raise ValueError("L’option IA doit valoir 0 ou 1.")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,120}", values["HANDCODING_AI_MODEL"]):
        raise ValueError("Nom de modèle invalide.")
    ports = []
    for key in ["HANDCODING_CODING_PORT", "HANDCODING_HARMONIZATION_PORT"]:
        value = values[key]
        if (
            not value.isascii()
            or not value.isdigit()
            or not 1024 <= int(value) <= 65535
        ):
            raise ValueError(
                "Les ports doivent être des nombres compris entre 1024 et 65535."
            )
        ports.append(int(value))
    if ports[0] == ports[1]:
        raise ValueError(
            "Le codage et l’harmonisation doivent avoir des ports différents."
        )
    key = values["OPENAI_API_KEY"]
    if key and (
        len(key) > 1024 or any(c.isspace() or not c.isprintable() for c in key)
    ):
        raise ValueError("La clé API contient des caractères non autorisés.")
    return authors


def read_values(root, environ=None, strict=True):
    env = os.environ if environ is None else environ
    values = {
        k: str(env.get(k, v)) if k != "OPENAI_API_KEY" else ""
        for k, v in DEFAULTS.items()
    }
    file = Path(root) / ".env"
    if file.is_symlink():
        raise ValueError("Le fichier .env ne doit pas être un lien symbolique.")
    if file.exists():
        if file.stat().st_size > 65536:
            raise ValueError("Le fichier .env est trop volumineux.")
        seen = set()
        for number, line in enumerate(
            file.read_text(encoding="utf-8-sig").splitlines(), 1
        ):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            name, separator, value = line.partition("=")
            name, value = name.strip(), value.strip()
            if not separator or name not in DEFAULTS or name in seen:
                if strict:
                    raise ValueError(
                        f"Ligne {number} du .env invalide ou variable non reconnue. Ouvrez Configurer.command."
                    )
                continue
            seen.add(name)
            if value.startswith('"'):
                try:
                    value = json.loads(value)
                except (ValueError, TypeError):
                    if strict:
                        raise ValueError(
                            f"Guillemets invalides à la ligne {number} du .env."
                        ) from None
                    continue
            if (
                not isinstance(value, str)
                or "\n" in value
                or "\r" in value
                or "\x00" in value
            ):
                if strict:
                    raise ValueError(f"Valeur invalide à la ligne {number} du .env.")
                continue
            values[name] = value
    if strict:
        validate(values)
    return values


def env_text(values):
    validate(values)
    lines = [
        "# Configuration privée — modifiable avec Configurer.command.",
        "# Valeurs entre guillemets doubles ; aucune commande shell n’est exécutée.",
        "",
    ]
    for key in DEFAULTS:
        lines.extend(
            [
                "# " + COMMENTS[key],
                key + "=" + json.dumps(values[key], ensure_ascii=False),
                "",
            ]
        )
    return "\n".join(lines)


def private_path(root, relative):
    root = Path(root).resolve()
    path = root / relative
    if not path.is_relative_to(root):
        raise ValueError("Emplacement privé invalide.")
    for parent in [path, *path.parents]:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError(
                "Les dossiers de données ne doivent pas contenir de liens symboliques."
            )
    return path


def locations(root):
    return {
        "input": private_path(root, "data/interviews/interviews.csv"),
        "database": private_path(root, "outputs/database/visual_coding.sqlite3"),
        "coding": private_path(root, "outputs/coding"),
        "analyses": private_path(root, "outputs/analyses_dags"),
    }


def ensure_layout(root, values):
    paths = locations(root)
    folders = [
        private_path(root, "data"),
        private_path(root, "outputs"),
        paths["input"].parent,
        paths["database"].parent,
        paths["coding"],
        paths["analyses"],
    ]
    for author in validate(values) + ["Harmonized"]:
        folders.extend(
            [paths["coding"] / slug(author), paths["analyses"] / slug(author)]
        )
    for folder in folders:
        private_path(root, str(folder.relative_to(Path(root).resolve())))
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    return paths


def atomic_write(path, payload):
    path = Path(path)
    if path.is_symlink():
        raise ValueError(
            "Le fichier de destination ne doit pas être un lien symbolique."
        )
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix=".configuration-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def validate_csv(payload):
    if not payload or len(payload) > 20 * 1024 * 1024:
        raise ValueError("Choisissez un CSV non vide, de 20 Mo maximum.")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ValueError("Le CSV doit être enregistré en UTF-8.") from None
    required = {
        "PID",
        "pair_id_interview",
        "pair_order_interview",
        "question",
        "response",
    }
    selected = required | {"interview_id"}
    csv.field_size_limit(20 * 1024 * 1024)
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        columns = reader.fieldnames or []
        if not required <= set(columns) or len(set(columns)) != len(columns):
            raise ValueError(
                "Colonnes requises : PID, pair_id_interview, pair_order_interview, question, response. Séparateur : virgule."
            )
        if {"phase", "phase_num", "pair_id_phase", "pair_order_in_phase"} & set(
            columns
        ):
            raise ValueError(
                "Cette application attend des interviews sans colonnes de phase."
            )
        rows, ids, orders = [], set(), set()
        for original in reader:
            # Personal identifier columns are never selected or used.
            row = {k: original.get(k, "") for k in selected}
            if any(v is None for v in row.values()) or None in original:
                raise ValueError(
                    "Une ligne du CSV ne contient pas le nombre attendu de champs."
                )
            pid, pair = row["PID"].strip(), row["pair_id_interview"].strip()
            order = row["pair_order_interview"].strip()
            if (
                not pid
                or not pair
                or pair in ids
                or not order.isascii()
                or not order.isdigit()
                or int(order) < 1
            ):
                raise ValueError(
                    "Vérifiez les identifiants de paires et leur ordre : ils doivent être renseignés, uniques et positifs."
                )
            position = (pid, row.get("interview_id", ""), int(order))
            if position in orders:
                raise ValueError(
                    "Deux paires occupent la même position dans un entretien."
                )
            ids.add(pair)
            orders.add(position)
            rows.append(
                (
                    row["pair_id_interview"],
                    row["PID"],
                    row.get("interview_id", ""),
                    int(order),
                    row["question"],
                    row["response"],
                )
            )
    except csv.Error:
        raise ValueError(
            "Le CSV est mal formé. Vérifiez son format et les guillemets."
        ) from None
    if not rows:
        raise ValueError("Le fichier ne contient aucune paire de question-réponse.")
    return rows


def check_database_input(database, rows):
    """Refuse replacing interviews already referenced by coding; never reset coding."""
    if not database.exists():
        return
    from urllib.parse import quote

    with closing(
        sqlite3.connect("file:" + quote(str(database)) + "?mode=ro", uri=True)
    ) as db:
        tables = {
            r[0]
            for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        if "interview_pairs" not in tables:
            raise ValueError(
                "Base de codage non reconnue ; aucune modification effectuée."
            )
        registered = [
            tuple(r)
            for r in db.execute(
                "SELECT pair_id,participant,interview_id,pair_order,question,response FROM interview_pairs"
            )
        ]
        if registered and not set(registered) <= set(rows):
            raise ValueError(
                "Ce fichier diffère des interviews déjà enregistrées dans la base de codage. Pour une autre étude, utilisez une copie vierge de l’application ; la base actuelle est conservée."
            )


def boot_environment(root):
    values = read_values(root)
    for key, value in values.items():
        if key == "OPENAI_API_KEY" and not value:
            continue  # Keep an existing Mac environment key, without persisting it.
        os.environ[key] = value
    paths = locations(root)
    os.environ.update(
        CODING_INTERVIEW_BASE=str(paths["input"]),
        INTERVIEW_OUTPUT_DIR=str(Path(root) / "outputs"),
        HANDCODING_GRAPH_DB=str(paths["database"]),
        PYTHONDONTWRITEBYTECODE="1",
    )
    return values, paths


def migrate_legacy(root, values, source=None, database=None):
    """Copy an existing study once. Caller must ensure the old app is closed."""
    paths = ensure_layout(root, values)
    payload = None
    if source and not paths["input"].exists():
        payload = Path(source).read_bytes()
        rows = validate_csv(payload)
        if database and Path(database).is_file():
            check_database_input(Path(database), rows)
    if database and Path(database).is_file() and not paths["database"].exists():
        from urllib.parse import quote

        fd, temp = tempfile.mkstemp(prefix=".migration-", dir=paths["database"].parent)
        os.close(fd)
        try:
            with (
                closing(
                    sqlite3.connect(
                        "file:" + quote(str(database)) + "?mode=ro", uri=True
                    )
                ) as old,
                closing(sqlite3.connect(temp)) as new,
            ):
                old.backup(new)
                if new.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise ValueError("La vérification de la base source a échoué.")
                before = old.execute("SELECT count(*) FROM revisions").fetchone()[0]
                if (
                    new.execute("SELECT count(*) FROM revisions").fetchone()[0]
                    != before
                ):
                    raise ValueError(
                        "La base a changé pendant la copie ; relancez après fermeture de l’application."
                    )
            os.replace(temp, paths["database"])
        finally:
            if os.path.exists(temp):
                os.unlink(temp)
    if payload is not None:
        atomic_write(paths["input"], payload)
    if paths["input"].is_file():
        check_database_input(
            paths["database"], validate_csv(paths["input"].read_bytes())
        )
    return paths
