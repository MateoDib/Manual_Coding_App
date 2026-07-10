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
    "coding_interview_base",
    "harmonization_interview_base",
    "harmonized_interview_base",
    "topics_harmonization",
    "coding_agreement_report",
    "llm_coding",
    "qa_handcoding_base",
    "qa_llm_coding_base",
    "participant",
    "transcript",
}

DENIED_CONTENT_SNIPPETS = {
    "Question excerpt",
    "Response excerpt",
    "Bonjour, je suis un assistant IA chargé",
    "Not yet harmonized",
}

CONTENT_SCAN_EXEMPT_PATHS = {
    "scripts/privacy_check.py",
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


def contains_denied_content(path: Path) -> bool:
    relative = path.relative_to(ROOT).as_posix()
    if relative in CONTENT_SCAN_EXEMPT_PATHS:
        return False
    if path.suffix.lower() not in {".md", ".py", ".tex", ".txt", ".cff"}:
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return True
    return any(snippet in text for snippet in DENIED_CONTENT_SNIPPETS)


def is_denied(path: Path) -> bool:
    name = path.name.lower()
    if path.suffix.lower() in DENIED_EXTENSIONS:
        return True
    if any(fragment in name for fragment in DENIED_NAME_FRAGMENTS):
        return True
    return contains_denied_content(path)


def main() -> int:
    denied = sorted(path.relative_to(ROOT).as_posix() for path in iter_candidate_files() if is_denied(path))
    if denied:
        print("Privacy check failed. Remove or ignore these files before publishing:")
        for path in denied:
            print(f"- {path}")
        return 1

    print("Privacy check passed. No blocked data-like files or known sensitive excerpts were found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
