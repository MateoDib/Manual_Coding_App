# Private Workbook Schema

The applications expect an Excel workbook stored locally. The workbook is not included in this repository.

## Recommended Public Column Names

| Column | Required by manual coding app | Required by harmonization app | Description |
|---|---:|---:|---|
| `question` | Yes | Yes | Interview question or prompt. |
| `response` | Yes | Yes | Participant response. This column is sensitive and must not be published. |
| `Topics_Coder_A` | Created if missing | Yes | Coder A topic sequence. |
| `Topics_Coder_B` | Created if missing | Yes | Coder B topic sequence. |
| `Topics_Coder_C` | Created if missing | Yes | Coder C topic sequence. |
| `Topics_Harmonized` | No | Created if missing | Final harmonized topic sequence. |

## Local Column Mapping

If the private workbook uses different column names, configure them locally:

```bash
export TOPICS_HARMONIZATION_FILE="/absolute/path/to/private/Topics_Harmonization.xlsx"
export TOPICS_CODER_A_COL="private_column_name_for_coder_a"
export TOPICS_CODER_B_COL="private_column_name_for_coder_b"
export TOPICS_CODER_C_COL="private_column_name_for_coder_c"
export TOPICS_HARMONIZED_COL="Topics_Harmonized"
```

Do not commit shell profiles, `.env` files, or notebooks that reveal sensitive local paths or private column names.

## Minimal Workbook for Manual Coding

The manual coding app can start from:

```text
question
response
```

It will create the configured coder columns if they are missing.

## Minimal Workbook for Harmonization

The harmonization app requires:

```text
question
response
Topics_Coder_A
Topics_Coder_B
Topics_Coder_C
```

It will create `Topics_Harmonized` if it is missing.
