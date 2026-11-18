"""Small, local-only configuration window. No API request is made here."""

from __future__ import annotations

import argparse
import base64
import json
import os
import secrets
import socket
import sqlite3
import subprocess
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from app_config import (
    DEFAULTS,
    atomic_write,
    check_database_input,
    ensure_layout,
    env_text,
    locations,
    read_values,
    validate,
    validate_csv,
)

UI = Path(__file__).parent / "setup_ui"


class Setup:
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        self.token = secrets.token_urlsafe(32)
        self.lock = threading.Lock()
        self.last_activity = time.monotonic()

    def metadata(self):
        warning = ""
        try:
            values = read_values(self.root)
        except ValueError:
            values = read_values(self.root, strict=False)
            warning = "Certains réglages du .env sont invalides. Corrigez les champs ci-dessous, puis enregistrez."
        paths = locations(self.root)
        private = values.pop("OPENAI_API_KEY")
        return {
            "values": values,
            "warning": warning,
            "key_available": bool(
                private or os.environ.get("OPENAI_API_KEY", "").strip()
            ),
            "local_key": bool(private),
            "input_present": paths["input"].is_file(),
            "input_folder": str(paths["input"].parent),
            "output_folder": str(self.root / "outputs"),
            "configured": (self.root / ".env").is_file(),
        }

    def save(self, data):
        if not isinstance(data, dict) or set(data) - {
            "values",
            "key_action",
            "new_key",
            "file",
            "later",
        }:
            raise ValueError("Configuration invalide.")
        current = read_values(self.root, strict=False)
        supplied = data.get("values")
        if (
            not isinstance(supplied, dict)
            or set(supplied) != set(DEFAULTS) - {"OPENAI_API_KEY"}
            or any(not isinstance(v, str) for v in supplied.values())
        ):
            raise ValueError("Renseignez les paramètres de configuration.")
        values = {**current, **supplied}
        action = data.get("key_action", "keep")
        if action == "replace":
            key = data.get("new_key")
            if not isinstance(key, str) or not key.strip():
                raise ValueError("Saisissez la clé privée dans le champ prévu.")
            values["OPENAI_API_KEY"] = key.strip()
        elif action == "environment":
            values["OPENAI_API_KEY"] = ""
        elif action != "keep":
            raise ValueError("Choix de clé API invalide.")
        validate(values)
        if values["HANDCODING_AI_ENABLED"] == "1" and not (
            values["OPENAI_API_KEY"] or os.environ.get("OPENAI_API_KEY", "").strip()
        ):
            raise ValueError(
                "Ajoutez une clé privée ou désactivez l’assistance IA pour le moment."
            )
        paths = locations(self.root)
        upload = data.get("file")
        payload = None
        if upload is not None:
            if (
                not isinstance(upload, dict)
                or set(upload) != {"name", "content"}
                or not isinstance(upload["name"], str)
                or not upload["name"].lower().endswith(".csv")
                or not isinstance(upload["content"], str)
            ):
                raise ValueError("Déposez un fichier CSV dans la zone d’import.")
            try:
                payload = base64.b64decode(upload["content"], validate=True)
            except (ValueError, TypeError):
                raise ValueError(
                    "Le transfert du fichier a échoué. Sélectionnez-le à nouveau."
                ) from None
            rows = validate_csv(payload)
            check_database_input(paths["database"], rows)
            if paths["input"].is_file() and paths["input"].read_bytes() != payload:
                # A running app retains the source text in memory. Do not replace
                # it underneath an active coding/harmonization session.
                for key in ["HANDCODING_CODING_PORT", "HANDCODING_HARMONIZATION_PORT"]:
                    with socket.socket() as probe:
                        try:
                            probe.bind(("127.0.0.1", int(current[key])))
                        except OSError:
                            raise ValueError(
                                "Fermez le codage et l’harmonisation avant de remplacer les interviews, puis réessayez."
                            ) from None
        if (
            payload is None
            and not paths["input"].exists()
            and data.get("later") is not True
        ):
            raise ValueError(
                "Ajoutez les interviews ou choisissez « Ajouter la base plus tard »."
            )
        paths = ensure_layout(self.root, values)
        if payload is not None:
            atomic_write(paths["input"], payload)
        atomic_write(self.root / ".env", env_text(values).encode("utf-8"))
        return {
            "saved": True,
            "input_present": paths["input"].is_file(),
            "input_folder": str(paths["input"].parent),
            "output_folder": str(self.root / "outputs"),
        }


