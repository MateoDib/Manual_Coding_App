from __future__ import annotations

import pandas as pd
import streamlit as st

from coding_utils import (
    DAG_OPERATORS,
    DEFAULT_SCOPE_QUALIFIERS,
    QUESTION_COL,
    REQUIRED_ENDING_NODES,
    RESPONSE_COL,
    append_token,
    build_topic_dictionary,
    coding_base_path,
    configured_coder_map,
    join_sequence,
    load_private_workbook,
    make_aggregate_topic,
    make_scoped_topic,
    normalize_topic,
    row_candidate_topics,
    save_private_workbook,
    validate_sequence,
)


CODER_COLS = configured_coder_map()
WORKBOOK_PATH = coding_base_path()
BACKUP_DIR = WORKBOOK_PATH.parent / "backups_manual_topic_coding"

st.set_page_config(page_title="Manual DAG-Compatible Topic Coding", layout="wide")

st.markdown(
    """
    <style>
    .block-container {max-width: 98%; padding-top: 1rem;}
    textarea {font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;}
    div[data-testid="stButton"] button {width: 100%;}
    </style>
    """,
    unsafe_allow_html=True,
)


def load_data() -> pd.DataFrame:
    return load_private_workbook(
        WORKBOOK_PATH,
        required_columns=[QUESTION_COL, RESPONSE_COL],
        create_columns=CODER_COLS.values(),
    )


def init_row_state(row_index: int, coder_col: str, current_value: str) -> None:
    state_key = f"manual_text_{row_index}_{coder_col}"
    if st.session_state.get("active_manual_row") != row_index or st.session_state.get("active_manual_col") != coder_col:
        st.session_state["active_manual_row"] = row_index
        st.session_state["active_manual_col"] = coder_col
        st.session_state[state_key] = current_value


def set_sequence(row_index: int, coder_col: str, value: str) -> None:
    st.session_state[f"manual_text_{row_index}_{coder_col}"] = value


def current_sequence(row_index: int, coder_col: str) -> str:
    return st.session_state.get(f"manual_text_{row_index}_{coder_col}", "")


def render_token_buttons(tokens: list[str], row_index: int, coder_col: str, prefix: str, columns: int = 4) -> None:
    if not tokens:
        st.caption("No tokens available.")
        return
    grid = st.columns(columns)
    for i, token in enumerate(tokens):
        with grid[i % columns]:
            if st.button(token, key=f"{prefix}_{row_index}_{coder_col}_{i}_{token}"):
                set_sequence(row_index, coder_col, append_token(current_sequence(row_index, coder_col), token))
                st.rerun()


try:
    df = load_data()
except Exception as exc:
    st.error(str(exc))
    st.info(
        "Manual coding expects `coding_interview_base.xlsx` by default. "
        "Set `INTERVIEW_WORKBOOK_DIR`, `CODING_INTERVIEW_BASE`, "
        "`TOPICS_CODER_COUNT`, or `TOPICS_CODER_COLUMNS` if your local setup differs."
    )
    st.stop()

n_rows = len(df)
if n_rows == 0:
    st.warning("The workbook contains no rows.")
    st.stop()

st.sidebar.header("Navigation")
st.sidebar.caption(f"Workbook: `{WORKBOOK_PATH}`")
selected_coder_name = st.sidebar.selectbox("Coder", list(CODER_COLS.keys()))
selected_coder_col = CODER_COLS[selected_coder_name]
st.sidebar.caption(f"Output column: `{selected_coder_col}`")

row_index = int(st.sidebar.number_input("Row", min_value=0, max_value=n_rows - 1, value=0, step=1))

show_uncoded_only = st.sidebar.checkbox("Rows without coding for selected coder", value=False)
if show_uncoded_only:
    uncoded = df[df[selected_coder_col].fillna("").astype(str).str.strip().eq("")].index.tolist()
    if uncoded:
        position = int(st.sidebar.number_input("Uncoded row position", min_value=0, max_value=len(uncoded) - 1, value=0, step=1))
        row_index = int(uncoded[position])
        st.sidebar.write(f"Selected row: **{row_index}**")
    else:
        st.sidebar.success("All rows are coded for this coder.")

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

coded_count = df[selected_coder_col].fillna("").astype(str).str.strip().ne("").sum()
st.sidebar.markdown("---")
st.sidebar.write(f"Rows: **{n_rows}**")
st.sidebar.write(f"Coded rows: **{coded_count}**")
st.sidebar.write(f"Remaining: **{n_rows - coded_count}**")
if st.session_state.get("backup_path_manual"):
    st.sidebar.caption(f"Backup: {st.session_state['backup_path_manual']}")

row = df.iloc[row_index]
init_row_state(row_index, selected_coder_col, str(row[selected_coder_col]))

st.title("Manual DAG-Compatible Topic Coding")
st.caption(
    "This app creates ordered topic sequences that can be interpreted qualitatively "
    "and translated into DAG-style representations of participant narratives."
)
st.progress(coded_count / max(n_rows, 1), text=f"{coded_count}/{n_rows} rows coded for {selected_coder_name}")
st.subheader(f"Row {row_index} - {selected_coder_name}")

