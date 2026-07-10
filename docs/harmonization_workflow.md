# Harmonization Workflow

## Overview

The workflow separates individual coding from harmonization. Individual coders first annotate the same question-response pairs using the shared DAG-compatible grammar. The harmonization step then compares the coder-level sequences and produces an adjudicated topic sequence for each row.

The goal of harmonization is not to erase disagreement. It is to make the final coding analytically transparent by preserving the strongest common structure while documenting mechanisms, qualifications, and distinct paths that are substantively warranted by the response.

## Step 1: Prepare the Private Workbook

The private workbook must contain the interview prompt, the interview response, and one topic column per coder. The public repository does not provide this workbook.

Recommended public schema:

```text
question
response
Topics_Coder_A
Topics_Coder_B
Topics_Coder_C
Topics_Harmonized
```

The harmonization app creates `Topics_Harmonized` if it is missing.

## Step 2: Independent Manual Coding

Run:

```bash
streamlit run apps/manual_topic_coding_app.py
```

The manual coding interface supports:

- navigation across rows;
- coder-specific output columns;
- reusable topic dictionaries built from existing coding;
- candidate topics from the current row;
- DAG operators and required ending nodes;
- aggregated topics with parentheses;
- scope qualifiers with square brackets;
- text-based editing for complex sequences;
- warnings for likely syntax issues;
- automatic local backup before the first save.

## Step 3: Harmonization

Run:

```bash
streamlit run apps/topic_harmonization_app.py
```

The harmonization interface displays the independent coding columns side by side and lets the harmonizer:

- replace the current harmonized sequence with a coder's full sequence;
- append a coder's sequence;
- select candidate topics proposed by any coder;
- edit the harmonized sequence manually;
- add subtopics and scope qualifiers;
- save the adjudicated sequence to `Topics_Harmonized`.

## Step 4: Interpretive Adjudication

The harmonized sequence should be constructed by asking:

- Which mechanism is explicitly present in the response?
- Which coder captured the most precise topic label?
- Are different coders capturing different valid narrative paths?
- Should a path be split with `;` rather than compressed into one chain?
- Are actor-specific qualifications needed with square brackets?
- Are subtopics needed under a broader category?
- Does the phase call for an ending node such as `acceptability`, `unacceptability`, or `ambivalent_acceptability`?
- Is the current answer a continuation that refines an earlier sequence?

## Step 5: Export and Analysis

The resulting private workbook can be used for downstream analysis, including agreement checks, topic aggregation, graph reconstruction, or qualitative comparison. Those derived files may still contain sensitive participant information and should not be committed unless they have been independently reviewed and fully anonymized.
