# CRISPR-studio

![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)

I built CRISPR-studio so I could hand a single folder to collaborators and have them go from raw pooled-screen counts to a navigable report without babysitting R scripts. It's a one-person project, tuned for biological researchers who just want the analysis to run.

## What you get
- CLI + Dash app that load the same pipeline core, so results match whether you stay in a terminal or use the UI.
- Built-in data validator, cached annotations, sample HTML report, and a Colab notebook for quick sharing.
- Optional extras for PDF export (`[reports]`), runtime benchmarking (`[benchmark]`), and native speed-ups (`[native]`).

## Install quick start
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install .
# Extras when needed:
# pip install .[reports]
# pip install .[benchmark]
# pip install .[native]
```
Once installed, the `make` targets mirror the same steps (`make install`, `make test`, `make run-app`, etc.).

## Core workflows
- Validate your own files first:
  ```bash
  crispr-studio validate-data counts.csv library.csv metadata.json
  python scripts/validate_dataset.py counts.csv library.csv metadata.json --skip-annotations --export-samples artifacts/normalized_samples.json
  ```
- Run the pipeline (MAGeCK optional, RRA is the default):
  ```bash
  crispr-studio run-pipeline sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json --enrichr-libraries Reactome_2022
  ```
- Opt into native accelerators once they're built:
  ```bash
  crispr-studio run-pipeline ... --use-native-rra --use-native-enrichment
  ```
- List artifacts and re-share reports:
  ```bash
  crispr-studio list-artifacts
  make build-report  # refreshes artifacts/sample_report/
  ```

## Dash app
```bash
python app.py  # serves Dash on http://127.0.0.1:8050
```
Upload your counts, library, and metadata once, then use **Run Analysis** or **Rerun Last Dataset** to reuse cached inputs. Tooltips explain QC badges and warning colors. The **Reports** tab links to the bundled HTML summary so you can show something even if a fresh run fails. Logs land in `logs/crispr_studio.log` and you can set `LOG_LEVEL=DEBUG` while debugging.

## Notebook & Colab
There's a Colab-friendly notebook under `notebooks/quickstart.ipynb`. The badge below opens it directly—handy when you just want to validate `sample_data/` or demonstrate the pipeline without touching local files.

[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jameshyojaelee/CRISPR-studio/blob/main/notebooks/quickstart.ipynb)

`docs/notebooks.md` has the short instructions for Colab vs. local runs plus the one-line `pip install "crispr_screen_expert[reports]"` snippet.

## API & scripts
- Serve FastAPI: `python app_api.py` or `crispr-studio serve-api --host 0.0.0.0 --port 8000`.
- Example client: `python examples/api_client.py --host http://127.0.0.1:8000` (also wired into `make api-example`).
- Quick curl template:
  ```bash
  HOST=http://127.0.0.1:8000
  curl -X POST "$HOST/v1/analysis" \
       -H "Content-Type: application/json" \
       -d '{"counts_path":"sample_data/demo_counts.csv","library_path":"sample_data/demo_library.csv","metadata_path":"sample_data/demo_metadata.json","use_mageck":false,"skip_annotations":true}'
  ```

## Project layout
- `src/crispr_screen_expert/` – pipeline, CLI, API, and Dash code.
- `docs/` – focused references: `user_guide.md`, `data_contract.md`, `notebooks.md`.
- `sample_data/` – demo inputs that satisfy the contract plus matching templates under `templates/data_contract/`.
- `scripts/` – dataset validation, benchmark helper, and small utilities.
- `assets/`, `templates/`, `artifacts/` – front-end assets and generated outputs.

## Troubleshooting cheat sheet
- Annotation hiccups? Reduce batch size (`MYGENE_BATCH_SIZE=250`) or run with `--skip-annotations`; cached results keep you moving.
- Native build failing? Reinstall the `[native]` extra and rerun `maturin develop --manifest-path rust/Cargo.toml`, or just set `CRISPR_STUDIO_FORCE_PYTHON=1` and keep going.
- QC badge stuck at CRITICAL? Open `qc_metrics.json` inside the latest artifact folder—the detail there mirrors the UI tooltip.
- Need runtime numbers? `python scripts/benchmark_pipeline.py --dataset-size medium --repeat 2 --jsonl --plot` dumps JSONL and a small HTML plot. Install `pip install .[benchmark]` first.

## Documentation
- `docs/user_guide.md` – practical walkthrough that blends the CLI, Dash, performance notes, and troubleshooting tips in one place.
- `docs/data_contract.md` – what the counts, library, and metadata files must look like (plus the validation script checklist).
- `docs/notebooks.md` – Colab/local notebook notes.

This repo stays intentionally small on ceremony—it's just me maintaining it. Issues are welcome, but there is no formal contribution process or governance overhead.
