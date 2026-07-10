from __future__ import annotations

import pandas as pd
import streamlit as st

from coding_utils import (
    DAG_OPERATOR_LABELS,
    DAG_OPERATORS,
    HARMONIZED_COL,
    QUESTION_COL,
    RESPONSE_COL,
    append_token,
    build_scope_dictionary,
    build_subtopic_dictionary,
    build_topic_dictionary,
    configured_coder_map,
    configured_required_ending_nodes,
    harmonization_base_path,
    harmonized_base_path,
    join_sequence,
    load_private_workbook,
    make_aggregate_topic,
    make_scoped_topic,
    normalize_topic,
    parse_token_list,
    row_candidate_topics,
    save_private_workbook,
    validate_sequence,
)


CODER_COLS = configured_coder_map()
INPUT_WORKBOOK_PATH = harmonization_base_path()
OUTPUT_WORKBOOK_PATH = harmonized_base_path()
ACTIVE_WORKBOOK_PATH = OUTPUT_WORKBOOK_PATH if OUTPUT_WORKBOOK_PATH.exists() else INPUT_WORKBOOK_PATH
BACKUP_DIR = OUTPUT_WORKBOOK_PATH.parent / "backups_topic_harmonization"

st.set_page_config(page_title="DAG-Compatible Topic Harmonization", layout="wide")

