from __future__ import annotations

import os
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ANALYSIS_ROOT = Path(
    os.environ.get("PILOT_ANALYSIS_DIR", str(PROJECT_ROOT.parent))
).expanduser()
# Participant data live outside the Git repository. The application therefore
# remains publishable while the coding material stays private.
PRIVATE_OUTPUT_DIR = Path(
    os.environ.get("INTERVIEW_OUTPUT_DIR", PROJECT_ROOT / "outputs")
).expanduser()

QUESTION_COL = os.environ.get("TOPICS_QUESTION_COL", "question")
RESPONSE_COL = os.environ.get("TOPICS_RESPONSE_COL", "response")
HARMONIZED_COL = os.environ.get("TOPICS_HARMONIZED_COL", "Topics_Harmonized")

CODING_BASE_ENV_VAR = "CODING_INTERVIEW_BASE"
AUTHOR_NAMES_ENV_VAR = "HANDCODING_AUTHORS"
PREFERRED_AUTHOR_ENV_VAR = "HANDCODING_AUTHOR"
# Public, non-identifying defaults. Public users may edit this list or set the
# HANDCODING_AUTHORS environment variable; private projects should use a local
# launcher/configuration outside this repository.
PUBLIC_DEFAULT_AUTHOR_NAMES = ("AuthorX", "AuthorY", "AuthorZ")

DEFAULT_CODING_BASE = str(PROJECT_ROOT / "data/interviews/interviews.csv")

DAG_OPERATORS = ["-->", "=", ";", "+", "&", "<", ">", "|"]
DAG_OPERATORS_SET = set(DAG_OPERATORS)

REQUIRED_ENDING_NODES = []


def coding_base_path() -> Path:
    return Path(os.environ.get(CODING_BASE_ENV_VAR, DEFAULT_CODING_BASE)).expanduser()


def safe_author_name(value: str) -> str:
    """Return an unambiguous file-name and column suffix."""
    clean = re.sub(r"[^A-Za-z0-9_-]+", "_", str(value).strip())
    return clean.strip("_") or "AuthorX"


def configured_author_names() -> tuple[str, ...]:
    """Return the fixed author choices for the current app launch.

    By default, the public app displays ``AuthorX``, ``AuthorY`` and
    ``AuthorZ``. A private launcher can supply a comma-separated list through
    ``HANDCODING_AUTHORS``. Names are validated after filename normalisation so
    two labels can never resolve to the same coding workbook.
    """
    configured = os.environ.get(AUTHOR_NAMES_ENV_VAR, "").strip()
    raw_names = (
        configured.split(",") if configured else list(PUBLIC_DEFAULT_AUTHOR_NAMES)
    )
    names: list[str] = []
    safe_names: set[str] = set()
    for raw_name in raw_names:
        name = str(raw_name).strip()
        if not name:
            continue
        safe = safe_author_name(name)
        if safe in safe_names:
            raise ValueError(
                f"Duplicate author choice after normalisation: {name!r}. "
                f"Check {AUTHOR_NAMES_ENV_VAR}."
            )
        safe_names.add(safe)
        names.append(name)
    if not names:
        raise ValueError(
            f"{AUTHOR_NAMES_ENV_VAR} must contain at least one author name."
        )
    return tuple(names)


def preferred_author_name(author_names: tuple[str, ...]) -> str:
    """Use HANDCODING_AUTHOR only when it is one of the declared choices."""
    requested = os.environ.get(PREFERRED_AUTHOR_ENV_VAR, "").strip()
    if requested:
        requested_safe = safe_author_name(requested)
        for author in author_names:
            if safe_author_name(author) == requested_safe:
                return author
    return author_names[0]


def topic_column_for_author(author: str) -> str:
    return f"Topics_{safe_author_name(author)}"


def parse_token_list(value: str) -> list[str]:
    parts = re.split(r"[\n,;]+", str(value))
    return [normalize_topic(part) for part in parts if normalize_topic(part)]


def configured_required_ending_nodes() -> list[str]:
    enabled = os.environ.get("ENABLE_REQUIRED_ENDING_NODES", "0").strip().lower()
    if enabled in {"0", "false", "no", "off"}:
        return []
    configured = os.environ.get("REQUIRED_ENDING_NODES", "").strip()
    if configured:
        return parse_token_list(configured)
    return REQUIRED_ENDING_NODES.copy()


def normalize_topic(value: str) -> str:
    value = str(value).strip()
    if not value:
        return ""
    if value in DAG_OPERATORS_SET:
        return value
    value = value.lower()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("_,")
