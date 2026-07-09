from __future__ import annotations

import html
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
import streamlit as st

try:
    from streamlit_sortables import sort_items  # noqa: F401
    SORTABLES_AVAILABLE = True
except Exception:
    SORTABLES_AVAILABLE = False


# ============================================================
# CONFIGURATION
# ============================================================

def get_script_dir() -> Path:
    """Return the directory in which this Streamlit script is stored."""
    try:
        return Path(__file__).resolve().parent
    except NameError:
        return Path.cwd().resolve()


BASE_DIR = get_script_dir()
WORKBOOK_ENV_VAR = "TOPICS_HARMONIZATION_FILE"


def get_configured_workbook_path() -> Path:
    """Return the private workbook path configured for local use."""
    configured_path = Path(os.environ.get(WORKBOOK_ENV_VAR, "Topics_Harmonization.xlsx")).expanduser()
    if configured_path.is_absolute():
        return configured_path
    return BASE_DIR / configured_path


# Input Excel file. The workbook is intentionally not distributed with this repository.
MAIN_FILE = get_configured_workbook_path()

# Optional safety copy made before the first save of a session.
BACKUP_DIR = BASE_DIR / "backups_topics_harmonization"

QUESTION_COL = "question"
RESPONSE_COL = "response"
CODER_A_COL = os.environ.get("TOPICS_CODER_A_COL", "Topics_Coder_A")
CODER_B_COL = os.environ.get("TOPICS_CODER_B_COL", "Topics_Coder_B")
CODER_C_COL = os.environ.get("TOPICS_CODER_C_COL", "Topics_Coder_C")
HARMONIZED_COL = os.environ.get("TOPICS_HARMONIZED_COL", "Topics_Harmonized")

CODER_COLS = {
    "Coder A": CODER_A_COL,
    "Coder B": CODER_B_COL,
    "Coder C": CODER_C_COL,
}

# Operators used to encode DAG-compatible narrative structures.
# They are always available in the interface and are never displayed
# in the substantive topic list.
DAG_OPERATORS = ["-->", "=", ";", "+", "&", "<", ">", "|"]
DAG_OPERATORS_SET = set(DAG_OPERATORS)

# Operators that normally require a substantive topic on both sides.
# The source marker "|" is treated separately: it should be followed by
# an information-source token, but it does not necessarily represent a DAG edge.
BINARY_DAG_OPERATORS = {"-->", "=", "+", "&", "<", ">"}
SOURCE_OPERATOR = "|"

# Ending nodes that must remain easily available because they are required
# in the Acceptability and Final phases whenever the response allows it.
REQUIRED_ENDING_NODES = [
    "acceptability",
    "unacceptability",
    "ambivalent_acceptability",
]
REQUIRED_ENDING_NODES_SET = set(REQUIRED_ENDING_NODES)

# Scope qualifiers attached to substantive topics with square brackets.
# They remain part of substantive tokens, not DAG operators.
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

TOPIC_SEPARATOR = " "
MAX_HISTORY_SIZE = 100
PUNCTUATION_TOKENS = {"(", ")", ",", "[", "]"}


# ============================================================
# TOPIC / DAG TOKEN PARSING
# ============================================================

def normalize_topic(topic: str) -> str:
    """
    Normalize one substantive topic.

    Rules:
    - topics are lowercased;
    - leading and trailing spaces are removed;
    - internal spaces are removed because spaces are token separators;
    - underscores are preserved;
    - DAG syntax operators are treated separately by normalize_dag_token().
    """
    topic = str(topic).strip().lower()
    topic = re.sub(r"\s+", "", topic)
    return topic


def normalize_subtopic(subtopic: str) -> str:
    """Normalize one subtopic used inside parentheses."""
    return normalize_topic(subtopic).strip(",")


def normalize_scope_qualifier(scope: str) -> str:
    """Normalize the content of a square-bracket scope qualifier.

    The scope qualifier may be a single group, such as:
        others

    or a comma-separated scope list, possibly with nested subgroup details:
        modest_household, company (agricultural_sector, sme)

    It is stored internally in compact form:
        modest_household,company(agricultural_sector,sme)
    """
    scope = str(scope).strip().strip("[]")
    scope = scope.lower()
    scope = re.sub(r"\s+", "", scope)
    scope = scope.strip(",")
    return scope


def split_top_level_commas(value: str) -> List[str]:
    """Split a comma-separated string while ignoring commas inside parentheses."""
    value = str(value)
    parts: List[str] = []
    current: List[str] = []
    depth = 0

    for char in value:
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


def format_scope_qualifier(scope: str) -> str:
    """Format a compact scope qualifier for display/export.

    Example:
        modest_household,company(agricultural_sector,sme)
    becomes:
        modest_household, company (agricultural_sector, sme)
    """
    compact_scope = normalize_scope_qualifier(scope)
    if not compact_scope:
        return ""

    formatted_parts: List[str] = []
    for part in split_top_level_commas(compact_scope):
        base, subgroups = parse_aggregate_topic(part)
        if subgroups:
            formatted_parts.append(f"{base} ({', '.join(subgroups)})")
        else:
            formatted_parts.append(normalize_topic(part))

    return ", ".join(part for part in formatted_parts if part)


def is_dag_operator(token: str) -> bool:
    """Return True if token is a DAG syntax operator."""
    return str(token).strip() in DAG_OPERATORS_SET


def parse_topic_components(token: str) -> Tuple[str, List[str], Optional[str]]:
    """
    Parse a substantive token into base topic, subtopics, and optional scope.

    Supported internal or manually typed forms include:
        base
        base[subscope]
        base(subtopic_1,subtopic_2)
        base(subtopic_1,subtopic_2)[scope]
        base[scope](subtopic_1,subtopic_2)

    The preferred exported form is:
        base (subtopic_1, subtopic_2)[scope]
    """
    token = normalize_topic(token)

    if not token:
        return "", [], None

    # Preferred internal form: base(subtopics)[scope]
    match = re.fullmatch(r"([^()\[\]]+)(?:\(([^()]*)\))?(?:\[([^\[\]]+)\])?", token)

    # Also accept base[scope](subtopics), then normalize it to the preferred order.
    if not match:
        alt_match = re.fullmatch(r"([^()\[\]]+)\[([^\[\]]+)\](?:\(([^()]*)\))?", token)
        if alt_match:
            base = normalize_topic(alt_match.group(1))
            scope = normalize_scope_qualifier(alt_match.group(2))
            subtopic_text = alt_match.group(3) or ""
            subtopics = [
                normalize_subtopic(part)
                for part in subtopic_text.split(",")
                if normalize_subtopic(part)
            ]
            return base, subtopics, scope or None
        return token, [], None

    base = normalize_topic(match.group(1))
    subtopic_text = match.group(2) or ""
    scope_text = match.group(3) or ""

    subtopics = [
        normalize_subtopic(part)
        for part in subtopic_text.split(",")
        if normalize_subtopic(part)
    ]
    scope = normalize_scope_qualifier(scope_text) if scope_text else None

    return base, subtopics, scope or None


def parse_aggregate_topic(token: str) -> Tuple[str, List[str]]:
    """
    Parse a topic of the form:
        base(subtopic_1,subtopic_2)

    If the token also has a scope qualifier, the scope is ignored here.
    Use parse_topic_components() when scope is needed.
    """
    base, subtopics, _ = parse_topic_components(token)
    return base, subtopics


