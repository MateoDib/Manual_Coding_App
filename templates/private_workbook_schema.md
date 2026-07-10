# Private Workbook Schema

The applications expect local Excel workbooks. These files are not included in the repository.

## Workbook 1: `coding_interview_base.xlsx`

This workbook is used for independent manual coding.

Minimum columns:

```text
question
response
```

Coder columns are created or expected according to the local coder configuration.

Default for three coders:

```text
Topics_Coder_1
Topics_Coder_2
Topics_Coder_3
```

## Workbook 2: `harmonization_interview_base.xlsx`

After all coders have added their columns, copy `coding_interview_base.xlsx` to `harmonization_interview_base.xlsx`.

The harmonization input must contain:

```text
question
response
Topics_Coder_1
Topics_Coder_2
...
Topics_Coder_N
```

## Workbook 3: `harmonized_interview_base.xlsx`

The harmonization app writes the final output to this workbook. It contains the coder columns plus:

```text
Topics_Harmonized
```

If this output workbook already exists, the harmonization app resumes from it.

## Configuring the Number of Coders

Use:

```bash
export TOPICS_CODER_COUNT=2
```

or explicit columns:

```bash
export TOPICS_CODER_COLUMNS="Coder_A_Topics,Coder_B_Topics,Coder_C_Topics,Coder_D_Topics"
```

## Configuring Workbook Paths

```bash
export INTERVIEW_WORKBOOK_DIR="/absolute/path/to/private/workbooks"
export CODING_INTERVIEW_BASE="coding_interview_base.xlsx"
export HARMONIZATION_INTERVIEW_BASE="harmonization_interview_base.xlsx"
export HARMONIZED_INTERVIEW_BASE="harmonized_interview_base.xlsx"
```

## Configuring Required Ending Nodes

The default ending nodes are the ones used in the associated paper, but they can be changed in the app sidebar or through environment variables:

```bash
export ENABLE_REQUIRED_ENDING_NODES=1
export REQUIRED_ENDING_NODES="acceptability,unacceptability,ambivalent_acceptability"
```

Use `ENABLE_REQUIRED_ENDING_NODES=0` to disable them by default.

Do not commit `.env` files, shell profiles, notebooks, screenshots, or documents that reveal sensitive local paths or private data.
