# DAG-Compatible Topic Coding and Harmonization

This repository documents and distributes the code used for manual topic coding and harmonization in a qualitative interview study. It is intended as a transparency companion for academic publication: the coding grammar, software workflow, and harmonization procedure are made available, while the underlying interview data and derived coding workbooks are not distributed because they contain sensitive participant information.

## Repository Scope

The repository contains:

- `apps/manual_topic_coding_app.py`: a Streamlit interface for coder-level topic coding.
- `apps/topic_harmonization_app.py`: a Streamlit interface for comparing coder-level annotations and producing a harmonized topic sequence.
- `docs/coding_protocol.md`: the coding grammar and analytic conventions.
- `docs/harmonization_workflow.md`: the independent coding and adjudication workflow.
- `docs/data_protection.md`: the data-exclusion and disclosure policy for this public repository.
- `templates/private_workbook_schema.md`: the expected private workbook structure.
- `scripts/privacy_check.py`: a local guardrail that flags files that should not be committed.

The repository does not contain participant responses, coder workbooks, LLM outputs, agreement reports, Excel files, JSONL files, or database exports.

## Methodological Summary

The coding system represents each interview response as an ordered sequence of normalized topic tokens. Tokens can encode substantive concepts, causal or logical links, definitions, narrative branches, additive combinations, coexistence, priority relations, scope qualifiers, and information sources. The notation is designed to remain readable for qualitative interpretation while also preserving a structure that can later be translated into directed acyclic graph style representations of reasoning.

The harmonization workflow starts from independent coder-level annotations, displays them side by side, and supports the construction of a single adjudicated sequence in `Topics_Harmonized`. The harmonized sequence is not a simple majority vote. It is a documented interpretive synthesis that preserves the mechanisms, qualifications, and final acceptability or affective nodes expressed in the interview material.

## Private Data Requirement

To run the applications, place a private workbook named `Topics_Harmonization.xlsx` next to the app being used, or set:

```bash
export TOPICS_HARMONIZATION_FILE="/absolute/path/to/private/Topics_Harmonization.xlsx"
```

The public defaults use anonymized coder columns:

```text
question
response
Topics_Coder_A
Topics_Coder_B
Topics_Coder_C
Topics_Harmonized
```

If your private workbook uses different column names, map them locally with environment variables:

```bash
export TOPICS_CODER_A_COL="private_column_name_for_coder_a"
export TOPICS_CODER_B_COL="private_column_name_for_coder_b"
export TOPICS_CODER_C_COL="private_column_name_for_coder_c"
export TOPICS_HARMONIZED_COL="Topics_Harmonized"
```

These local values should not be committed.

## Installation

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Running the Applications

Manual coding:

```bash
streamlit run apps/manual_topic_coding_app.py
```

Harmonization:

```bash
streamlit run apps/topic_harmonization_app.py
```

Both applications write back to the configured private workbook and create timestamped local backups before the first save in a session. Backup folders are ignored by Git.

## Privacy Check Before Commit

Before publishing changes, run:

```bash
python3 scripts/privacy_check.py
```

The script blocks common sensitive data formats and project-specific filenames such as Excel workbooks, JSONL checkpoints, agreement reports, and local backup folders.

## Citation

Please cite this repository using the metadata in `CITATION.cff`. If this repository is used in relation to a specific article, cite both the article and the repository.

## License

The code and documentation in this repository are released under the MIT License. This license does not apply to the underlying interview data, which are not included and are not publicly redistributable.
