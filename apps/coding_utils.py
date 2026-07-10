from __future__ import annotations

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


WORKBOOK_ENV_VAR = "TOPICS_HARMONIZATION_FILE"
QUESTION_COL = os.environ.get("TOPICS_QUESTION_COL", "question")
RESPONSE_COL = os.environ.get("TOPICS_RESPONSE_COL", "response")
CODER_A_COL = os.environ.get("TOPICS_CODER_A_COL", "Topics_Coder_A")
CODER_B_COL = os.environ.get("TOPICS_CODER_B_COL", "Topics_Coder_B")
CODER_C_COL = os.environ.get("TOPICS_CODER_C_COL", "Topics_Coder_C")
HARMONIZED_COL = os.environ.get("TOPICS_HARMONIZED_COL", "Topics_Harmonized")

CODER_COLS = {
    "Coder A": CODER_A_COL,
    "Coder B": CODER_B_COL,
    "Coder C": CODER_C_COL,
}

DAG_OPERATORS = ["-->", "=", ";", "+", "&", "<", ">", "|"]
DAG_OPERATORS_SET = set(DAG_OPERATORS)
BINARY_OPERATORS = {"-->", "=", "+", "&", "<", ">"}
REQUIRED_ENDING_NODES = [
    "acceptability",
    "unacceptability",
    "ambivalent_acceptability",
]
DEFAULT_SCOPE_QUALIFIERS = [
    "self",
    "future_self",
    "others",
    "households",
    "firms",
    "low_income_households",
    "rural_households",
    "urban_households",
    "car_dependent_people",
    "public_authorities",
]

_TOKEN_PATTERN = re.compile(r"(-->|[=;+&<>|])")
_TOPIC_CHUNK_PATTERN = re.compile(r"[A-Za-z0-9_]+(?:\s*\([^)]*\))?(?:\[[^]]*\])?")


def get_app_dir(file_path: str) -> Path:
    return Path(file_path).resolve().parent


def get_workbook_path(app_dir: Path) -> Path:
    configured = Path(os.environ.get(WORKBOOK_ENV_VAR, "Topics_Harmonization.xlsx")).expanduser()
    if configured.is_absolute():
        return configured
    return app_dir / configured


def normalize_topic(value: str) -> str:
    value = str(value).strip()
    if not value:
        return ""
    if value in DAG_OPERATORS_SET:
        return value
    value = value.lower()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value)
    value = value.strip("_,")
    return value


def normalize_scope(value: str) -> str:
    value = str(value).strip().strip("[]").lower()
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_*,_*_", ",_", value)
    return value.strip("_,")


def make_aggregate_topic(base: str, subtopics: str) -> str:
    base_topic = normalize_topic(base)
    clean_subtopics = [normalize_topic(part) for part in re.split(r"[,;]", str(subtopics))]
    clean_subtopics = [part for part in clean_subtopics if part]
    if not base_topic:
        return ""
    if not clean_subtopics:
        return base_topic
    return f"{base_topic} ({', '.join(clean_subtopics)})"


def make_scoped_topic(topic: str, scope: str) -> str:
    clean_topic = str(topic).strip()
    clean_scope = normalize_scope(scope)
    if not clean_topic or not clean_scope:
        return clean_topic
    return f"{clean_topic}[{clean_scope}]"


def normalize_sequence(value: object) -> str:
    text = "" if pd.isna(value) else str(value)
    text = text.replace("->", "-->")
    text = _TOKEN_PATTERN.sub(r" \1 ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def split_sequence(value: object) -> list[str]:
    text = normalize_sequence(value)
    if not text:
        return []
    return text.split()


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
    candidates: list[str] = []
    for match in _TOPIC_CHUNK_PATTERN.finditer(text):
        token = match.group(0).strip()
        if token in DAG_OPERATORS_SET:
            continue
        if token in {"none"}:
            candidates.append(token)
            continue
        base = token.split("(", 1)[0].split("[", 1)[0].strip()
        clean = normalize_topic(base)
        if clean and clean not in DAG_OPERATORS_SET:
            candidates.append(clean)
    return sorted(set(candidates))


def build_topic_dictionary(df: pd.DataFrame, columns: Iterable[str]) -> list[str]:
    topics: set[str] = set(REQUIRED_ENDING_NODES)
    for col in columns:
        if col not in df.columns:
            continue
        for value in df[col].fillna(""):
            topics.update(extract_substantive_topics(value))
    return sorted(topics)


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
            f"Place a private workbook next to the app or set {WORKBOOK_ENV_VAR}."
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
    if session_state.get(key):
        return
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backup_dir / f"{path.stem}_{label}_backup_{timestamp}{path.suffix}"
    shutil.copy2(path, backup_path)
    session_state[key] = True
    session_state[f"backup_path_{label}"] = str(backup_path)


def save_private_workbook(df: pd.DataFrame, path: Path, backup_dir: Path, session_state: dict, label: str) -> None:
    make_backup_once(path, backup_dir, session_state, label)
    df.to_excel(path, index=False)
