"""Configured visual coding entry point."""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from app_config import boot_environment  # noqa: E402

if os.environ.get("HANDCODING_SKIP_BOOT") != "1":
    boot_environment(ROOT)
    os.environ["HANDCODING_SKIP_BOOT"] = "1"
from graph_ui import run_workspace  # noqa: E402

run_workspace(harmonization=True)
