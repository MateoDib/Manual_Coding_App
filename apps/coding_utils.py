from __future__ import annotations

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_WORKBOOK_DIR = Path(
    os.environ.get("INTERVIEW_WORKBOOK_DIR", PROJECT_ROOT / "private_workbooks")
).expanduser()

QUESTION_COL = os.environ.get("TOPICS_QUESTION_COL", "question")
RESPONSE_COL = os.environ.get("TOPICS_RESPONSE_COL", "response")
HARMONIZED_COL = os.environ.get("TOPICS_HARMONIZED_COL", "Topics_Harmonized")

CODING_BASE_ENV_VAR = "CODING_INTERVIEW_BASE"
HARMONIZATION_BASE_ENV_VAR = "HARMONIZATION_INTERVIEW_BASE"
HARMONIZED_BASE_ENV_VAR = "HARMONIZED_INTERVIEW_BASE"

DEFAULT_CODING_BASE = "coding_interview_base.xlsx"
DEFAULT_HARMONIZATION_BASE = "harmonization_interview_base.xlsx"
DEFAULT_HARMONIZED_BASE = "harmonized_interview_base.xlsx"

DAG_OPERATORS = ["-->", "=", ";", "+", "&", "<", ">", "|"]
DAG_OPERATORS_SET = set(DAG_OPERATORS)
BINARY_OPERATORS = {"-->", "=", "+", "&", "<", ">"}

REQUIRED_ENDING_NODES = [
    "acceptability",
    "unacceptability",
    "ambivalent_acceptability",
]

TOKEN_PATTERN = re.compile(r"(-->|[=;+&<>|])")
TOPIC_CHUNK_PATTERN = re.compile(r"[A-Za-z0-9_]+(?:\s*\([^)]*\))?(?:\[[^]]*\])?")

DAG_OPERATOR_LABELS = {
    "-->": "causal -->",
    "=": "definition =",
    ";": "path ;",
    "+": "add +",
    "&": "coexist &",
    "<": "priority <",
    ">": "priority >",
    "|": "source |",
}


def workbook_path(env_var: str, default_name: str) -> Path:
    configured = Path(os.environ.get(env_var, default_name)).expanduser()
    if configured.is_absolute():
        return configured
    return PRIVATE_WORKBOOK_DIR / configured


def coding_base_path() -> Path:
    return workbook_path(CODING_BASE_ENV_VAR, DEFAULT_CODING_BASE)


def harmonization_base_path() -> Path:
    return workbook_path(HARMONIZATION_BASE_ENV_VAR, DEFAULT_HARMONIZATION_BASE)


def harmonized_base_path() -> Path:
    return workbook_path(HARMONIZED_BASE_ENV_VAR, DEFAULT_HARMONIZED_BASE)


def configured_coder_columns() -> list[str]:
    """Return coder columns for one, two, or N coders.

    Configure either:
    - TOPICS_CODER_COLUMNS="Topics_Coder_1,Topics_Coder_2,..."
    - TOPICS_CODER_COUNT=3
    """
    explicit_columns = os.environ.get("TOPICS_CODER_COLUMNS", "").strip()
    if explicit_columns:
        columns = [col.strip() for col in explicit_columns.split(",") if col.strip()]
        if not columns:
            raise ValueError("TOPICS_CODER_COLUMNS was provided but contains no valid column names.")
        return columns

    raw_count = os.environ.get("TOPICS_CODER_COUNT", "3").strip()
    try:
        coder_count = int(raw_count)
    except ValueError as exc:
        raise ValueError("TOPICS_CODER_COUNT must be an integer.") from exc
    if coder_count < 1:
        raise ValueError("TOPICS_CODER_COUNT must be at least 1.")
    return [f"Topics_Coder_{i}" for i in range(1, coder_count + 1)]


def configured_coder_map() -> dict[str, str]:
    return {f"Coder {index}": column for index, column in enumerate(configured_coder_columns(), start=1)}


def parse_token_list(value: str) -> list[str]:
    parts = re.split(r"[\n,;]+", str(value))
    return [normalize_topic(part) for part in parts if normalize_topic(part)]