def parse_scope_qualified_topic(token: str) -> Tuple[str, Optional[str]]:
    """Parse a topic and return its base topic and optional scope qualifier."""
    base, _, scope = parse_topic_components(token)
    return base, scope


def make_topic_token(base: str, subtopics: Optional[List[str]] = None, scope: Optional[str] = None) -> str:
    """
    Build the internal compact representation of a substantive topic.

    Examples:
        make_topic_token("green_subsidies", ["electric_vehicles"], "others")
        -> "green_subsidies(electric_vehicles)[others]"

        make_topic_token("fuel_price_increase", [], "others")
        -> "fuel_price_increase[others]"
    """
    base = normalize_topic(base)
    clean_subtopics = [normalize_subtopic(x) for x in (subtopics or []) if normalize_subtopic(x)]
    clean_scope = normalize_scope_qualifier(scope or "")

    if not base:
        return ""

    token = base
    if clean_subtopics:
        token += f"({','.join(clean_subtopics)})"
    if clean_scope:
        token += f"[{clean_scope}]"

    return token


def make_aggregate_topic(base: str, subtopics: List[str]) -> str:
    """
    Build the internal compact representation of an aggregated topic.

    Example:
        base = "green_subsidies"
        subtopics = ["electric_vehicles", "public_transport"]

    returns:
        "green_subsidies(electric_vehicles,public_transport)"
    """
    return make_topic_token(base=base, subtopics=subtopics, scope=None)


def make_scope_qualified_topic(base: str, scope: str) -> str:
    """
    Build the internal compact representation of a scope-qualified topic.

    Example:
        base = "fuel_price_increase"
        scope = "others"

    returns:
        "fuel_price_increase[others]"
    """
    return make_topic_token(base=base, subtopics=[], scope=scope)


def normalize_dag_token(token: str) -> str:
    """
    Normalize a token in the harmonized coding sequence.

    DAG operators are preserved exactly. Substantive topics are normalized.
    Parenthesized aggregates and square-bracketed scopes are stored in compact
    internal form:
        green_subsidies(electric_vehicles,public_transport)[others]
    """
    token = str(token).strip()

    if token in DAG_OPERATORS_SET:
        return token

    # Keep stray punctuation as tokens so validation can warn about it.
    if token in PUNCTUATION_TOKENS:
        return token

    base, subtopics, scope = parse_topic_components(token)
    return make_topic_token(base, subtopics, scope)


def raw_tokenize_dag_text(text: str) -> List[str]:
    """
    Tokenize a DAG coding string into raw lexical units.

    It recognizes:
    - -->
    - =
    - ;
    - +
    - &
    - < and >
    - |
    - parentheses, commas, square brackets
    - regular topic tokens

    This tokenizer is intentionally permissive so that it can parse:
        A (X, Y)[self] --> B
        A(X,Y)[self] --> B
        A[self] (X, Y) --> B

    Important: "-->" must be matched before the standalone ">" operator.
    """
    text = str(text).strip()
    if text == "":
        return []

    pattern = r"-->|[=+;&<>|(),\[\]]|[^\s=+;&<>|(),\[\]]+"
    return re.findall(pattern, text)


def _parse_parenthesized_subtopics(raw_tokens: List[str], start: int) -> Tuple[List[str], int, bool]:
    """
    Parse subtopics starting at raw_tokens[start] == '('.

    Returns (subtopics, next_index_after_closing_parenthesis, success).
    """
    if start >= len(raw_tokens) or raw_tokens[start] != "(":
        return [], start, False

    subtopics: List[str] = []
    j = start + 1

    while j < len(raw_tokens):
        if raw_tokens[j] == ")":
            return subtopics, j + 1, True
        if raw_tokens[j] != ",":
            subtopic = normalize_subtopic(raw_tokens[j])
            if subtopic:
                subtopics.append(subtopic)
        j += 1

    return subtopics, start, False


def _parse_scope_qualifier(raw_tokens: List[str], start: int) -> Tuple[Optional[str], int, bool]:
    """
    Parse a scope qualifier starting at raw_tokens[start] == '['.

    Returns (scope, next_index_after_closing_bracket, success).
    The content inside square brackets is kept as a structured string, so the
    app supports both simple and composite scopes, for example:
        [others]
        [modest_household, company (agricultural_sector, sme)]
    """
    if start >= len(raw_tokens) or raw_tokens[start] != "[":
        return None, start, False

    parts: List[str] = []
    j = start + 1

    while j < len(raw_tokens):
        if raw_tokens[j] == "]":
            scope = normalize_scope_qualifier(" ".join(parts))
            return scope or None, j + 1, bool(scope)

        # Keep commas and parentheses because they structure composite scopes.
        if raw_tokens[j] not in {"[", "]"}:
            parts.append(raw_tokens[j])
        j += 1

    return None, start, False


def split_topics(value) -> List[str]:
    """
    Split a topic / DAG sequence into internal tokens.

    The function is robust to semicolons glued to the previous topic:
        A --> B; C --> D
    becomes:
        ["a", "-->", "b", ";", "c", "-->", "d"]

    It also compacts parenthesized aggregates and scope qualifiers:
        A (X, Y)[others]
    becomes one substantive token:
        "a(x,y)[others]"
    """
    if pd.isna(value):
        return []

    raw_tokens = raw_tokenize_dag_text(str(value))
    tokens: List[str] = []
    i = 0

    while i < len(raw_tokens):
        current = raw_tokens[i]

        if current in DAG_OPERATORS_SET:
            tokens.append(current)
            i += 1
            continue

        if current in PUNCTUATION_TOKENS:
            # Stray punctuation is kept as a token so that validation can warn.
            tokens.append(current)
            i += 1
            continue

        base = normalize_topic(current)
        subtopics: List[str] = []
        scope: Optional[str] = None
        i += 1

        # Accept both A[scope](X,Y) and A(X,Y)[scope].
        parsing_optional_suffixes = True
        while parsing_optional_suffixes and i < len(raw_tokens):
            parsing_optional_suffixes = False

            if raw_tokens[i] == "(":
                parsed_subtopics, next_i, success = _parse_parenthesized_subtopics(raw_tokens, i)
                if success:
                    subtopics = parsed_subtopics
                    i = next_i
                    parsing_optional_suffixes = True
                    continue

            if raw_tokens[i] == "[":
                parsed_scope, next_i, success = _parse_scope_qualifier(raw_tokens, i)
                if success:
                    scope = parsed_scope
                    i = next_i
                    parsing_optional_suffixes = True
                    continue

        if base:
            tokens.append(make_topic_token(base, subtopics, scope))

    return [normalize_dag_token(token) for token in tokens if normalize_dag_token(token)]


def format_dag_token(token: str) -> str:
    """
    Format one internal token for display/export.

    Examples:
        green_subsidies(electric_vehicles,public_transport)
        -> green_subsidies (electric_vehicles, public_transport)

        fuel_price_increase[others]
        -> fuel_price_increase[others]

        green_subsidies(electric_vehicles,public_transport)[others]
        -> green_subsidies (electric_vehicles, public_transport)[others]
    """
    token = normalize_dag_token(token)

    if token in DAG_OPERATORS_SET:
        return token

    if token in PUNCTUATION_TOKENS:
        return token

    base, subtopics, scope = parse_topic_components(token)
    output = base
    if subtopics:
        output += f" ({', '.join(subtopics)})"
    if scope:
        output += f"[{format_scope_qualifier(scope)}]"
    return output


