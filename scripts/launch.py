"""Local V3 launcher. Explicit paths; no release manifest or automatic export."""

from __future__ import annotations

import argparse
import errno
import os
import socket
import subprocess
import sys
from pathlib import Path

from app_config import boot_environment, ensure_layout

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["coding", "harmonization"])
    parser.add_argument("--analysis-dir", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--port", type=int)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    try:
        values, paths = boot_environment(ROOT)
        ensure_layout(ROOT, values)
    except (OSError, ValueError) as exc:
        parser.error(str(exc) + " Ouvrez Configurer.command.")
    source = (
        (args.analysis_dir.expanduser().resolve() / "interviews.csv")
        if args.analysis_dir
        else paths["input"]
    )
    output = (
        args.output_dir.expanduser().resolve() if args.output_dir else ROOT / "outputs"
    )
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT / "outputs"):
        parser.error("Choisissez le dossier outputs pour les résultats privés.")
    if not source.is_file():
        parser.error(
            "Les interviews ne sont pas encore ajoutées. Ouvrez Configurer.command ou placez interviews.csv dans "
            + str(paths["input"].parent)
        )
    env = os.environ.copy()
    env.update(
        PYTHONDONTWRITEBYTECODE="1",
        PILOT_ANALYSIS_DIR=str(ROOT),
        HANDCODING_SKIP_BOOT="1",
        CODING_INTERVIEW_BASE=str(source),
        INTERVIEW_OUTPUT_DIR=str(output),
        HANDCODING_GRAPH_DB=str(output / "database" / "visual_coding.sqlite3"),
    )
    if args.headless:
        env["STREAMLIT_SERVER_HEADLESS"] = "true"
    port = args.port or int(
        values[
            "HANDCODING_CODING_PORT"
            if args.mode == "coding"
            else "HANDCODING_HARMONIZATION_PORT"
        ]
    )
    if not 1024 <= port <= 65535:
        parser.error("Le port doit être compris entre 1024 et 65535.")
    with socket.socket() as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE:
                parser.error("Impossible d’ouvrir le port local : " + str(exc))
            print(
                f"Le port {port} est déjà utilisé. Si la V3 est ouverte, retrouvez-la à http://127.0.0.1:{port}/. Sinon, choisissez un autre port avec --port.",
                file=sys.stderr,
            )
            return 1
    app = (
        "manual_topic_coding_app.py"
        if args.mode == "coding"
        else "topic_harmonization_app.py"
    )
    return subprocess.call(
        [
            sys.executable,
            "-B",
            "-m",
            "streamlit",
            "run",
            str(ROOT / "apps" / app),
            "--server.address",
            "127.0.0.1",
            "--server.port",
            str(port),
            "--browser.gatherUsageStats",
            "false",
        ],
        env=env,
        cwd=ROOT,
    )


if __name__ == "__main__":
    sys.exit(main())
