# CRISPR-studio User Guide

## Installation

1. Ensure Python 3.11+ is available (`module load Python/3.11.5-GCCcore-13.2.0` on the HPC environment; 3.12 also supported).
2. Clone the repository and create a virtual environment:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install --upgrade pip
   make install
   ```
3. (Optional) install native build prerequisites if you plan to use the accelerated modules:
   - **Linux**: `sudo apt-get install -y build-essential cmake ninja-build rustc cargo`
   - **macOS**: `brew install cmake ninja rustup` then run `rustup-init`
   - **Windows**: Install Visual Studio Build Tools (MSVC), CMake, Ninja, and Rust via `rustup`
4. Optionally, populate a `.env` file with settings:
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
- Offline validation with actionable hints and a normalized sample manifest:
  ```bash
  python scripts/validate_dataset.py sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json --export-samples artifacts/normalized_samples.json
  ```
- Run with native accelerators (requires the native modules to be built):
  ```bash
  crispr-studio run-pipeline sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json --use-native-rra --use-native-enrichment --enrichr-libraries native_demo
  ```
- List prior analyses and available artifacts:
  ```bash
  crispr-studio list-artifacts
  ```

## Native Acceleration

Native modules speed up robust rank aggregation and enrichment. Build them once per environment:

```bash
pip install .[native]
maturin develop --manifest-path rust/Cargo.toml --release
python -m scikit_build_core.build --wheel -S cpp -b cpp/build/user -o cpp/dist
pip install cpp/dist/*.whl
```

Set `CRISPR_STUDIO_USE_NATIVE_RRA=1` and/or `CRISPR_STUDIO_USE_NATIVE_ENRICHMENT=1` to force-enable native paths globally. Use `CRISPR_STUDIO_FORCE_PYTHON=1` to temporarily disable all native extensions. When a backend is missing or raises an error the pipeline logs a warning and automatically falls back to the Python implementation.

| Dataset profile | Recommended backend |
| --- | --- |
| Exploratory (<5k guides) | Pure Python |
| Production (~20k guides) | Native RRA (optionally native enrichment) |
| Genome-scale (≥100k guides) | Native RRA + native enrichment |

## Dash Application

1. Launch the web UI locally:
   ```bash
   python app.py
   ```
   Visit `http://127.0.0.1:8050` in a browser.

2. Upload counts, library, and metadata files via the Upload tab. The configuration panel confirms metadata parsing (screen type, sample count, thresholds).

3. Click **Run Analysis**. Jobs execute in the background; the UI polls automatically until completion. Use **Rerun Last Dataset** to reuse cached uploads/settings without re-uploading files.

4. Explore results:
   - **Results** tab: summary cards, volcano plot, interactive gene table (select a row to view annotations in the modal).
   - **QC** tab: replicate correlation and detection heatmap with thresholds. Hover the info badges for remediation hints; CRITICAL/WARNING badges are de-duplicated before display.
   - **Pathways** tab: bubble chart summarising Enrichr/GSEA output.
   - **Reports** tab: download an HTML summary or the bundled sample preview; PDF export requires the reports extra (`pip install .[reports]`). A bundled sample HTML report is always available under `artifacts/sample_report/`.

## Interpreting Metrics

- **QC Badges**: Metrics surface `OK`, `WARNING`, or `CRITICAL`. Revisit library prep or sequencing if replicate correlations fall below 0.7 or detection ratios drop under 75%.
- **Significance Thresholds**: Default FDR ≤ 0.10; adjust via metadata (`analysis.fdr_threshold`) or CLI flags when invoking the pipeline.
- **Pathway Analysis**: Enrichr libraries configured with `--enrichr-libraries`. Interpret bubble radius as gene hits within the pathway; -log10(FDR) drives the x-axis.
- **Narratives**: Deterministic summaries always available. Enabling the OpenAI key appends AI-generated text labelled with caveats.

## Troubleshooting

- **Data Contract Violations**: `crispr-studio validate-data` highlights missing columns or mismatched guides. Ensure `guide_id` column exists and metadata sample IDs align with counts columns.
- **MAGeCK Missing**: Install from Bitbucket (`pip install /tmp/mageck-bitbucket`). The pipeline automatically falls back to RRA when MAGeCK fails or is unavailable.
- **Native build failures**: Confirm platform prerequisites (compilers, CMake, Ninja, Rust) are installed and run the build commands from a clean virtual environment. Review `cpp/build/*/CMakeOutput.log` or `rust/target` logs for details.
- **Native RRA/enrichment unavailable**: If the native module fails to import, set `CRISPR_STUDIO_FORCE_PYTHON=1` to continue with the Python fallback and rebuild the extension later.
- **WeasyPrint Not Installed**: HTML export remains available; install system dependencies and `pip install .[reports]` for PDF support.
- **Large Datasets**: Background jobs are queued (ThreadPoolExecutor). Monitor `logs/crispr_studio.log` for timings and warnings.

## Configure Analytics Opt-In

Analytics logging is disabled by default. Set `CRISPR_STUDIO__ENABLE_ANALYTICS=true` in `.env` to capture anonymised events (analysis started/completed, QC warnings) written under `analytics/`.

## FAQ

- **MAGeCK works but native RRA fails to build** – rebuild the Rust extension (`maturin develop --manifest-path rust/Cargo.toml --release`) and ensure the toolchain requirements are installed. Until then, rely on the Python fallback (`CRISPR_STUDIO_FORCE_PYTHON=1`).
- **Can I disable native enrichment only?** – yes, either unset `CRISPR_STUDIO_USE_NATIVE_ENRICHMENT` or pass `--use-native-enrichment/--no-use-native-enrichment` through the CLI when running pipelines.
- **Where are native gene sets stored?** – the demo ships with `resources/enrichment/native_demo.json`. Provide your own JSON mapping of `{ "library": { "set_name": [genes...] } }` to extend it.
