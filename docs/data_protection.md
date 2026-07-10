# Data Protection and Public Disclosure Policy

## Principle

This repository is an open-science release of code and methodology, not a data release. It supports transparency for the paper **"Using AI-led semi-structured interviews to explore the connection between Carbon Tax narratives and climate anxiety"** while excluding materials that could identify or expose participants.

## Excluded Materials

The following materials must not be committed:

- interview transcripts;
- participant responses;
- raw or cleaned coding workbooks;
- `coding_interview_base.xlsx`;
- `harmonization_interview_base.xlsx`;
- `harmonized_interview_base.xlsx`;
- coder-specific workbooks;
- agreement reports containing row-level coding;
- LLM coding checkpoints or manifests;
- database exports;
- local backup folders;
- screenshots or documents containing participant responses.

## Why the Data Are Excluded

The interview data may contain sensitive narratives, personal experiences, social positions, or contextual details. Publishing the apps and protocol is sufficient for methodological transparency; publishing the empirical workbooks would be inappropriate without a separate anonymization and ethics review process.

## Local Use

Researchers should store private workbooks outside version control, preferably in a local `private_workbooks/` folder ignored by Git. The public apps default to this local structure.

## Pre-Publication Check

Before committing or pushing, run:

```bash
python3 scripts/privacy_check.py
```

This script blocks common data-bearing formats and project-specific filenames. It is a guardrail, not a substitute for human review.