def join_dag_tokens(tokens: List[str]) -> str:
    """
    Join internal DAG tokens for Excel storage.

    Formatting rules:
    - '-->', '=', '+', '&', '<', '>', and '|' are surrounded by spaces;
    - ';' is attached to the previous token to mark a new DAG / narrative path;
    - aggregated topics are exported as 'A (X, Y, Z)';
    - scope qualifiers are attached to the substantive topic as 'A[scope]' or
      'A (X, Y)[scope]'.
    """
    clean_tokens = [normalize_dag_token(token) for token in tokens if normalize_dag_token(token)]

    output: List[str] = []
    for token in clean_tokens:
        if token == ";":
            if output:
                output[-1] = output[-1].rstrip() + ";"
            else:
                output.append(";")
        else:
            output.append(format_dag_token(token))

    return TOPIC_SEPARATOR.join(output)


def unique_topics(topics: List[str]) -> List[str]:
    """Return sorted unique normalized tokens."""
    return sorted(set(
        normalize_dag_token(topic)
        for topic in topics
        if normalize_dag_token(topic)
    ))


def get_substantive_topics(tokens: List[str], include_aggregates: bool = True) -> List[str]:
    """
    Keep only substantive topics, excluding DAG operators and punctuation.

    If include_aggregates=True, an aggregate or scoped topic such as:
        green_subsidies(electric_vehicles,public_transport)[others]
    is kept as one candidate token.

    If include_aggregates=False, only the base topic is kept:
        green_subsidies
    """
    substantive = []
    for token in tokens:
        token = normalize_dag_token(token)
        if not token or token in DAG_OPERATORS_SET or token in PUNCTUATION_TOKENS:
            continue

        if include_aggregates:
            substantive.append(token)
        else:
            base, _, _ = parse_topic_components(token)
            substantive.append(base)

    return unique_topics(substantive)


def get_subtopics_from_tokens(tokens: List[str]) -> List[str]:
    """Return all subtopics already used inside aggregate topics."""
    subtopics: List[str] = []
    for token in tokens:
        _, token_subtopics, _ = parse_topic_components(token)
        subtopics.extend(token_subtopics)
    return unique_topics(subtopics)


def get_scope_qualifiers_from_tokens(tokens: List[str]) -> List[str]:
    """Return all scope qualifiers already used inside square brackets."""
    scopes: List[str] = []
    for token in tokens:
        _, _, scope = parse_topic_components(token)
        if scope:
            scopes.append(scope)
    return sorted(set(scopes))


def get_all_subtopics_from_df(df: pd.DataFrame) -> List[str]:
    """Build a subtopic dictionary from all coder and harmonized columns."""
    subtopics: List[str] = []
    for col in list(CODER_COLS.values()) + [HARMONIZED_COL]:
        if col in df.columns:
            for value in df[col]:
                subtopics.extend(get_subtopics_from_tokens(split_topics(value)))
    return sorted(set(subtopics))


def get_all_scope_qualifiers_from_df(df: pd.DataFrame) -> List[str]:
    """Build a scope qualifier dictionary from all coder and harmonized columns."""
    scopes: List[str] = []
    for col in list(CODER_COLS.values()) + [HARMONIZED_COL]:
        if col in df.columns:
            for value in df[col]:
                scopes.extend(get_scope_qualifiers_from_tokens(split_topics(value)))
    scopes.extend(DEFAULT_SCOPE_QUALIFIERS)
    return sorted(set(scope for scope in scopes if scope))


def get_subtopic_options(
    all_topics: List[str],
    candidate_topics: List[str],
    current_sequence: List[str],
    all_subtopics: List[str],
) -> List[str]:
    """Return selectable substantive subtopics.

    Options include:
    - subtopics already used inside parentheses in the database;
    - the substantive topic dictionary;
    - substantive candidates for the current row;
    - substantive tokens already present in the current harmonized sequence;
    - the required ending nodes, although they should rarely be used as subtopics.
    """
    options = set(all_subtopics)
    options.update(all_topics)
    options.update(candidate_topics)
    options.update(REQUIRED_ENDING_NODES)
    options.update(get_substantive_topics(current_sequence, include_aggregates=False))
    options.update(get_subtopics_from_tokens(current_sequence))
    return sorted(option for option in options if option and option not in DAG_OPERATORS_SET)


def get_scope_options(current_sequence: List[str], all_scope_qualifiers: List[str]) -> List[str]:
    """Return selectable scope qualifiers and scope groups.

    A scope option may be a simple label such as "others" or a structured
    group such as "company (agricultural_sector, sme)".
    """
    options = set(DEFAULT_SCOPE_QUALIFIERS)
    options.update(all_scope_qualifiers)
    options.update(get_scope_qualifiers_from_tokens(current_sequence))

    # Also expose top-level elements contained in composite scopes.
    for scope in list(options):
        for part in split_top_level_commas(scope):
            if part:
                options.add(part)

    return sorted(option for option in options if option)


def get_all_topics_from_df(df: pd.DataFrame) -> List[str]:
    """Build a substantive topic dictionary from all coder and harmonized columns."""
    topics: List[str] = []
    for col in list(CODER_COLS.values()) + [HARMONIZED_COL]:
        if col in df.columns:
            for value in df[col]:
                topics.extend(get_substantive_topics(split_topics(value)))

    # Required ending nodes are always available, even if absent from the file.
    topics.extend(REQUIRED_ENDING_NODES)
    return sorted(set(topics))


def get_candidate_topics_for_row(row: pd.Series) -> List[str]:
    """
    Return unique substantive topics proposed by the three coders for the current row.

    DAG operators are deliberately removed because they are displayed in a
    separate, always-available operator block. Required ending nodes are added
    in a separate block, not here, to keep row-specific candidates readable.
    """
    topics: List[str] = []
    for col in CODER_COLS.values():
        if col in row.index:
            topics.extend(get_substantive_topics(split_topics(row[col])))
    return sorted(set(topic for topic in topics if topic not in DAG_OPERATORS_SET))


# Backward-compatible alias: some parts of the UI use the older name.
def join_topics(topics: List[str]) -> str:
    return join_dag_tokens(topics)


# ============================================================
# DAG VALIDATION
# ============================================================

