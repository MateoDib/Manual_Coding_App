# Private Workbook Schema

The applications expect a local Excel workbook. This workbook is not included in the repository because it contains sensitive participant-level material.

## Recommended Public Column Names

| Column | Manual coding app | Harmonization app | Description |
|---|---:|---:|---|
| `question` | Required | Required | Interview question or prompt. |
| `response` | Required | Required | Participant response. |
| `Topics_Coder_A` | Created if missing | Required | Coder A topic sequence. |
| `Topics_Coder_B` | Created if missing | Required | Coder B topic sequence. |
| `Topics_Coder_C` | Created if missing | Required | Coder C topic sequence. |
| `Topics_Harmonized` | Not required | Created if missing | Final harmonized topic sequence. |

## Local Column Mapping

If the private workbook uses different column names, configure them locally:

```bash
export TOPICS_HARMONIZATION_FILE="/absolute/path/to/private/Topics_Harmonization.xlsx"
export TOPICS_QUESTION_COL="question"
export TOPICS_RESPONSE_COL="response"
export TOPICS_CODER_A_COL="private_column_name_for_coder_a"
export TOPICS_CODER_B_COL="private_column_name_for_coder_b"
export TOPICS_CODER_C_COL="private_column_name_for_coder_c"
export TOPICS_HARMONIZED_COL="Topics_Harmonized"
```

Do not commit shell profiles, `.env` files, notebooks, or screenshots that reveal sensitive local paths or private column names.

## Minimal Workbook for Manual Coding

The manual coding app can start from:

```text
question
response
```

It creates the configured coder columns if they are missing.

## Minimal Workbook for Harmonization

The harmonization app requires:

```text
question
response
Topics_Coder_A
Topics_Coder_B
Topics_Coder_C
```

It creates `Topics_Harmonized` if it is missing.
