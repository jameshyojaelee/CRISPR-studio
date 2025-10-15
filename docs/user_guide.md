# CRISPR-studio User Guide

## Installation

1. Ensure Python 3.11 is available (`module load Python/3.11.5-GCCcore-13.2.0` on the HPC environment).
2. Clone the repository and create a virtual environment:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   make install
   ```
3. Optionally, populate a `.env` file with settings:
   ```bash
   echo "OPENAI_API_KEY=your-key" >> .env
   echo "LOG_LEVEL=INFO" >> .env
   ```

## Command-Line Interface

Run `crispr-studio --help` to view commands. Common workflows:

- Validate inputs before analysis:
  ```bash
  crispr-studio validate-data sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json
  ```
- Execute the analysis pipeline (results stored in `artifacts/`):
  ```bash
  crispr-studio run-pipeline sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json --enrichr-libraries Reactome_2022
  ```
- List prior analyses and available artifacts:
  ```bash
  crispr-studio list-artifacts
  ```

## Dash Application

1. Launch the web UI locally:
   ```bash
   python app.py
   ```
   Visit `http://127.0.0.1:8050` in a browser.

2. Upload counts, library, and metadata files via the Upload tab. The configuration panel confirms metadata parsing (screen type, sample count, thresholds).

3. Click **Run Analysis**. Jobs execute in the background; the UI polls automatically until completion.

4. Explore results:
   - **Results** tab: summary cards, volcano plot, interactive gene table (select a row to view annotations in the modal).
   - **QC** tab: replicate correlation and detection heatmap with thresholds.
   - **Pathways** tab: bubble chart summarising Enrichr/GSEA output.
   - **Reports** tab: download an HTML summary; PDF export requires WeasyPrint.

## Interpreting Metrics

- **QC Badges**: Metrics surface `OK`, `WARNING`, or `CRITICAL`. Revisit library prep or sequencing if replicate correlations fall below 0.7 or detection ratios drop under 75%.
- **Significance Thresholds**: Default FDR ≤ 0.10; adjust via metadata (`analysis.fdr_threshold`) or CLI flags when invoking the pipeline.
- **Pathway Analysis**: Enrichr libraries configured with `--enrichr-libraries`. Interpret bubble radius as gene hits within the pathway; -log10(FDR) drives the x-axis.
- **Narratives**: Deterministic summaries always available. Enabling the OpenAI key appends AI-generated text labelled with caveats.

## Troubleshooting

- **Data Contract Violations**: `crispr-studio validate-data` highlights missing columns or mismatched guides. Ensure `guide_id` column exists and metadata sample IDs align with counts columns.
- **MAGeCK Missing**: Install from Bitbucket (`pip install /tmp/mageck-bitbucket`). The pipeline automatically falls back to RRA when MAGeCK fails or is unavailable.
- **WeasyPrint Not Installed**: HTML export remains available; install system dependencies and `pip install weasyprint` for PDF support.
- **Large Datasets**: Background jobs are queued (ThreadPoolExecutor). Monitor `logs/crispr_studio.log` for timings and warnings.

## Configure Analytics Opt-In

Analytics logging is disabled by default. Set `CRISPR_STUDIO__ENABLE_ANALYTICS=true` in `.env` to capture anonymised events (analysis started/completed, QC warnings) written under `analytics/`.