st.markdown(
    """
    <style>
    .block-container {max-width: 98%; padding-top: 1rem;}
    textarea {font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;}
    div[data-testid="stButton"] button {
        width: 100%;
        min-height: 2.35rem;
        white-space: normal;
        font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def load_data() -> pd.DataFrame:
    return load_private_workbook(
        ACTIVE_WORKBOOK_PATH,
        required_columns=[QUESTION_COL, RESPONSE_COL, *CODER_COLS.values()],
        create_columns=[HARMONIZED_COL],
    )


def init_row_state(row_index: int, current_value: str) -> None:
    key = f"harmonized_text_{row_index}"
    if st.session_state.get("active_harmonized_row") != row_index:
        st.session_state["active_harmonized_row"] = row_index
        st.session_state[key] = current_value


def set_sequence(row_index: int, value: str) -> None:
    st.session_state[f"harmonized_text_{row_index}"] = value


def current_sequence(row_index: int) -> str:
    return st.session_state.get(f"harmonized_text_{row_index}", "")


def sidebar_required_ending_nodes() -> list[str]:
    default_nodes = configured_required_ending_nodes()
    st.sidebar.markdown("---")
    st.sidebar.subheader("Coding options")
    enabled = st.sidebar.checkbox(
        "Enable required ending nodes",
        value=bool(default_nodes),
        help="When enabled, these study-specific ending nodes are available as shortcut buttons.",
    )
    raw_nodes = st.sidebar.text_area(
        "Required ending nodes",
        value="\n".join(default_nodes),
        height=96,
        disabled=not enabled,
        help="Use one node per line, or separate nodes with commas or semicolons.",
    )
    if not enabled:
        return []
    return parse_token_list(raw_nodes)


def render_token_buttons(
    tokens: list[str],
    row_index: int,
    prefix: str,
    columns: int = 4,
    labels: dict[str, str] | None = None,
) -> None:
    if not tokens:
        st.caption("No tokens available.")
        return
    grid = st.columns(columns)
    for i, token in enumerate(tokens):
        with grid[i % columns]:
            display_label = labels.get(token, token) if labels else token
            help_text = f"Insert `{token}`" if display_label != token else None
            if st.button(display_label, key=f"{prefix}_{row_index}_{i}_{token}", help=help_text):
                set_sequence(row_index, append_token(current_sequence(row_index), token))
                st.rerun()


try:
    df = load_data()
except Exception as exc:
    st.error(str(exc))
    st.info(
        "Harmonization expects `harmonization_interview_base.xlsx` by default. "
        "It writes the final harmonized workbook to `harmonized_interview_base.xlsx`. "
        "Set `INTERVIEW_WORKBOOK_DIR`, `HARMONIZATION_INTERVIEW_BASE`, "
        "`HARMONIZED_INTERVIEW_BASE`, `TOPICS_CODER_COUNT`, or `TOPICS_CODER_COLUMNS` "
        "if your local setup differs."
    )
    st.stop()

n_rows = len(df)
if n_rows == 0:
    st.warning("The workbook contains no rows.")
    st.stop()

st.sidebar.header("Navigation")
st.sidebar.caption(f"Input base: `{INPUT_WORKBOOK_PATH}`")
st.sidebar.caption(f"Active base: `{ACTIVE_WORKBOOK_PATH}`")
st.sidebar.caption(f"Final output: `{OUTPUT_WORKBOOK_PATH}`")

row_index = int(st.sidebar.number_input("Row", min_value=0, max_value=n_rows - 1, value=0, step=1))

show_unharmonized_only = st.sidebar.checkbox("Rows without harmonization", value=False)
if show_unharmonized_only:
    missing = df[df[HARMONIZED_COL].fillna("").astype(str).str.strip().eq("")].index.tolist()
    if missing:
        position = int(st.sidebar.number_input("Unharmonized row position", min_value=0, max_value=len(missing) - 1, value=0, step=1))
        row_index = int(missing[position])
        st.sidebar.write(f"Selected row: **{row_index}**")
    else:
        st.sidebar.success("All rows are harmonized.")

search_text = st.sidebar.text_input("Search question/response", value="")
if search_text.strip():
    mask = (
        df[QUESTION_COL].astype(str).str.contains(search_text, case=False, na=False)
        | df[RESPONSE_COL].astype(str).str.contains(search_text, case=False, na=False)
    )
    matches = df[mask].index.tolist()
    if matches:
        pos = int(st.sidebar.number_input("Search result", min_value=0, max_value=len(matches) - 1, value=0, step=1))
        row_index = int(matches[pos])
        st.sidebar.write(f"Matches: **{len(matches)}**")
    else:
        st.sidebar.warning("No match.")

harmonized_count = df[HARMONIZED_COL].fillna("").astype(str).str.strip().ne("").sum()
st.sidebar.markdown("---")
st.sidebar.write(f"Rows: **{n_rows}**")
st.sidebar.write(f"Harmonized rows: **{harmonized_count}**")
st.sidebar.write(f"Remaining: **{n_rows - harmonized_count}**")
if st.session_state.get("backup_path_harmonization"):
    st.sidebar.caption(f"Backup: {st.session_state['backup_path_harmonization']}")

required_ending_nodes = sidebar_required_ending_nodes()

row = df.iloc[row_index]
init_row_state(row_index, str(row[HARMONIZED_COL]))

st.title("DAG-Compatible Topic Harmonization")
st.caption(
    "This app adjudicates multiple coder sequences into one harmonized sequence "
    "that preserves narrative mechanisms and can be translated into DAG-style structures."
)
st.progress(harmonized_count / max(n_rows, 1), text=f"{harmonized_count}/{n_rows} rows harmonized")
st.subheader(f"Row {row_index}")

left, right = st.columns(2, gap="large")
with left:
    st.markdown("#### Question")
    st.write(row[QUESTION_COL])
with right:
    st.markdown("#### Response")
    st.write(row[RESPONSE_COL])

st.markdown("### Individual codings")
coder_columns = list(CODER_COLS.values())
for coder_name, coder_col in CODER_COLS.items():
    st.markdown(f"#### {coder_name}")
    coding = str(row.get(coder_col, ""))
    st.code(coding if coding.strip() else "[empty]", language="text")
    use_col, append_col = st.columns([1, 1])
    with use_col:
        if st.button(f"Use {coder_name}", key=f"use_{coder_name}_{row_index}"):
            set_sequence(row_index, coding)
            st.rerun()
    with append_col:
        if st.button(f"Append {coder_name}", key=f"append_{coder_name}_{row_index}"):
            set_sequence(row_index, append_token(current_sequence(row_index), coding))
            st.rerun()

all_topic_columns = coder_columns + [HARMONIZED_COL]
all_topics = build_topic_dictionary(df, all_topic_columns, extra_topics=required_ending_nodes)
existing_subtopics = build_subtopic_dictionary(df, all_topic_columns)
existing_scopes = build_scope_dictionary(df, all_topic_columns)
candidate_topics = row_candidate_topics(row, coder_columns)

st.markdown("### Token shortcuts")
st.markdown("##### DAG operators")
render_token_buttons(DAG_OPERATORS, row_index, "operator", columns=8, labels=DAG_OPERATOR_LABELS)

st.markdown("##### Required ending nodes")
if required_ending_nodes:
    render_token_buttons(required_ending_nodes, row_index, "ending", columns=3)
else:
    st.caption("Required ending nodes are disabled.")

st.markdown("##### Candidate topics from coder sequences")
render_token_buttons(candidate_topics, row_index, "candidate", columns=5)

with st.expander("Topic dictionary", expanded=False):
    render_token_buttons(all_topics, row_index, "dictionary", columns=5)

st.markdown("### Harmonized sequence")
text_key = f"harmonized_text_{row_index}"
sequence_text = st.text_area(
    "Edit the harmonized topic sequence",
    key=text_key,
    height=140,
    label_visibility="collapsed",
)

col_topic, col_aggregate, col_scope = st.columns(3, gap="large")
with col_topic:
    st.markdown("#### Add topic")
    new_topic = st.text_input("Topic label", key=f"new_topic_{row_index}")
    if st.button("Add topic", key=f"add_topic_{row_index}"):
        token = normalize_topic(new_topic)
        if token:
            set_sequence(row_index, append_token(sequence_text, token))
            st.rerun()

with col_aggregate:
    st.markdown("#### Add aggregate")
    aggregate_base = st.text_input("Base topic", key=f"aggregate_base_{row_index}")
    subtopic_options = ["", *existing_subtopics]
    selected_subtopic = st.selectbox(
        "Type or select a substantive subtopic",
        subtopic_options,
        format_func=lambda value: value or "Select an existing subtopic",
        help="Existing values found inside parentheses, e.g. `(electric_vehicle_infrastructure)`.",
        key=f"aggregate_selected_subtopic_{row_index}",
    )
    if not existing_subtopics:
        st.caption("No existing subtopics yet; paste a new parentheses content below.")
    aggregate_subtopics = st.text_input(
        "Or paste/edit the full parentheses content",
        placeholder="(electric_vehicle_infrastructure, soft_mobility)",
        help="Use the content that should appear inside parentheses.",
        key=f"aggregate_subtopics_{row_index}",
    )
    if st.button("Add aggregate", key=f"add_aggregate_{row_index}"):
        token = make_aggregate_topic(aggregate_base, aggregate_subtopics or selected_subtopic)
        if token:
            set_sequence(row_index, append_token(sequence_text, token))
            st.rerun()

with col_scope:
    st.markdown("#### Add scope")
    scope_topic = st.text_input("Topic to qualify", value="", key=f"scope_topic_{row_index}")
    scope_options = ["", *existing_scopes]
    scope_value = st.selectbox(
        "Type or select a scope qualifier or scoped group",
        scope_options,
        format_func=lambda value: f"[{value}]" if value else "Select an existing scope",
        help="Existing values found inside square brackets, e.g. `[self]` or `[company (agricultural_sector, sme)]`.",
        key=f"scope_value_{row_index}",
    )
    if not existing_scopes:
        st.caption("No existing scopes yet; paste a new square-bracket content below.")
    custom_scope = st.text_input(
        "Or paste/edit the full square-bracket content",
        placeholder="[modest_household, company (agricultural_sector, sme)]",
        help="Use the content that should appear inside square brackets.",
        key=f"custom_scope_{row_index}",
    )
    if st.button("Add scoped topic", key=f"add_scope_{row_index}"):
        scope = custom_scope or scope_value
        token = make_scoped_topic(scope_topic, scope)
        if token:
            set_sequence(row_index, append_token(sequence_text, token))
            st.rerun()

warnings = validate_sequence(sequence_text)
if warnings:
    st.warning("Syntax warnings")
    for warning in warnings:
        st.write(f"- {warning}")

save_col, save_next_col, clear_col = st.columns([1, 1, 1])
with save_col:
    if st.button("Save harmonization", type="primary"):
        df.at[row_index, HARMONIZED_COL] = join_sequence([sequence_text])
        save_private_workbook(df, OUTPUT_WORKBOOK_PATH, BACKUP_DIR, st.session_state, "harmonization")
        st.cache_data.clear()
        st.success(f"Saved in {OUTPUT_WORKBOOK_PATH.name}.")
        st.rerun()

with save_next_col:
    if st.button("Save and next"):
        df.at[row_index, HARMONIZED_COL] = join_sequence([sequence_text])
        save_private_workbook(df, OUTPUT_WORKBOOK_PATH, BACKUP_DIR, st.session_state, "harmonization")
        st.cache_data.clear()
        st.session_state["active_harmonized_row"] = None
        st.success(f"Saved in {OUTPUT_WORKBOOK_PATH.name}.")
        st.rerun()

with clear_col:
    if st.button("Clear local editor"):
        set_sequence(row_index, "")
        st.rerun()

with st.expander("Harmonization overview", expanded=False):
    overview = df[[QUESTION_COL, RESPONSE_COL, HARMONIZED_COL]].copy()
    overview["is_harmonized"] = overview[HARMONIZED_COL].fillna("").astype(str).str.strip().ne("")
    st.dataframe(overview, use_container_width=True, hide_index=True)