def handler_for(setup):
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(20)

        def log_message(self, *args):
            pass  # Never log bodies, credentials, tokens or interview text.

        def send(self, code, payload, content_type="application/json; charset=utf-8"):
            if isinstance(payload, dict):
                payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            )
            self.end_headers()
            self.wfile.write(payload)

        def authorized(self, post=False):
            host = f"127.0.0.1:{self.server.server_port}"
            if self.headers.get("Host") != host or not self.path.startswith(
                "/" + setup.token + "/"
            ):
                return False
            if self.headers.get("Origin") not in {None, "http://" + host}:
                return False
            if self.headers.get("Sec-Fetch-Site") not in {None, "same-origin", "none"}:
                return False
            if post and not secrets.compare_digest(
                self.headers.get("X-Setup-Token", ""), setup.token
            ):
                return False
            setup.last_activity = time.monotonic()
            return True

        def do_GET(self):
            if not self.authorized():
                self.send(403, {"error": "Accès non autorisé."})
                return
            route = self.path[len(setup.token) + 2 :]
            if route in {"", "app.js", "style.css"}:
                name = route or "index.html"
                kind = {
                    "index.html": "text/html",
                    "app.js": "text/javascript",
                    "style.css": "text/css",
                }[name]
                self.send(200, (UI / name).read_bytes(), kind + "; charset=utf-8")
            elif route == "icon.svg":
                self.send(
                    200,
                    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect x="4" y="6" width="24" height="20" rx="3" fill="white" stroke="black" stroke-width="2"/></svg>',
                    "image/svg+xml",
                )
            elif route == "api/settings":
                try:
                    self.send(200, setup.metadata())
                except (OSError, ValueError):
                    self.send(
                        400,
                        {
                            "error": "Le fichier .env est illisible ou invalide. Vérifiez ses paramètres avec le modèle .env.example."
                        },
                    )
            else:
                self.send(404, {"error": "Page inconnue."})

        def do_POST(self):
            if not self.authorized(post=True):
                self.send(403, {"error": "Accès non autorisé."})
                return
            if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                self.send(415, {"error": "Format de requête invalide."})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 29 * 1024 * 1024:
                    raise ValueError("Le fichier transféré est trop volumineux.")
                data = json.loads(self.rfile.read(length))
                route = self.path[len(setup.token) + 2 :]
                with setup.lock:
                    if route == "api/save":
                        result = setup.save(data)
                    elif route == "api/open-folder":
                        if data not in [{"folder": "input"}, {"folder": "outputs"}]:
                            raise ValueError("Dossier inconnu.")
                        paths = ensure_layout(setup.root, read_values(setup.root))
                        path = (
                            paths["input"].parent
                            if data["folder"] == "input"
                            else setup.root / "outputs"
                        )
                        subprocess.Popen(
                            ["/usr/bin/open", str(path)],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        result = {"opened": True}
                    elif route == "api/close":
                        result = {"closed": True}
                        threading.Thread(
                            target=self.server.shutdown, daemon=True
                        ).start()
                    else:
                        self.send(404, {"error": "Action inconnue."})
                        return
                self.send(200, result)
            except (ValueError, TypeError, UnicodeError) as exc:
                self.send(
                    400,
                    {
                        "error": str(exc)
                        if not isinstance(exc, json.JSONDecodeError)
                        else "Requête mal formée."
                    },
                )
            except (OSError, sqlite3.Error):
                self.send(
                    500,
                    {
                        "error": "Enregistrement impossible. Vérifiez que le volume est monté et accessible en écriture. Aucun codage n’est supprimé."
                    },
                )

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--app-dir", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    setup = Setup(args.app_dir)
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(setup))
    server.daemon_threads = True
    url = f"http://127.0.0.1:{server.server_port}/{setup.token}/"

    def expire():
        while not stopped.wait(15):
            if time.monotonic() - setup.last_activity > 1800:
                server.shutdown()
                return

    stopped = threading.Event()
    threading.Thread(target=expire, daemon=True).start()
    print("Configuration privée, sur ce Mac uniquement :", url, flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stopped.set()
        server.server_close()


if __name__ == "__main__":
    main()
