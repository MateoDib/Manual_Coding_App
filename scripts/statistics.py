"""Statistics entry point sharing the application's private configuration."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from app_config import boot_environment, ensure_layout

ROOT = Path(__file__).resolve().parents[1]


def main():
    values, _ = boot_environment(ROOT)
    ensure_layout(ROOT, values)
    return subprocess.call(
        [
            sys.executable,
            "-B",
            str(ROOT / "Descriptives_Statistics" / "compute.py"),
            *sys.argv[1:],
        ]
    )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(str(exc) + " Vérifiez Configurer.command.", file=sys.stderr)
        sys.exit(1)
