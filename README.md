# Manual Coding App: DAG-Compatible Topic Coding and Harmonization

This repository provides documentation for the manual coding of qualitative interview material used in "Using AI-led semi-structured interviews to explore the connection between Carbon Tax narratives and climate anxiety" for transparency and open-science purpose.

The repository contains two Streamlit applications:

- `apps/manual_topic_coding_app.py`: coder-level manual topic coding.
- `apps/topic_harmonization_app.py`: comparison of independent coder sequences and construction of a harmonized sequence.


## Repository Scope

This repository includes:

- reusable code for manual coding and harmonization;
- a coding protocol;
- a harmonization workflow description;
- a private workbook schema;
- a privacy check script;
- `.gitignore` rules that block common sensitive data formats and project-specific outputs.

It does not include:

- Excel workbooks used for the study;
- interview transcripts or participant responses;
- row-level coding outputs;
- agreement reports;
- database exports.

## Expected Private Workbook

The applications are designed to run against a local private workbook, not a public dataset. The default expected columns are:

```text
question
response
Topics_Coder_A
Topics_Coder_B
Topics_Coder_C
Topics_Harmonized
```

The manual coding app requires only `question` and `response`; it creates coder columns if they are missing. The harmonization app requires the three coder columns and creates `Topics_Harmonized` if it is missing.

If the workbook uses private or project-specific column names, map them locally with environment variables:

```bash
export TOPICS_HARMONIZATION_FILE="/absolute/path/to/private/Topics_Harmonization.xlsx"
export TOPICS_CODER_A_COL="private_column_name_for_coder_a"
export TOPICS_CODER_B_COL="private_column_name_for_coder_b"
export TOPICS_CODER_C_COL="private_column_name_for_coder_c"
export TOPICS_HARMONIZED_COL="Topics_Harmonized"
```

These local settings should not be committed.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the Apps

Manual coding:

```bash
streamlit run apps/manual_topic_coding_app.py
```

Harmonization:

```bash
streamlit run apps/topic_harmonization_app.py
```

Both apps write back to the configured private workbook and create a timestamped backup before the first save in a session.

## Privacy Check

Before committing or publishing changes, run:

```bash
python3 scripts/privacy_check.py
```

The script flags common data-bearing files and project-specific outputs that should not be published.

## License

The code and documentation are released under the MIT License. This license does not apply to the underlying interview data, which are not included and are not publicly redistributable.
