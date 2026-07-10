from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

DENIED_EXTENSIONS = {
    ".csv",
    ".db",
    ".dta",
    ".feather",
    ".jsonl",
    ".parquet",
    ".rds",
    ".sav",
    ".sqlite",
    ".tsv",
    ".xls",
    ".xlsm",
    ".xlsx",
}

DENIED_NAME_FRAGMENTS = {
    "topics_harmonization",
    "coding_agreement_report",
    "llm_coding",
    "qa_handcoding_base",
    "qa_llm_coding_base",
    "participant",
    "transcript",
    "interview",
}

ALLOWED_PATHS = {
    "docs/coding_protocol.md",
    "docs/data_protection.md",
    "docs/harmonization_workflow.md",
}


def iter_candidate_files() -> list[Path]:
    if (ROOT / ".git").exists():
        result = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=False,
        )
        return [ROOT / item.decode("utf-8") for item in result.stdout.split(b"\0") if item]

    return [path for path in ROOT.rglob("*") if path.is_file() and ".git" not in path.parts]


def is_denied(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    name = path.name.lower()

    if relative in ALLOWED_PATHS:
        return False
    if path.suffix.lower() in DENIED_EXTENSIONS:
        return True
    return any(fragment in name for fragment in DENIED_NAME_FRAGMENTS)


def main() -> int:
    denied = sorted(path.relative_to(ROOT).as_posix() for path in iter_candidate_files() if is_denied(path))
    if denied:
        print("Privacy check failed. Remove or ignore these files before publishing:")
        for path in denied:
            print(f"- {path}")
        return 1

    print("Privacy check passed. No blocked data-like files were found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
