# Harmonization Workflow

## Overview

This workflow accompanies the open-science release for **"Using AI-led semi-structured interviews to explore the connection between Carbon Tax narratives and climate anxiety"** by **Matéo Dib, Thibaut Arpinon, and Bérangère Legendre**.

The workflow separates independent coding from harmonization. Coders first annotate question-response pairs using the shared DAG-compatible grammar. The harmonization app then compares the coder-level sequences and produces one adjudicated sequence that preserves the most defensible narrative mechanism.

## Step 1: Prepare `coding_interview_base.xlsx`

The manual coding workbook must be private and local. It contains at least:

```text
question
response
```

The manual coding app creates or fills coder columns according to:

```bash
export TOPICS_CODER_COUNT=3
```

or:

```bash
export TOPICS_CODER_COLUMNS="Topics_Coder_1,Topics_Coder_2,Topics_Coder_3"
```

## Step 2: Independent Manual Coding

Run:

```bash
streamlit run apps/manual_topic_coding_app.py
```

Each coder selects their coder slot and saves an ordered DAG-compatible sequence. The coding is saved in `coding_interview_base.xlsx`.

The app supports:

- navigation across rows;
- one, two, or N coder columns;
- reusable topic dictionaries built from existing coding;
- DAG operators and configurable required ending nodes;
- aggregated topics with parentheses, with selectors limited to existing substantive subtopics;
- scope qualifiers with square brackets, with selectors limited to existing scopes or scoped groups;
- text editing for complex sequences;
- warnings for likely syntax issues;
- automatic local backups before overwriting an existing workbook.

## Step 3: Create `harmonization_interview_base.xlsx`

After all coders have completed their columns, copy:

```text
coding_interview_base.xlsx
```

to:

```text
harmonization_interview_base.xlsx
```

This preserves the manual-coding base and creates a separate input for harmonization.

## Step 4: Harmonize Codings

Run:

```bash
streamlit run apps/topic_harmonization_app.py
```

The harmonization app reads `harmonization_interview_base.xlsx` unless `harmonized_interview_base.xlsx` already exists, in which case it resumes from the final output workbook.

The harmonization app writes to:

```text
harmonized_interview_base.xlsx
```

## Step 5: Interpretive Adjudication

The harmonized sequence should be constructed by asking:

- Which mechanism is explicitly present in the response?
- Which coder captured the most precise topic label?
- Are different coders capturing different valid narrative paths?
- Should a path be split with `;` rather than compressed into one chain?
- Are actor-specific qualifications needed with square brackets?
- Are subtopics needed under a broader category?
- Does the phase call for an endpoint such as `acceptability`, `unacceptability`, `ambivalent_acceptability`, or an emotion?
- Is the current answer a continuation that refines an earlier sequence?

The harmonized sequence is not a majority vote. It is a transparent interpretive adjudication designed to preserve DAG-compatible narrative structure.

## Step 6: Reuse in Other Contexts

The apps can be adapted to other interview studies by changing the workbook columns, topic dictionary, phase-specific rules, required ending nodes, and coding protocol. Reuse must cite the repository and the associated paper, as described in `CITATION_POLICY.md`.
