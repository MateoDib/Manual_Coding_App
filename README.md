# Manual Coding App for DAG-Compatible Qualitative Coding

This repository provides the public code and documentation used in the open-science release accompanying the paper **"Using AI-led semi-structured interviews to explore the connection between Carbon Tax narratives and climate anxiety"**, co-authored by **Matéo Dib, Thibaut Arpinon, and Bérangère Legendre**.

The repository is designed for transparency: it documents how the coding and harmonization were conducted, and it provides reusable applications for other qualitative projects. It does **not** publish the interview databases, participant responses, coder workbooks, or agreement reports, because these materials may contain sensitive participant-level information.

## What the Apps Do

These applications are not only topic-coding tools. They help researchers create **DAG-compatible qualitative codings**: ordered topic sequences that preserve narrative mechanisms, causal chains, definitions, trade-offs, priorities, coexistence relations, information sources, and actor-specific scope qualifiers.

The resulting coding can be read qualitatively and can also be translated into graph-like representations of participants' reasoning.

## Repository Contents

- `apps/manual_topic_coding_app.py`: Streamlit app for coder-level manual coding.
- `apps/topic_harmonization_app.py`: Streamlit app for comparing coder sequences and producing a harmonized sequence.
- `apps/coding_utils.py`: shared parsing, configuration, workbook, backup, and validation utilities.
- `docs/coding_protocol.md`: the main document for understanding how to code and how to build DAG-compatible sequences.
- `docs/harmonization_workflow.md`: the workflow from independent coding to harmonized DAG-compatible coding.
- `docs/data_protection.md`: the data-exclusion policy for the open-science release.
- `templates/private_workbook_schema.md`: the expected local workbook structure.
- `scripts/privacy_check.py`: a guardrail to prevent sensitive workbooks and outputs from being committed.
- `CITATION.cff` and `CITATION_POLICY.md`: citation metadata and reuse expectations.

For learning how to code, start with `docs/coding_protocol.md`, then read `docs/harmonization_workflow.md`, then check `templates/private_workbook_schema.md`.

## Private Workbook Workflow

The public repository does not include data. Locally, the workflow uses three private Excel workbooks:

1. `coding_interview_base.xlsx`: input for the manual coding app. It contains at least `question` and `response`; coder columns are created or filled by the manual app.
2. `harmonization_interview_base.xlsx`: a copy of `coding_interview_base.xlsx` after the N coders have added their coding columns.
3. `harmonized_interview_base.xlsx`: the final output produced by the harmonization app, with the harmonized topic/DAG-compatible sequence.

By default, the apps look for these files in a local `private_workbooks/` folder inside the repository. This folder is ignored by Git.

## One, Two, or N Coders

The number of coders is configurable.

Use a count:

```bash
export TOPICS_CODER_COUNT=3
```

This creates or expects:

```text
Topics_Coder_1
Topics_Coder_2
Topics_Coder_3
```

Or provide explicit column names:

```bash
export TOPICS_CODER_COLUMNS="Topics_Coder_1,Topics_Coder_2,Topics_Coder_3,Topics_Coder_4"
```

The harmonization app requires all configured coder columns to be present in `harmonization_interview_base.xlsx`.

## Optional Path Configuration

If your private workbooks are stored elsewhere:

```bash
export INTERVIEW_WORKBOOK_DIR="/absolute/path/to/private/workbooks"
export CODING_INTERVIEW_BASE="coding_interview_base.xlsx"
export HARMONIZATION_INTERVIEW_BASE="harmonization_interview_base.xlsx"
export HARMONIZED_INTERVIEW_BASE="harmonized_interview_base.xlsx"
```

You can also configure the question, response, and harmonized columns:

```bash
export TOPICS_QUESTION_COL="question"
export TOPICS_RESPONSE_COL="response"
export TOPICS_HARMONIZED_COL="Topics_Harmonized"
```

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

Both apps create local timestamped backups before overwriting an existing workbook.

## Open-Science Reuse

This repository is released to make the coding procedure inspectable, reproducible, and adaptable. The apps can be reused in other qualitative projects if the coding grammar, workbook schema, and topic labels are adapted to the new research context.

Any reuse, adaptation, redistribution, or scholarly use of this app must cite the repository and the associated paper. See `CITATION_POLICY.md` and `CITATION.cff`.

## Data Protection

Do not commit:

- interview transcripts or participant responses;
- `coding_interview_base.xlsx`;
- `harmonization_interview_base.xlsx`;
- `harmonized_interview_base.xlsx`;
- coder workbooks;
- agreement reports;
- JSONL checkpoints;
- database exports.

Before publishing changes, run:

```bash
python3 scripts/privacy_check.py
```

This check is a guardrail, not a substitute for human review.