def validate_dag_sequence(tokens: List[str]) -> List[str]:
    """
    Return soft warnings about potentially malformed DAG syntax.

    The app does not block saving. The goal is to help coders detect likely
    mistakes while preserving flexibility in manual coding.
    """
    warnings: List[str] = []
    tokens = [normalize_dag_token(token) for token in tokens if normalize_dag_token(token)]

    if not tokens:
        return warnings

    if tokens[0] in DAG_OPERATORS_SET:
        warnings.append(
            "The sequence starts with a DAG operator. Usually, a sequence should start with a substantive topic."
        )

    if tokens[-1] in BINARY_DAG_OPERATORS or tokens[-1] == SOURCE_OPERATOR:
        warnings.append(
            "The sequence ends with an unfinished operator. Usually, a substantive topic or information source should follow it."
        )

    for i in range(len(tokens) - 1):
        current = tokens[i]
        nxt = tokens[i + 1]

        if current in BINARY_DAG_OPERATORS and nxt in DAG_OPERATORS_SET:
            warnings.append(f"Two operators appear consecutively: '{current} {nxt}'.")

        if current == SOURCE_OPERATOR and nxt in DAG_OPERATORS_SET:
            warnings.append("The source marker '|' should usually be followed by an information-source token.")

        if current == ";" and nxt == ";":
            warnings.append("Two semicolons appear consecutively. This creates an empty narrative path.")

        if current == ";" and nxt in BINARY_DAG_OPERATORS:
            warnings.append(f"A new narrative path starts with operator '{nxt}' after ';'.")

        if current in {"<", ">"} and nxt in {"<", ">"}:
            warnings.append(
                "Two priority operators appear consecutively. Verify that the intended ranking is explicit."
            )

    raw_text = " ".join(tokens)
    if raw_text.count("(") != raw_text.count(")"):
        warnings.append("Parentheses are not balanced.")

    if raw_text.count("[") != raw_text.count("]"):
        warnings.append("Square brackets are not balanced.")

    for i, token in enumerate(tokens):
        if token in {"[", "]"}:
            warnings.append(
                "A scope qualifier appears as a separate token. Attach it directly to a substantive topic, e.g. fuel_price_increase[others]."
            )
        if token not in DAG_OPERATORS_SET and token not in PUNCTUATION_TOKENS:
            base, _, scope = parse_topic_components(token)
            if scope is not None and not base:
                warnings.append("A scope qualifier is attached to an empty topic.")

    return list(dict.fromkeys(warnings))


def explain_dag_operator(operator: str) -> str:
    """Return the coding meaning of one DAG operator."""
    meanings = {
        "-->": "positive causal link: A --> B means that A leads to B in the participant's reasoning.",
        "=": "definition: A = B means that the participant defines or understands A as B.",
        ";": "new DAG / new narrative path: A --> B; C --> D separates two distinct lines of reasoning.",
        "+": "additive association: A + B means that A and B are jointly combined or added.",
        "&": "coexistence: A & B means that A and B coexist without implying additive reinforcement.",
        "<": "priority comparison: A < B means that B prevails over A in the participant's reasoning.",
        ">": "priority comparison: A > B means that A prevails over B in the participant's reasoning.",
        "|": "information source marker: A --> B | newspaper records that the source of information is a newspaper.",
    }
    return meanings.get(operator, "DAG operator")


# ============================================================
# DATA I/O
# ============================================================

@st.cache_data(show_spinner=False)
def load_main_file() -> pd.DataFrame:
    """Load the Excel file and create harmonization column if necessary."""
    if not MAIN_FILE.exists():
        raise FileNotFoundError(
            f"File not found: {MAIN_FILE}\n\n"
            f"Place 'Topics_Harmonization.xlsx' in the same folder as this app "
            f"or set {WORKBOOK_ENV_VAR} to the private workbook path."
        )

    df = pd.read_excel(MAIN_FILE)

    required_cols = [
        QUESTION_COL,
        RESPONSE_COL,
        CODER_A_COL,
        CODER_B_COL,
        CODER_C_COL,
    ]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError("Missing columns: " + ", ".join(missing_cols))

    if HARMONIZED_COL not in df.columns:
        df[HARMONIZED_COL] = ""

    # Avoid NaN display in text fields.
    for col in required_cols + [HARMONIZED_COL]:
        df[col] = df[col].fillna("")

    return df


def make_backup_once() -> None:
    """Create one timestamped backup before the first save in a Streamlit session."""
    if st.session_state.get("backup_created", False):
        return

    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_file = BACKUP_DIR / f"Topics_Harmonization_backup_{timestamp}.xlsx"
    shutil.copy2(MAIN_FILE, backup_file)
    st.session_state["backup_created"] = True
    st.session_state["backup_file"] = str(backup_file)


def save_main_file(df: pd.DataFrame) -> None:
    """Save the updated Excel file."""
    make_backup_once()
    df.to_excel(MAIN_FILE, index=False)
    st.cache_data.clear()


# ============================================================
# SESSION STATE HELPERS
# ============================================================