def configured_required_ending_nodes() -> list[str]:
    enabled = os.environ.get("ENABLE_REQUIRED_ENDING_NODES", "1").strip().lower()
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


def strip_wrapping(value: str, left: str, right: str) -> str:
    value = str(value).strip()
    if value.startswith(left) and value.endswith(right):
        return value[1:-1].strip()
    return value


def split_top_level_commas(value: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    depth = 0
    for char in str(value):
        if char == "(":
            depth += 1
            current.append(char)
        elif char == ")":
            depth = max(0, depth - 1)
            current.append(char)
        elif char == "," and depth == 0:
            part = "".join(current).strip()
            if part:
                parts.append(part)
            current = []
        else:
            current.append(char)
    part = "".join(current).strip()
    if part:
        parts.append(part)
    return parts


def normalize_parentheses_content(value: str) -> str:
    value = strip_wrapping(value, "(", ")")
    parts = [normalize_topic(part) for part in split_top_level_commas(value)]
    return ", ".join(part for part in parts if part)


def normalize_scope_part(value: str) -> str:
    value = str(value).strip()
    match = re.fullmatch(r"([^()]+)\((.*)\)", value)
    if not match:
        return normalize_topic(value)
    base = normalize_topic(match.group(1))
    subgroups = normalize_parentheses_content(match.group(2))
    if not base:
        return ""
    if not subgroups:
        return base
    return f"{base} ({subgroups})"


def normalize_scope(value: str) -> str:
    value = strip_wrapping(value, "[", "]")
    parts = [normalize_scope_part(part) for part in split_top_level_commas(value)]
    return ", ".join(part for part in parts if part)


def make_aggregate_topic(base: str, subtopics: str) -> str:
    base_topic = normalize_topic(base)
    clean_subtopics = normalize_parentheses_content(subtopics)
    if not base_topic:
        return ""
    if not clean_subtopics.strip():
        return base_topic
    return f"{base_topic} ({clean_subtopics})"


def normalize_topic_expression(value: str) -> str:
    value = str(value).strip()
    if not value:
        return ""
    match = re.fullmatch(r"([^()[\]]+)\((.*)\)", value)
    if match:
        return make_aggregate_topic(match.group(1), match.group(2))
    return normalize_topic(value)


def make_scoped_topic(topic: str, scope: str) -> str:
    clean_topic = normalize_topic_expression(topic)
    clean_scope = normalize_scope(scope)
    if not clean_topic or not clean_scope:
        return clean_topic
    return f"{clean_topic}[{clean_scope}]"


def normalize_sequence(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = re.sub(r"(?<!-)->", "-->", text)
    text = TOKEN_PATTERN.sub(r" \1 ", text)
    return re.sub(r"\s+", " ", text).strip()


def split_sequence(value: object) -> list[str]:
    text = normalize_sequence(value)
    return text.split() if text else []


def join_sequence(parts: Iterable[str]) -> str:
    text = " ".join(str(part).strip() for part in parts if str(part).strip())
    text = normalize_sequence(text)
    text = text.replace(" ( ", " (").replace(" )", ")")
    text = text.replace(" ,", ",")
    return text


def append_token(sequence: str, token: str) -> str:
    return join_sequence([sequence, token])


def extract_substantive_topics(value: object) -> list[str]:
    text = normalize_sequence(value)
    if not text:
        return []

    topics: set[str] = set()
    for match in TOPIC_CHUNK_PATTERN.finditer(text):
        token = match.group(0).strip()
        if token in DAG_OPERATORS_SET:
            continue
        base = token.split("(", 1)[0].split("[", 1)[0].strip()
        clean = normalize_topic(base)
        if clean and clean not in DAG_OPERATORS_SET:
            topics.add(clean)
    return sorted(topics)


def build_topic_dictionary(df: pd.DataFrame, columns: Iterable[str], extra_topics: Iterable[str] = ()) -> list[str]:
    topics: set[str] = set(extra_topics)
    for col in columns:
        if col not in df.columns:
            continue
        for value in df[col].fillna(""):
            topics.update(extract_substantive_topics(value))
    return sorted(topics)


def extract_subtopics(value: object) -> list[str]:
    text = normalize_sequence(value)
    text_without_scopes = re.sub(r"\[[^\]]*\]", "", text)
    subtopics: set[str] = set()
    for content in re.findall(r"\(([^)]*)\)", text_without_scopes):
        for part in split_top_level_commas(content):
            clean = normalize_topic(part)
            if clean:
                subtopics.add(clean)
    return sorted(subtopics)


def extract_scope_qualifiers(value: object) -> list[str]:
    text = normalize_sequence(value)
    scopes: set[str] = set()
    for content in re.findall(r"\[([^\]]*)\]", text):
        normalized_full_scope = normalize_scope(content)
        if normalized_full_scope:
            scopes.add(normalized_full_scope)
        for part in split_top_level_commas(content):
            normalized_part = normalize_scope_part(part)
            if normalized_part:
                scopes.add(normalized_part)
    return sorted(scopes)


def build_subtopic_dictionary(df: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    subtopics: set[str] = set()
    for col in columns:
        if col not in df.columns:
            continue
        for value in df[col].fillna(""):
            subtopics.update(extract_subtopics(value))
    return sorted(subtopics)


def build_scope_dictionary(df: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    scopes: set[str] = set()
    for col in columns:
        if col not in df.columns:
            continue
        for value in df[col].fillna(""):
            scopes.update(extract_scope_qualifiers(value))
    return sorted(scopes)


def row_candidate_topics(row: pd.Series, columns: Iterable[str]) -> list[str]:
    topics: set[str] = set()
    for col in columns:
        if col in row.index:
            topics.update(extract_substantive_topics(row[col]))
    return sorted(topics)


def validate_sequence(value: object) -> list[str]:
    tokens = split_sequence(value)
    warnings: list[str] = []
    if not tokens:
        return warnings

    if tokens[0] in BINARY_OPERATORS:
        warnings.append("The sequence starts with an operator that usually requires a topic before it.")
    if tokens[-1] in BINARY_OPERATORS or tokens[-1] == "|":
        warnings.append("The sequence ends with an operator that usually requires a following token.")

    for left, right in zip(tokens, tokens[1:]):
        if left in DAG_OPERATORS_SET and right in DAG_OPERATORS_SET:
            warnings.append(f"Two operators appear consecutively: {left} {right}.")
        if left == right and left in DAG_OPERATORS_SET:
            warnings.append(f"The operator {left} is repeated.")

    raw = str(value)
    if raw.count("(") != raw.count(")"):
        warnings.append("Parentheses are not balanced.")
    if raw.count("[") != raw.count("]"):
        warnings.append("Square brackets are not balanced.")
    if " [" in raw:
        warnings.append("Scope qualifiers should be attached directly to topics, e.g. fuel_price_increase[others].")
    return sorted(set(warnings))


def load_private_workbook(path: Path, required_columns: Iterable[str], create_columns: Iterable[str] = ()) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(
            f"File not found: {path}\n\n"
            "Create the private workbook locally or configure its path with the relevant environment variable."
        )

    df = pd.read_excel(path)
    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))

    for col in create_columns:
        if col not in df.columns:
            df[col] = ""

    for col in set(required_columns).union(create_columns):
        if col in df.columns:
            df[col] = df[col].fillna("")
    return df


def make_backup_once(path: Path, backup_dir: Path, session_state: dict, label: str) -> None:
    key = f"backup_created_{label}"
    if session_state.get(key) or not path.exists():
        return
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{path.stem}_{label}_backup_{timestamp}{path.suffix}"
    shutil.copy2(path, backup_path)
    session_state[key] = True
    session_state[f"backup_path_{label}"] = str(backup_path)


def save_private_workbook(df: pd.DataFrame, path: Path, backup_dir: Path, session_state: dict, label: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    make_backup_once(path, backup_dir, session_state, label)
    df.to_excel(path, index=False)
