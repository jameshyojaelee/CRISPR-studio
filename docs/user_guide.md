# CRISPR-studio Field Guide

Thanks for checking out my personal CRISPR screen toolkit. This guide is written for researchers who just need clear steps—no product fluff, no multi-team handoffs.

## Before you start
- Python 3.11+ only. I build/test with 3.11 and 3.12.
- Create a fresh virtual environment. I use:
  ```bash
  python3.11 -m venv .venv
  source .venv/bin/activate
  pip install --upgrade pip
  pip install .
  ```
- Extras:
  - `pip install .[reports]` for kaleido + WeasyPrint so PDF export works.
  - `pip install .[benchmark]` for psutil-backed runtime checks.
  - `pip install .[native]` if you feel like compiling the Rust/C++ accelerators.
- Optional `.env` entries: `OPENAI_API_KEY`, `LOG_LEVEL`, and overrides such as `CRISPR_STUDIO__ARTIFACTS_DIR`.

## Command-line flow
1. **Validate your files** (do this before any heavy analysis):
   ```bash
   crispr-studio validate-data counts.csv library.csv metadata.json
   python scripts/validate_dataset.py counts.csv library.csv metadata.json --skip-annotations --export-samples artifacts/normalized_samples.json
   ```
   The script version prints friendlier suggestions (missing guide IDs, duplicate columns, non-numeric counts).
2. **Run the pipeline** on the bundled demo data or your own:
   ```bash
   crispr-studio run-pipeline sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json --enrichr-libraries Reactome_2022
   ```
   Useful toggles:
   - `--skip-annotations` for air-gapped demos.
   - `--use-native-rra`, `--use-native-enrichment` once the native wheels are installed.
   - `--use-mageck false` to stay entirely within the RRA path.
3. **Check artifacts**: `crispr-studio list-artifacts` shows the folders created under `artifacts/<timestamp>/`.
4. **Benchmark or profile when curious**:
   ```bash
   python scripts/benchmark_pipeline.py --dataset-size medium --repeat 2 --jsonl --plot
   ```
   Outputs land under `artifacts/benchmarks/<timestamp>/` as JSONL, markdown summaries, and a simple HTML runtime plot.

## Dash walkthrough
1. Run `python app.py` and open `http://127.0.0.1:8050`.
2. Upload counts/library/metadata once. They stay cached so **Rerun Last Dataset** can replay without re-uploading.
3. Hover the QC badges for hints on what each severity level means; CRITICAL stops the CLI but still surfaces details in the UI.
4. The **Results** tab shows the volcano plot and gene table. Click any row to see annotations, run-specific warnings, and narratives (LLM text appears only if you add an OpenAI key).
5. The **QC** tab contains correlation/detection charts with tooltips that explain remediation ideas.
6. The **Reports** tab always includes the bundled sample HTML report plus fresh exports if the latest run succeeded. Use this when demoing—the page works even when the live pipeline hiccups.
7. Logs live at `logs/crispr_studio.log`; set `LOG_LEVEL=DEBUG` if something feels off.

## Performance and native notes
| Dataset profile | Approx runtime (Python path) | Tips |
| --- | --- | --- |
| 1k guides, 4 reps | 10–15 s | Leave everything pure Python. |
| 20k guides, 6 reps | 75–110 s | Consider native RRA (`pip install .[native]`). |
| 100k guides, 8 reps | 5–7 min | Use both native toggles; prewarm annotation cache. |

- Native builds: `maturin develop --manifest-path rust/Cargo.toml` and `python -m scikit_build_core.build -S cpp -b cpp/build && pip install cpp/build/*.whl`.
- Force modes: set `CRISPR_STUDIO_USE_NATIVE_RRA=1` / `CRISPR_STUDIO_USE_NATIVE_ENRICHMENT=1` or `CRISPR_STUDIO_FORCE_PYTHON=1` if the builds act up.
- Annotation cache: a quick run without `--skip-annotations` hydrates `.cache/gene_cache.json`. For flaky networks set `MYGENE_BATCH_SIZE=250`.

## Troubleshooting quick hits
- **Annotations warning** like `batch 2 (HTTP 503, 200 genes skipped)` → rerun later or flip on `--skip-annotations`. Failed batches are retried; the cache prevents re-downloading everything.
- **Native module missing** → reinstall the `[native]` extra and rebuild, or move on with the Python fallback. The UI and CLI both show a single warning, not a wall of duplicates.
- **QC hard stop** → the CLI exits when any metric hits CRITICAL. Open the matching `qc_metrics.json` file to see why (low replicate correlation, detection drop, etc.).
- **MAGeCK unavailable** → either install MAGeCK manually or stick with RRA by passing `--use-mageck false`.
- **Want to demo without surprises** → pre-run `crispr-studio run-pipeline ... --skip-annotations` so artifacts exist before you screen-share. Keep screenshots handy under `artifacts/sample_report/`.

## API and automation
- Launch: `python app_api.py` or `crispr-studio serve-api --host 0.0.0.0 --port 8000`.
- Client helper: `python examples/api_client.py --host http://127.0.0.1:8000` (relies on `sample_data/`).
- Tests: `pytest -k api_client_example` ensures the payload builder keeps working; the rest of the suite lives under `tests/` and runs quickly on the demo data.

## Notebook pathway
If you prefer a guided notebook, open the Colab badge in the README or run the notebook locally from the repo root so the relative paths work. The notebook loads `sample_data/`, turns off MAGeCK, skips annotations, and draws quick Plotly figures; edit the `DATA_DIR` cell to point at your own files.

## Data templates and validation
- Templates for counts/library/metadata live in `templates/data_contract/` and align with the rules in `docs/data_contract.md`.
- `scripts/validate_dataset.py` supports `--skip-annotations` and `--export-samples` to emit a normalized manifest.
- The CLI and Dash use the same validation logic, so once a dataset passes here it will load everywhere.