def ensure_session_defaults() -> None:
    defaults = {
        "active_row_index": None,
        "harmonized_sequence": [],
        "harmonized_history": [],
        "topic_input_version": 0,
        "sortable_version": 0,
        "subtopic_input_version": 0,
        "scope_input_version": 0,
        "pending_subtopics": [],
        "pending_scope_qualifiers": [],
        "backup_created": False,
        "backup_file": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def refresh_topic_input() -> None:
    st.session_state["topic_input_version"] += 1


def refresh_subtopic_input() -> None:
    st.session_state["subtopic_input_version"] += 1


def refresh_scope_input() -> None:
    st.session_state["scope_input_version"] += 1


def refresh_sortable_list() -> None:
    st.session_state["sortable_version"] += 1


def init_row_state(row_index: int, current_tokens: List[str]) -> None:
    ensure_session_defaults()
    if st.session_state["active_row_index"] != row_index:
        st.session_state["active_row_index"] = row_index
        st.session_state["harmonized_sequence"] = current_tokens.copy()
        st.session_state["harmonized_history"] = []
        st.session_state["pending_subtopics"] = []
        st.session_state["pending_scope_qualifiers"] = []
        refresh_topic_input()
        refresh_subtopic_input()
        refresh_scope_input()
        refresh_sortable_list()


def push_history() -> None:
    current_sequence = st.session_state.get("harmonized_sequence", []).copy()
    history = st.session_state.get("harmonized_history", [])
    if history and history[-1] == current_sequence:
        return
    history.append(current_sequence)
    if len(history) > MAX_HISTORY_SIZE:
        history = history[-MAX_HISTORY_SIZE:]
    st.session_state["harmonized_history"] = history


def undo_last_change() -> None:
    history = st.session_state.get("harmonized_history", [])
    if not history:
        return
    st.session_state["harmonized_sequence"] = history.pop()
    st.session_state["harmonized_history"] = history
    refresh_topic_input()
    refresh_subtopic_input()
    refresh_scope_input()
    refresh_sortable_list()


def add_token_to_sequence(token: str) -> None:
    token = normalize_dag_token(token)
    if token:
        push_history()
        st.session_state["harmonized_sequence"].append(token)
        refresh_topic_input()
        refresh_sortable_list()


def add_topic_to_sequence(topic: str) -> None:
    """Add one substantive topic or one DAG operator to the sequence."""
    add_token_to_sequence(topic)


def add_topics_to_sequence(topics: List[str]) -> None:
    clean_tokens = [normalize_dag_token(topic) for topic in topics if normalize_dag_token(topic)]
    if clean_tokens:
        push_history()
        st.session_state["harmonized_sequence"].extend(clean_tokens)
        refresh_topic_input()
        refresh_sortable_list()


def replace_sequence(tokens: List[str]) -> None:
    clean_tokens = [normalize_dag_token(token) for token in tokens if normalize_dag_token(token)]
    if clean_tokens != st.session_state.get("harmonized_sequence", []):
        push_history()
        st.session_state["harmonized_sequence"] = clean_tokens
        refresh_topic_input()
        refresh_subtopic_input()
        refresh_scope_input()
        refresh_sortable_list()


def remove_topic_at_position(position: int) -> None:
    sequence = st.session_state.get("harmonized_sequence", [])
    if 0 <= position < len(sequence):
        push_history()
        sequence.pop(position)
        st.session_state["harmonized_sequence"] = sequence
        refresh_sortable_list()


def clear_sequence() -> None:
    if st.session_state.get("harmonized_sequence", []):
        push_history()
        st.session_state["harmonized_sequence"] = []
        refresh_sortable_list()


def update_sequence_after_sorting(new_sequence: List[str]) -> None:
    old_sequence = st.session_state.get("harmonized_sequence", [])
    if new_sequence != old_sequence:
        push_history()
        st.session_state["harmonized_sequence"] = new_sequence
        refresh_sortable_list()


def find_last_substantive_topic_index(sequence: List[str]) -> Optional[int]:
    """Return the index of the last non-operator topic in a sequence."""
    for i in range(len(sequence) - 1, -1, -1):
        token = normalize_dag_token(sequence[i])
        if token and token not in DAG_OPERATORS_SET and token not in PUNCTUATION_TOKENS:
            return i
    return None


def get_substantive_topic_indices(sequence: List[str]) -> List[int]:
    """Return the positions of all substantive topics in the sequence."""
    indices: List[int] = []
    for i, token in enumerate(sequence):
        token = normalize_dag_token(token)
        if token and token not in DAG_OPERATORS_SET and token not in PUNCTUATION_TOKENS:
            indices.append(i)
    return indices


def add_subtopics_to_topic_at_index(topic_index: Optional[int], subtopics_text: str) -> bool:
    """
    Enrich a selected substantive topic with parenthesized subtopics.

    Example:
        selected token: green_subsidies[others]
        subtopics_text: electric_vehicles, public_transport
    becomes:
        green_subsidies(electric_vehicles,public_transport)[others]

    If the selected topic already has subtopics, the new list replaces the old one.
    Existing scope qualifiers are preserved.
    """
    sequence = st.session_state.get("harmonized_sequence", [])

    if topic_index is None or not (0 <= topic_index < len(sequence)):
        return False

    token = normalize_dag_token(sequence[topic_index])
    if token in DAG_OPERATORS_SET or token in PUNCTUATION_TOKENS:
        return False

    base, _, scope = parse_topic_components(token)
    subtopics = [
        normalize_subtopic(x)
        for x in re.split(r"[,;\n]+", subtopics_text)
        if normalize_subtopic(x)
    ]

    if not subtopics:
        return False

    push_history()
    sequence[topic_index] = make_topic_token(base, subtopics, scope)
    st.session_state["harmonized_sequence"] = sequence
    refresh_subtopic_input()
    refresh_sortable_list()
    return True


def add_subtopics_to_last_topic(subtopics_text: str) -> bool:
    """Backward-compatible helper: enrich the last substantive topic."""
    return add_subtopics_to_topic_at_index(
        find_last_substantive_topic_index(st.session_state.get("harmonized_sequence", [])),
        subtopics_text,
    )


def add_scope_to_topic_at_index(topic_index: Optional[int], scope_text: str) -> bool:
    """
    Enrich a selected substantive topic with a square-bracketed scope qualifier.

    Example:
        selected token: fuel_price_increase
        scope_text: others
    becomes:
        fuel_price_increase[others]

    If the selected topic already has a scope qualifier, the new qualifier
    replaces the old one. Existing subtopics are preserved.
    """
    sequence = st.session_state.get("harmonized_sequence", [])

    if topic_index is None or not (0 <= topic_index < len(sequence)):
        return False

    token = normalize_dag_token(sequence[topic_index])
    if token in DAG_OPERATORS_SET or token in PUNCTUATION_TOKENS:
        return False

    base, subtopics, _ = parse_topic_components(token)
    scope = normalize_scope_qualifier(scope_text)

    if not scope:
        return False

    push_history()
    sequence[topic_index] = make_topic_token(base, subtopics, scope)
    st.session_state["harmonized_sequence"] = sequence
    refresh_scope_input()
    refresh_sortable_list()
    return True


def clear_scope_from_topic_at_index(topic_index: Optional[int]) -> bool:
    """Remove the square-bracketed scope qualifier from a selected topic."""
    sequence = st.session_state.get("harmonized_sequence", [])

    if topic_index is None or not (0 <= topic_index < len(sequence)):
        return False

    token = normalize_dag_token(sequence[topic_index])
    if token in DAG_OPERATORS_SET or token in PUNCTUATION_TOKENS:
        return False

    base, subtopics, scope = parse_topic_components(token)
    if not scope:
        return False

    push_history()
    sequence[topic_index] = make_topic_token(base, subtopics, None)
    st.session_state["harmonized_sequence"] = sequence
    refresh_scope_input()
    refresh_sortable_list()
    return True


# ============================================================
# UI HELPERS
# ============================================================

def make_sortable_labels(sequence: List[str]) -> List[str]:
    return [f"{i + 1}. {format_dag_token(topic)}" for i, topic in enumerate(sequence)]


def remove_sortable_prefix(label: str) -> str:
    if ". " not in label:
        return normalize_dag_token(label)
    return normalize_dag_token(label.split(". ", 1)[1])


def get_row_from_query_params(n_rows: int) -> int:
    default_row_index = 0
    if "row" in st.query_params:
        try:
            default_row_index = int(st.query_params["row"])
            default_row_index = max(0, min(default_row_index, n_rows - 1))
        except (ValueError, TypeError):
            default_row_index = 0
    return default_row_index


def is_uncoded(value) -> bool:
    return pd.isna(value) or str(value).strip() == ""


def scroll_box(content, height: int = 260) -> None:
    """Display text in a fixed-height scrollable box."""
    safe_content = html.escape(str(content))
    st.markdown(
        f"""
        <div style="
            border: 1px solid #ddd;
            border-radius: 0.4rem;
            padding: 0.55rem;
            height: {height}px;
            overflow-y: auto;
            white-space: pre-wrap;
            background-color: rgba(250, 250, 250, 0.03);
        ">
            {safe_content}
        </div>
        """,
        unsafe_allow_html=True,
    )


def display_button_label(token: str) -> str:
    """Return a robust visible label for Streamlit buttons and pills.

    Internally, operators are always stored as ASCII tokens. For a few symbols,
    the app uses full-width characters as labels to avoid weak rendering in
    some Streamlit themes. The saved Excel output remains unchanged.
    """
    labels = {
        "+": "＋",
        "<": "＜",
        ">": "＞",
        "&": "&",
        "|": "|",
    }
    if token in labels:
        return labels[token]
    return format_dag_token(token)


def render_token_buttons(tokens: List[str], key_prefix: str, columns_count: int = 4) -> None:
    """Render clickable token selectors in a compact, fluid layout.

    The preferred rendering uses st.pills, which wraps tokens naturally on
    the available width and avoids the visual separation created by st.columns.
    The fallback keeps the app usable on older Streamlit versions where
    st.pills is not available.
    """
    if not tokens:
        return

    clean_tokens = [normalize_dag_token(token) for token in tokens if normalize_dag_token(token)]
    if not clean_tokens:
        return

    if hasattr(st, "pills"):
        selected_token = st.pills(
            label=" ",
            options=clean_tokens,
            selection_mode="single",
            format_func=display_button_label,
            key=f"{key_prefix}_pills_{st.session_state['topic_input_version']}",
            label_visibility="collapsed",
        )

        if selected_token is not None:
            add_token_to_sequence(selected_token)
            st.rerun()

        return

    cols = st.columns(min(columns_count, max(1, len(clean_tokens))))
    for i, token in enumerate(clean_tokens):
        label = display_button_label(token)
        with cols[i % len(cols)]:
            if st.button(
                label,
                key=f"{key_prefix}_{i}_{token}",
                help=explain_dag_operator(token) if token in DAG_OPERATORS_SET else None,
            ):
                add_token_to_sequence(token)
                st.rerun()


# ============================================================
# STREAMLIT APP
# ============================================================

st.set_page_config(
    page_title="Topic harmonization",
    layout="wide",
)

# Compact layout: reduce vertical whitespace and title/button sizes so that
# more coding information remains visible on a single screen.
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.1rem;
        padding-bottom: 1rem;
        max-width: 98%;
    }
    h1 {
        font-size: 1.45rem !important;
        margin-bottom: 0.25rem !important;
    }
    h2 {
        font-size: 1.15rem !important;
        margin-top: 0.55rem !important;
        margin-bottom: 0.25rem !important;
    }
    h3 {
        font-size: 1.02rem !important;
        margin-top: 0.45rem !important;
        margin-bottom: 0.2rem !important;
    }
    h4 {
        font-size: 0.92rem !important;
        margin-top: 0.25rem !important;
        margin-bottom: 0.1rem !important;
    }
    div[data-testid="stMarkdownContainer"] p {
        margin-bottom: 0.25rem !important;
    }
    div[data-testid="stVerticalBlock"] {
        gap: 0.35rem !important;
    }
    div[data-testid="stHorizontalBlock"] {
        gap: 0.45rem !important;
    }
    div[data-testid="stButton"] button {
        padding: 0.22rem 0.45rem !important;
        min-height: 2.0rem !important;
        font-size: 0.86rem !important;
    }
    div[data-testid="stPills"] {
        margin-top: -0.15rem !important;
        margin-bottom: 0.05rem !important;
    }
    div[data-testid="stPills"] button {
        padding: 0.20rem 0.48rem !important;
        min-height: 1.75rem !important;
        font-size: 0.86rem !important;
        margin-bottom: 0.15rem !important;
    }
    details summary p {
        font-size: 0.92rem !important;
    }
    div[data-testid="stExpander"] {
        margin-top: 0.25rem !important;
        margin-bottom: 0.25rem !important;
    }
    div[data-testid="stCodeBlock"] pre {
        padding: 0.35rem 0.55rem !important;
        margin-top: 0.05rem !important;
        margin-bottom: 0.1rem !important;
        font-size: 0.82rem !important;
    }
    hr {
        margin-top: 0.45rem !important;
        margin-bottom: 0.45rem !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Topic harmonization")

ensure_session_defaults()

try:
    df = load_main_file()
except Exception as exc:
    st.error(str(exc))
    st.stop()

n_rows = len(df)
if n_rows == 0:
    st.warning("The Excel file is empty.")
    st.stop()

all_topics = get_all_topics_from_df(df)
all_subtopics = get_all_subtopics_from_df(df)
all_scope_qualifiers = get_all_scope_qualifiers_from_df(df)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("Navigation")

default_row_index = get_row_from_query_params(n_rows)

row_index = st.sidebar.number_input(
    "Row",
    min_value=0,
    max_value=n_rows - 1,
    value=default_row_index,
    step=1,
)

show_uncoded_only = st.sidebar.checkbox(
    "Rows without harmonized coding only",
    value=False,
)

if show_uncoded_only:
    uncoded_indices = df[df[HARMONIZED_COL].apply(is_uncoded)].index.tolist()
    if len(uncoded_indices) == 0:
        st.sidebar.success("All rows are harmonized.")
    else:
        selected_uncoded_position = st.sidebar.number_input(
            "Uncoded occurrence",
            min_value=0,
            max_value=len(uncoded_indices) - 1,
            value=0,
            step=1,
        )
        row_index = uncoded_indices[selected_uncoded_position]

search_text = st.sidebar.text_input("Search in question/response", value="")
if search_text.strip():
    mask = (
        df[QUESTION_COL].astype(str).str.contains(search_text, case=False, na=False)
        | df[RESPONSE_COL].astype(str).str.contains(search_text, case=False, na=False)
    )
    matched_indices = df[mask].index.tolist()
    if matched_indices:
        selected_match_position = st.sidebar.number_input(
            "Search result occurrence",
            min_value=0,
            max_value=len(matched_indices) - 1,
            value=0,
            step=1,
        )
        row_index = matched_indices[selected_match_position]
        st.sidebar.write(f"Matches: **{len(matched_indices)}**")
    else:
        st.sidebar.warning("No match.")

st.sidebar.markdown("---")

n_harmonized = df[HARMONIZED_COL].fillna("").astype(str).str.strip().ne("").sum()
st.sidebar.write(f"Rows: **{n_rows}**")
st.sidebar.write(f"Harmonized rows: **{n_harmonized}**")
st.sidebar.write(f"Remaining: **{n_rows - n_harmonized}**")
st.sidebar.write(f"Unique substantive topics: **{len(all_topics)}**")
st.sidebar.write(f"Scope qualifiers: **{len(all_scope_qualifiers)}**")
st.sidebar.write(f"Undo states: **{len(st.session_state.get('harmonized_history', []))}**")

if st.session_state.get("backup_file"):
    st.sidebar.caption(f"Backup: {st.session_state['backup_file']}")

with st.sidebar.expander("DAG syntax reminder", expanded=False):
    st.markdown(
        """
        `A --> B` : A leads to B.  
        `A = B` : A is defined as B.  
        `A + B` : A and B are additively combined.  
        `A & B` : A and B coexist without additive meaning.  
        `A < B` : B prevails over A.  
        `A > B` : A prevails over B.  
        `A (X, Y)` : X and Y are subtopics aggregated under A.  
        `A[scope]` : the topic applies to a specific actor, group, or viewpoint.  
        `A --> B; C --> D` : two distinct narrative paths.  
        `A --> B | newspaper` : information source.
        """
    )


# ============================================================
# CURRENT ROW
# ============================================================

row = df.loc[row_index]
current_harmonized_tokens = split_topics(row[HARMONIZED_COL])
init_row_state(row_index, current_harmonized_tokens)

st.subheader(f"Row {row_index}")

progress = n_harmonized / n_rows if n_rows else 0
st.progress(progress, text=f"{n_harmonized}/{n_rows} rows harmonized")

col_question, col_response = st.columns(2, gap="large")

with col_question:
    st.markdown("### Question")
    scroll_box(row[QUESTION_COL], height=210)

with col_response:
    st.markdown("### Response")
    scroll_box(row[RESPONSE_COL], height=210)


# ============================================================
# THREE CODINGS
# ============================================================

st.markdown("---")
st.markdown("### Individual codings")

for coder_name, coder_col in CODER_COLS.items():
    tokens = split_topics(row[coder_col])

    col_name, col_code, col_use, col_add = st.columns([1.0, 6.0, 1.25, 1.25])
    with col_name:
        st.markdown(f"#### {coder_name}")

    with col_code:
        if tokens:
            st.code(join_dag_tokens(tokens), language="text")
        else:
            st.caption("No topic.")

    with col_use:
        if st.button(
            "Use",
            key=f"use_{coder_name}_{row_index}",
            disabled=not bool(tokens),
            help=f"Replace the harmonized sequence with {coder_name}'s coding.",
        ):
            replace_sequence(tokens)
            st.rerun()

    with col_add:
        if st.button(
            "Add",
            key=f"add_{coder_name}_{row_index}",
            disabled=not bool(tokens),
            help=f"Append {coder_name}'s coding to the harmonized sequence.",
        ):
            add_topics_to_sequence(tokens)
            st.rerun()

candidate_topics = get_candidate_topics_for_row(row)

with st.expander("Candidate topics for this row", expanded=True):
    st.markdown("#### DAG operators")
    render_token_buttons(DAG_OPERATORS, key_prefix=f"dag_operator_{row_index}", columns_count=8)

    st.markdown("#### Required ending nodes")
    render_token_buttons(REQUIRED_ENDING_NODES, key_prefix=f"ending_node_{row_index}", columns_count=3)

    st.markdown("#### Candidate substantive topics")
    if candidate_topics:
        render_token_buttons(candidate_topics, key_prefix=f"candidate_{row_index}", columns_count=6)
    else:
        st.info("No candidate substantive topic for this row.")


# ============================================================
# HARMONIZATION INPUT
# ============================================================

st.markdown("---")
st.markdown("### Harmonized coding")

sequence = st.session_state.get("harmonized_sequence", [])
available_topics = sorted(set(all_topics + candidate_topics + REQUIRED_ENDING_NODES + get_substantive_topics(sequence)))

st.markdown("#### Add a substantive topic")
topic_input_key = f"topic_input_{st.session_state['topic_input_version']}"

topic_choice = st.selectbox(
    "Add a substantive topic",
    options=available_topics,
    index=None,
    placeholder="Type or select a substantive topic",
    accept_new_options=True,
    key=topic_input_key,
    label_visibility="collapsed",
)

if topic_choice is not None and str(topic_choice).strip() != "":
    add_topic_to_sequence(topic_choice)
    st.rerun()

st.markdown("#### Add subtopics to a substantive topic")
substantive_indices = get_substantive_topic_indices(sequence)
last_topic_index = find_last_substantive_topic_index(sequence)
selected_subtopic_target_index = None

if substantive_indices:
    default_target_position = (
        substantive_indices.index(last_topic_index)
        if last_topic_index in substantive_indices
        else len(substantive_indices) - 1
    )

    selected_subtopic_target_index = st.selectbox(
        "Topic to enrich with subtopics",
        options=substantive_indices,
        index=default_target_position,
        format_func=lambda idx: f"{idx + 1}. {format_dag_token(sequence[idx])}",
        key=f"subtopic_target_{row_index}_{st.session_state['sortable_version']}",
        help="By default, the selected topic is the last substantive topic added to the sequence, but you can choose any substantive topic already present.",
    )

subtopic_options = get_subtopic_options(
    all_topics=all_topics,
    candidate_topics=candidate_topics,
    current_sequence=sequence,
    all_subtopics=all_subtopics,
)

subtopic_choice_key = f"subtopic_choice_{row_index}_{st.session_state['subtopic_input_version']}"
subtopic_choice = st.selectbox(
    "Type or select a substantive subtopic",
    options=subtopic_options,
    index=None,
    placeholder="Type or select a substantive subtopic",
    accept_new_options=True,
    key=subtopic_choice_key,
    disabled=not bool(substantive_indices),
)

col_add_subtopic, col_apply_subtopics, col_clear_subtopics = st.columns([1.2, 1.2, 1.2])
with col_add_subtopic:
    if st.button(
        "Add subtopic",
        disabled=not bool(substantive_indices) or subtopic_choice is None or not str(subtopic_choice).strip(),
    ):
        clean_subtopic = normalize_subtopic(str(subtopic_choice))
        if clean_subtopic:
            pending = st.session_state.get("pending_subtopics", []).copy()
            pending.append(clean_subtopic)
            st.session_state["pending_subtopics"] = pending
            refresh_subtopic_input()
            st.rerun()

with col_apply_subtopics:
    pending_subtopics = st.session_state.get("pending_subtopics", [])
    if st.button(
        "Apply subtopics",
        disabled=selected_subtopic_target_index is None or len(pending_subtopics) == 0,
    ):
        success = add_subtopics_to_topic_at_index(
            selected_subtopic_target_index,
            ", ".join(pending_subtopics),
        )
        if success:
            st.session_state["pending_subtopics"] = []
            st.rerun()
        else:
            st.warning("No valid subtopic entered.")

with col_clear_subtopics:
    if st.button(
        "Clear subtopics",
        disabled=len(st.session_state.get("pending_subtopics", [])) == 0,
    ):
        st.session_state["pending_subtopics"] = []
        refresh_subtopic_input()
        st.rerun()

if st.session_state.get("pending_subtopics", []):
    st.code(", ".join(st.session_state["pending_subtopics"]), language="text")

st.markdown("#### Add scope qualifiers to a substantive topic")
selected_scope_target_index = None

if substantive_indices:
    default_scope_target_position = (
        substantive_indices.index(last_topic_index)
        if last_topic_index in substantive_indices
        else len(substantive_indices) - 1
    )

    selected_scope_target_index = st.selectbox(
        "Topic to qualify with square brackets",
        options=substantive_indices,
        index=default_scope_target_position,
        format_func=lambda idx: f"{idx + 1}. {format_dag_token(sequence[idx])}",
        key=f"scope_target_{row_index}_{st.session_state['sortable_version']}",
        help=(
            "By default, the selected topic is the last substantive topic added to the sequence. "
            "You can qualify any substantive topic already present."
        ),
    )

scope_options = get_scope_options(sequence, all_scope_qualifiers)
scope_choice_key = f"scope_choice_{row_index}_{st.session_state['scope_input_version']}"
scope_choice = st.selectbox(
    "Type or select a scope qualifier or scoped group",
    options=scope_options,
    index=None,
    placeholder="Type or select a scope, e.g. self, others, company (agricultural_sector, sme)",
    accept_new_options=True,
    key=scope_choice_key,
    disabled=not bool(substantive_indices),
)

full_scope_text = st.text_input(
    "Or paste/edit the full square-bracket content",
    value=", ".join(
        format_scope_qualifier(scope)
        for scope in st.session_state.get("pending_scope_qualifiers", [])
        if normalize_scope_qualifier(scope)
    ),
    placeholder="Example: modest_household, company (agricultural_sector, sme)",
    key=f"full_scope_text_{row_index}_{st.session_state['scope_input_version']}",
    disabled=not bool(substantive_indices),
    help=(
        "Use this when the scope contains several actors or a nested group. "
        "For example: modest_household, company (agricultural_sector, sme)."
    ),
)

col_add_scope, col_apply_scope, col_clear_scope, col_reset_pending_scope = st.columns([1.2, 1.2, 1.2, 1.2])
with col_add_scope:
    if st.button(
        "Add scope",
        disabled=not bool(substantive_indices) or scope_choice is None or not str(scope_choice).strip(),
    ):
        clean_scope = normalize_scope_qualifier(str(scope_choice))
        if clean_scope:
            pending_scopes = st.session_state.get("pending_scope_qualifiers", []).copy()
            pending_scopes.append(clean_scope)
            st.session_state["pending_scope_qualifiers"] = pending_scopes
            refresh_scope_input()
            st.rerun()

with col_apply_scope:
    if st.button(
        "Apply scopes",
        disabled=selected_scope_target_index is None or not normalize_scope_qualifier(full_scope_text),
    ):
        success = add_scope_to_topic_at_index(selected_scope_target_index, full_scope_text)
        if success:
            st.session_state["pending_scope_qualifiers"] = []
            st.rerun()
        else:
            st.warning("No valid scope qualifier entered.")

with col_clear_scope:
    if st.button(
        "Clear applied scope",
        disabled=selected_scope_target_index is None,
    ):
        success = clear_scope_from_topic_at_index(selected_scope_target_index)
        if success:
            st.rerun()
        else:
            st.warning("The selected topic has no scope qualifier to clear.")

with col_reset_pending_scope:
    if st.button(
        "Clear pending scopes",
        disabled=len(st.session_state.get("pending_scope_qualifiers", [])) == 0,
    ):
        st.session_state["pending_scope_qualifiers"] = []
        refresh_scope_input()
        st.rerun()

if st.session_state.get("pending_scope_qualifiers", []):
    st.code(
        ", ".join(format_scope_qualifier(scope) for scope in st.session_state["pending_scope_qualifiers"]),
        language="text",
    )

st.caption(
    "Scope qualifiers are exported as `topic[scope]`, for example "
    "`unreadiness[modest_household, company (agricultural_sector, sme)]`."
)

# Direct text area: useful for pasting an already ordered sequence.
manual_text = st.text_area(
    "Or paste/edit the full harmonized sequence",
    value=join_dag_tokens(sequence),
    height=90,
    help=(
        "DAG syntax is allowed. Examples: A --> B; A = B; "
        "A + B --> C; A & B --> C; A < B; A (X, Y) --> C; "
        "A[others] --> B; A[modest_household, company (agricultural_sector, sme)] --> B; A --> B | newspaper."
    ),
    key=f"manual_text_{row_index}_{st.session_state['sortable_version']}",
)

col_apply_manual, col_clear_manual = st.columns([1, 4])
with col_apply_manual:
    if st.button("Apply text", key=f"apply_manual_{row_index}"):
        replace_sequence(split_topics(manual_text))
        st.rerun()

# The previous "Ordered harmonized sequence" block has been intentionally removed.
# The sequence can still be controlled through:
# - DAG operator buttons;
# - required ending node buttons;
# - candidate topic buttons;
# - the substantive topic selectbox;
# - the subtopic and scope qualifier sections;
# - the manual text area above.
# To remove or reorder tokens, edit the full sequence in the text area and click "Apply text".

final_sequence = st.session_state.get("harmonized_sequence", [])
final_topics_string = join_dag_tokens(final_sequence)
validation_warnings = validate_dag_sequence(final_sequence)

st.markdown("#### Final harmonized coding")
st.code(final_topics_string, language="text")

if validation_warnings:
    st.warning("Potential syntax issues detected. Saving remains possible, but please verify the sequence.")
    for warning in validation_warnings:
        st.caption(f"- {warning}")
else:
    st.success("No obvious DAG syntax issue detected.")

col_undo, col_clear = st.columns([1, 1])
with col_undo:
    if st.button(
        "Undo",
        disabled=len(st.session_state.get("harmonized_history", [])) == 0,
    ):
        undo_last_change()
        st.rerun()

with col_clear:
    if st.button("Clear sequence", disabled=len(final_sequence) == 0):
        clear_sequence()
        st.rerun()


# ============================================================
# SAVE AND NAVIGATION
# ============================================================

st.markdown("---")

col_save, col_save_next, col_prev, col_next = st.columns([1, 1, 1, 1])

with col_save:
    if st.button("Save", type="primary"):
        df.at[row_index, HARMONIZED_COL] = final_topics_string
        try:
            save_main_file(df)
            st.success("Saved in Topics_Harmonized.")
        except PermissionError:
            st.error("Could not save. Please close the Excel file and try again.")
        except Exception as exc:
            st.error(f"Save failed: {exc}")

with col_save_next:
    if st.button("Save and next"):
        df.at[row_index, HARMONIZED_COL] = final_topics_string
        try:
            save_main_file(df)
            next_index = min(n_rows - 1, row_index + 1)
            st.query_params["row"] = str(next_index)
            st.rerun()
        except PermissionError:
            st.error("Could not save. Please close the Excel file and try again.")
        except Exception as exc:
            st.error(f"Save failed: {exc}")

with col_prev:
    if st.button("Previous row"):
        previous_index = max(0, row_index - 1)
        st.query_params["row"] = str(previous_index)
        st.rerun()

with col_next:
    if st.button("Next row"):
        next_index = min(n_rows - 1, row_index + 1)
        st.query_params["row"] = str(next_index)
        st.rerun()


# ============================================================
# DIAGNOSTICS / EXPORT PREVIEW
# ============================================================

with st.expander("Harmonization overview"):
    overview = df[[QUESTION_COL, RESPONSE_COL, HARMONIZED_COL]].copy()
    overview.insert(0, "row_index", df.index)
    overview["is_harmonized"] = overview[HARMONIZED_COL].fillna("").astype(str).str.strip().ne("")
    st.dataframe(
        overview,
        use_container_width=True,
        hide_index=True,
    )

with st.expander("Substantive topic dictionary"):
    dictionary_topics = sorted(set(
        all_topics
        + candidate_topics
        + REQUIRED_ENDING_NODES
        + get_substantive_topics(st.session_state.get("harmonized_sequence", []))
    ))
    st.dataframe(
        pd.DataFrame({"Topics": [format_dag_token(topic) for topic in dictionary_topics]}),
        use_container_width=True,
        hide_index=True,
    )

with st.expander("Scope qualifier dictionary"):
    st.dataframe(
        pd.DataFrame({"Scope qualifiers": get_scope_options(sequence, all_scope_qualifiers)}),
        use_container_width=True,
        hide_index=True,
    )

with st.expander("DAG coding grammar"):
    st.markdown(
        """
        The harmonized coding is treated as an ordered token sequence.

        - `A --> B` means that topic `A` positively or causally leads to topic `B` in the participant's reasoning.
        - `A = B` means that the participant defines or understands `A` as `B`.
        - `A + B` means that `A` and `B` are additively combined.
        - `A & B` means that `A` and `B` coexist without implying additive reinforcement.
        - `A < B` means that `B` prevails over `A` in the participant's reasoning.
        - `A > B` means that `A` prevails over `B` in the participant's reasoning.
        - `A (X, Y, Z)` means that the broad topic `A` aggregates the subtopics `X`, `Y`, and `Z`.
        - `A[scope]` means that the topic applies to a specific actor, group, or viewpoint, e.g. `fuel_price_increase[others]`. Composite scopes such as `unreadiness[modest_household, company (agricultural_sector, sme)]` are allowed.
        - `A --> B; C --> D` means that the same question-response pair contains two distinct narrative paths or DAG components.
        - `A --> B | newspaper` records the information source mentioned by the participant.
        - `acceptability`, `unacceptability`, and `ambivalent_acceptability` are required ending nodes in the Acceptability and Final phases whenever the response allows such coding.

        The symbols `-->`, `=`, `;`, `+`, `&`, `<`, `>`, and `|` are not substantive topics. They are always available in the dedicated operator block. Square brackets are not standalone operators: they are attached directly to substantive topics.
        """
    )
