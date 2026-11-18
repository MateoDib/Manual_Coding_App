# Manual Coding App

Code interview question–answer pairs as editable narrative graphs, compare independent coders, and export publication figures in TikZ. The app runs locally in your browser and keeps coding revisions, quotations and graph lineage in one SQLite database.

## Start on macOS

Requires **Python 3.11–3.13**. Download this repository and unzip it, or clone it. The folder can be renamed or moved.

1. Open **Installer.command** to install the application dependencies.
2. Open **Configurer.command**. Set the coder names and default coder, then drop your `interviews.csv` into the import area. You can also choose “Ajouter la base plus tard”.
3. Open **Lancer_Codage.command** to code, or **Lancer_Harmonisation.command** to compare coders.
4. For descriptive statistics, first open `Descriptives_Statistics/Installer.command`, then **Lancer_Statistiques.command** at the application root.

The interface and configuration assistant are in French. Node.js is not needed to run the app: the editor is already built. For compiled LaTeX previews, install a TeX distribution providing `pdflatex`, TikZ and `standalone`; TikZ source remains exportable without it.

Stop a running app with **Ctrl+C in its Terminal window**. Closing the browser tab does not stop the server. Default ports are 8541 (coding) and 8542 (harmonization); change them with Configurer.command if needed.

## Interview file

Use a comma-separated UTF-8 CSV, with **one row per question–answer pair**:

| Column | Content |
|---|---|
| `PID` | Stable participant pseudonym; avoid direct identifiers |
| `pair_id_interview` | Unique, nonempty pair ID across the file |
| `pair_order_interview` | Positive integer giving the pair order within the interview |
| `question` | Interviewer's question |
| `response` | Participant's answer |
| `interview_id` | Optional: separates multiple interviews for one participant |

This version uses a single interview phase. It does not read the Excel input format of earlier repository versions. Importing copies the CSV without changing the original file.

## Coding and outputs

- Double-click to create a topic; drag from its handles to connect topics or create the next block. Select and move multiple blocks together; copy, paste and undo with the usual shortcuts.
- Code causal links, `&`, `+`, `=`, priorities `>` / `<`, subtopics `()`, scopes `[]` and sources `|`. A causal arrow can target a topic or an entire relation; these meanings remain distinct in the stored data.
- Reuse earlier DAGs from the same interview. Technical copies, scientific recurrence and quotations supporting the current answer are recorded separately.
- Coding saves continuously. Validate each pair explicitly; `none` differs from an uncoded answer. A layout change does not create a scientific disagreement.

```text
Manual_Coding_App/
├── .env                              # private configuration, created by setup
├── data/interviews/interviews.csv    # private input
├── outputs/database/visual_coding.sqlite3
├── outputs/coding/<coder>/coding.xlsx
└── outputs/analyses_dags/<coder>/
    ├── report.html
    └── descriptives.xlsx
```

The database is the reference for resuming work; spreadsheet and figure exports are derived from it. Statistics produce only an HTML report and a workbook. Their default frequencies count each participant once per concept or relation; copied DAGs do not multiply participant counts.

See the [coding guide](docs/guide.fr.md) for notation, quotations, revisions and scientific tables, and the [statistics guide](Descriptives_Statistics/README.md) for inclusion rules and denominators.

## Optional AI assistance

Disabled by default. Enable it and configure an OpenAI API key through **Configurer.command**, or use an existing `OPENAI_API_KEY` environment variable. A request is made only when the coder asks for a recommendation. Interview content needed for that request is sent to OpenAI; participant IDs and internal tracking metadata are excluded. Review, edit or reject every proposal before validating the coding. No API call is made during setup.

## Replication and development

The repository contains **code and documentation only**. Interviews, coding databases, exports, Python environments and `.env` are excluded from Git. Share research data separately under your study's access rules; never publish a configured local folder as-is.

To rebuild the editor after editing `frontend/src/`, run `npm ci` followed by `npm run build` inside `frontend/`. The Python entry points are `scripts/configure.py`, `scripts/launch.py` and `scripts/statistics.py`. Review the versioned notation in `apps/coding_scheme.py` when adapting the app to another study.

Released under the [MIT license](LICENSE). Citation metadata and the associated study are described in [CITATION.cff](CITATION.cff) and [CITATION_POLICY.md](CITATION_POLICY.md).