left, right = st.columns(2, gap="large")
with left:
    st.markdown("#### Question")
    st.write(row[QUESTION_COL])
with right:
    st.markdown("#### Response")
    st.write(row[RESPONSE_COL])

all_topic_columns = list(CODER_COLS.values())
all_topics = build_topic_dictionary(df, all_topic_columns)
candidate_topics = row_candidate_topics(row, all_topic_columns)

with st.expander("Token shortcuts", expanded=True):
    st.markdown("##### DAG operators")
    render_token_buttons(DAG_OPERATORS, row_index, selected_coder_col, "operator", columns=8)

    st.markdown("##### Required ending nodes")
    render_token_buttons(REQUIRED_ENDING_NODES, row_index, selected_coder_col, "ending", columns=3)

    st.markdown("##### Candidate topics from this row")
    render_token_buttons(candidate_topics, row_index, selected_coder_col, "candidate", columns=5)

    with st.expander("Topic dictionary", expanded=False):
        render_token_buttons(all_topics, row_index, selected_coder_col, "dictionary", columns=5)

st.markdown("### Coding sequence")
text_key = f"manual_text_{row_index}_{selected_coder_col}"
sequence_text = st.text_area(
    "Edit the ordered topic sequence",
    key=text_key,
    height=130,
    label_visibility="collapsed",
)

col_topic, col_aggregate, col_scope = st.columns(3, gap="large")
with col_topic:
    st.markdown("#### Add topic")
    new_topic = st.text_input("Topic label", key=f"new_topic_{row_index}_{selected_coder_col}")
    if st.button("Add topic", key=f"add_topic_{row_index}_{selected_coder_col}"):
        token = normalize_topic(new_topic)
        if token:
            set_sequence(row_index, selected_coder_col, append_token(sequence_text, token))
            st.rerun()

with col_aggregate:
    st.markdown("#### Add aggregate")
    aggregate_base = st.text_input("Base topic", key=f"aggregate_base_{row_index}_{selected_coder_col}")
    aggregate_subtopics = st.text_input("Subtopics, comma-separated", key=f"aggregate_subtopics_{row_index}_{selected_coder_col}")
    if st.button("Add aggregate", key=f"add_aggregate_{row_index}_{selected_coder_col}"):
        token = make_aggregate_topic(aggregate_base, aggregate_subtopics)
        if token:
            set_sequence(row_index, selected_coder_col, append_token(sequence_text, token))
            st.rerun()

with col_scope:
    st.markdown("#### Add scope")
    scope_topic = st.text_input("Topic to qualify", value="", key=f"scope_topic_{row_index}_{selected_coder_col}")
    scope_value = st.selectbox(
        "Scope qualifier",
        DEFAULT_SCOPE_QUALIFIERS + ["custom"],
        key=f"scope_value_{row_index}_{selected_coder_col}",
    )
    custom_scope = ""
    if scope_value == "custom":
        custom_scope = st.text_input("Custom scope", key=f"custom_scope_{row_index}_{selected_coder_col}")
    if st.button("Add scoped topic", key=f"add_scope_{row_index}_{selected_coder_col}"):
        scope = custom_scope if scope_value == "custom" else scope_value
        token = make_scoped_topic(scope_topic, scope)
        if token:
            set_sequence(row_index, selected_coder_col, append_token(sequence_text, token))
            st.rerun()

warnings = validate_sequence(sequence_text)
if warnings:
    st.warning("Syntax warnings")
    for warning in warnings:
        st.write(f"- {warning}")

save_col, save_next_col, clear_col = st.columns([1, 1, 1])
with save_col:
    if st.button("Save", type="primary"):
        df.at[row_index, selected_coder_col] = join_sequence([sequence_text])
        save_private_workbook(df, WORKBOOK_PATH, BACKUP_DIR, st.session_state, "manual")
        st.cache_data.clear()
        st.success(f"Saved in {selected_coder_col}.")
        st.rerun()

with save_next_col:
    if st.button("Save and next"):
        df.at[row_index, selected_coder_col] = join_sequence([sequence_text])
        save_private_workbook(df, WORKBOOK_PATH, BACKUP_DIR, st.session_state, "manual")
        st.cache_data.clear()
        st.session_state["active_manual_row"] = None
        st.success(f"Saved in {selected_coder_col}.")
        st.rerun()

with clear_col:
    if st.button("Clear local editor"):
        set_sequence(row_index, selected_coder_col, "")
        st.rerun()

with st.expander("Coding overview", expanded=False):
    overview = df[[QUESTION_COL, RESPONSE_COL, selected_coder_col]].copy()
    overview["is_coded"] = overview[selected_coder_col].fillna("").astype(str).str.strip().ne("")
    st.dataframe(overview, use_container_width=True, hide_index=True)
