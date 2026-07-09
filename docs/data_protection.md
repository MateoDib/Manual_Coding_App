# Data Protection and Public Disclosure Policy

## Principle

This repository is designed for methodological transparency without disclosure of sensitive participant data. It publishes the coding grammar and software used in the study, but excludes the empirical material to which the software was applied.

## Excluded Materials

The following materials must not be committed:

- interview transcripts;
- participant responses;
- raw or cleaned coding workbooks;
- harmonized coding workbooks;
- agreement reports containing row-level coding;
- LLM coding checkpoints or manifests;
- database exports;
- local backup folders;
- files that can directly or indirectly identify participants.

## File Types Ignored by Default

The `.gitignore` blocks common data-bearing formats, including Excel, CSV, TSV, JSONL, parquet, database, and statistical package files. It also blocks project-specific files such as `Topics_Harmonization.xlsx`, `coding_agreement_report.xlsx`, and `llm_coding_*` artifacts.

## Local Use

Researchers should run the apps against a private workbook stored outside the repository, or against an ignored local copy. The recommended approach is:

```bash
export TOPICS_HARMONIZATION_FILE="/absolute/path/to/private/Topics_Harmonization.xlsx"
```

Local environment variables can map private column names to the anonymized public defaults. These local settings should remain outside version control.

## Pre-Publication Check

Before committing or pushing, run:

```bash
python3 scripts/privacy_check.py
```

This script is a guardrail, not a substitute for human review. Any new output file should still be inspected before publication.
