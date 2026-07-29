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

## Required Ending Nodes

The apps are prefilled with the ending nodes used in the paper:

```text
acceptability
unacceptability
ambivalent_acceptability
```

They can be enabled, disabled, or edited directly in the app sidebar. For reuse in another project, you can also configure them before launch:

```bash
export ENABLE_REQUIRED_ENDING_NODES=1
export REQUIRED_ENDING_NODES="acceptability,unacceptability,ambivalent_acceptability"
```

To disable them by default:

```bash
export ENABLE_REQUIRED_ENDING_NODES=0
```

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

These instructions install the software needed to run the Streamlit applications. They do not download or expose any interview data, participant responses, private coding workbooks, or agreement reports.

### Prerequisites

You need:

- Git, to clone the repository;
- Python 3.10 or newer, with Python 3.11 recommended;
- a terminal application;
- a web browser, because Streamlit opens the apps locally in the browser.

A GitHub account is not required to clone and run this public repository. It is only needed if you want to fork the repository or push changes.

### macOS

1. Open Terminal.

2. Install Apple's command-line developer tools, which include Git:

```bash
xcode-select --install
```

If Git is already installed, this command may report that the tools are already available. You can check with:

```bash
git --version
```

3. Check whether Python 3 is already installed:

```bash
python3 --version
```

If Python 3.10 or newer is not available, install Python from <https://www.python.org/downloads/> or, if you use Homebrew, run:

```bash
brew install python
```

4. Clone the repository and enter the project folder:

```bash
git clone https://github.com/MateoDib/Manual_Coding_App.git
cd Manual_Coding_App
```

5. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

After activation, your terminal prompt usually shows `(.venv)`.

6. Upgrade `pip` and install the required Python packages:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

7. Verify the installation:

```bash
python -c "import streamlit, pandas, openpyxl; import streamlit_sortables; print('Installation OK')"
streamlit --version
```

8. Create the private workbook folder used by the apps:

```bash
mkdir -p private_workbooks
```

Place private Excel workbooks in `private_workbooks/` only on your local machine. This folder is ignored by Git.

### Windows

The recommended Windows shell is PowerShell.

1. Install Git for Windows.

Using `winget` in PowerShell:

```powershell
winget install --id Git.Git -e --source winget
```

Alternatively, download Git from <https://git-scm.com/download/win>. After installation, open a new PowerShell window and check:

```powershell
git --version
```

2. Install Python 3.10 or newer, with Python 3.11 recommended.

Using `winget`:

```powershell
winget install --id Python.Python.3.11 -e --source winget
```

Alternatively, download Python from <https://www.python.org/downloads/windows/>. During installation, select **Add Python to PATH** if the installer offers this option.

Check the installation:

```powershell
py --version
```

3. Clone the repository and enter the project folder:

```powershell
git clone https://github.com/MateoDib/Manual_Coding_App.git
cd Manual_Coding_App
```

4. Create a virtual environment:

```powershell
py -3 -m venv .venv
```

5. Activate the virtual environment:

```powershell
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation because script execution is restricted, allow scripts for the current PowerShell session only, then activate again:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

After activation, your terminal prompt usually shows `(.venv)`.

6. Upgrade `pip` and install the required Python packages:

```powershell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

7. Verify the installation:

```powershell
python -c "import streamlit, pandas, openpyxl; import streamlit_sortables; print('Installation OK')"
streamlit --version
```

8. Create the private workbook folder used by the apps:

```powershell
New-Item -ItemType Directory -Force private_workbooks
```

Place private Excel workbooks in `private_workbooks\` only on your local machine. This folder is ignored by Git.

### Updating an Existing Local Copy

If you already cloned the repository, open a terminal in the local `Manual_Coding_App` folder and run:

```bash
git pull
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

On Windows, the same commands work in PowerShell once the virtual environment is activated.

### Keeping Data Private

Before adding or committing any file, check that private study material remains outside version control:

```bash
git status
python3 scripts/privacy_check.py
```

On Windows, use:

```powershell
git status
python scripts/privacy_check.py
```

The repository's `.gitignore` excludes `private_workbooks/`, Excel workbooks, data exports, outputs, logs, and common database formats. This is a guardrail, not a substitute for human review.

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

Any reuse, adaptation, redistribution, teaching use, or scholarly use of this app must cite the repository and the associated paper. See `CITATION_POLICY.md` and `CITATION.cff`.

Required repository citation:

> Dib, M. (2026). *Adaptive Manual Coding Application for Qualitative Research*. GitHub repository.

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
