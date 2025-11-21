# Data Contract — CRISPR-studio Demo & Pipeline Inputs

This document defines the required structure for datasets consumed by CRISPR-studio. All files use UTF-8 encoding and ASCII characters.

## 1. sgRNA Count Matrix (`.csv` or `.tsv`)

- **Shape:** rows represent individual sgRNAs; columns represent experimental samples.
- **Required columns:** every biological sample referenced in the metadata JSON, with consistent casing.
- **Required index:** first column named `guide_id` (string). IDs should match entries in the library file.
- **Cell values:** non-negative integers representing raw read counts. Empty cells are not permitted; use `0` for absent reads.
- **Delimiter detection:** comma (CSV) or tab (TSV) accepted. Header row mandatory.
- **Example columns:** `guide_id,CTRL_A,CTRL_B,TREAT_A,TREAT_B`.

### Validation Rules
- Every guide in the count matrix must exist in the library annotation.
- No duplicate `guide_id` rows.
- Sample column names must appear exactly in the metadata `samples[].column`.
- Counts should be within a feasible range (0–50,000 for typical pooled screens).

## 2. Library Annotation (`.csv`)

- **Columns (required):**
  - `guide_id`: string, unique per row.
  - `gene_symbol`: string, HGNC-style upper-case gene name or `NTC` for non-targeting controls.
- **Columns (optional):**
  - `weight`: float (defaults to `1.0`), used to weight guides during aggregation.
  - Additional metadata columns (e.g., `sequence`, `notes`) are preserved but ignored by the core pipeline.
- **Constraints:** exactly one row per `guide_id`. Gene symbols should be uppercase alphanumeric characters with `_` if needed.

## 3. Experiment Metadata (`.json`)

Top-level keys:

```json
{
  "experiment_name": "Demo Dropout Screen",
  "screen_type": "dropout",
  "fdr_threshold": 0.1,
  "samples": [
    {
      "sample_id": "CTRL_A",
      "column": "CTRL_A",
      "condition": "control",
      "replicate": "A",
      "role": "control"
    },
    {
      "sample_id": "CTRL_B",
      "column": "CTRL_B",
      "condition": "control",
      "replicate": "B",
      "role": "control"
    },
    {
      "sample_id": "TREAT_A",
      "column": "TREAT_A",
      "condition": "treatment",
      "replicate": "A",
      "role": "treatment"
    },
    {
      "sample_id": "TREAT_B",
      "column": "TREAT_B",
      "condition": "treatment",
      "replicate": "B",
      "role": "treatment"
    }
  ],
  "analysis": {
    "scoring_method": "mageck",
    "enable_pathway": true,
    "enable_llm": false
  }
}
```

### Field Definitions
- `screen_type`: `"dropout"` or `"enrichment"`; determines fold-change sign conventions.
- `samples`: list describing each column in the counts matrix. `replicate` values group biological replicates. `role` accepts `"control"`, `"treatment"`, `"neutral"`, or `"exclude"`.
- `analysis` (optional): toggles and thresholds for downstream modules.

### Validation Rules
- `sample_id` and `column` must be unique.
- There must be at least one control and one treatment sample.
- Replicate labels may repeat across conditions (e.g., `A`, `B`) but pairings must make sense (control A vs. treatment A).
- Fields outside the schema are ignored but preserved for reporting.

### Templates
- `templates/data_contract/counts_template.csv` — sample counts header plus example values.
- `templates/data_contract/library_template.csv` — guide-to-gene mapping with optional weight column.
- `templates/data_contract/metadata_template.json` — Pydantic-compatible metadata stub with control/treatment samples.

## 4. Derived Artifacts (Pipeline Output)

While not inputs, downstream components produce standardized outputs:
- `artifacts/<timestamp>/normalized_counts.csv`
- `artifacts/<timestamp>/gene_results.csv`
- `artifacts/<timestamp>/qc_metrics.json`
- `artifacts/<timestamp>/pathway_results.csv`
- `artifacts/<timestamp>/report.html` (and optional PDF)

These artifacts inherit metadata from the input files to ensure reproducibility.

## 5. Demo Dataset Guarantee

Sample files in `sample_data/` conform to this contract:
- `demo_counts.csv`
- `demo_library.csv`
- `demo_metadata.json`

Use the generator script (`scripts/generate_demo_dataset.py`) to recreate or customize synthetic data while maintaining compatibility.

## 6. Validation Script & Fix Checklist

Run `python scripts/validate_dataset.py sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json` to lint a dataset without hitting external services (`--skip-annotations`).

Common fixes suggested by the script:
- Remove duplicate `guide_id` rows and duplicate sample columns.
- Ensure every metadata sample appears in the counts header.
- Keep counts non-negative integers (replace blanks with 0).
- Align library gene symbols to uppercase HGNC-like names and include all guides present in the counts file.

Add `--export-samples normalized_samples.json` to emit a normalised sample manifest for downstream automation.
