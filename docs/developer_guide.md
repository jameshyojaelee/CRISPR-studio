# Developer Guide

## Architecture Overview

```
┌────────────────────────────┐
│ Dash UI (src/.../app)      │
│  • layout.py               │
│  • callbacks.py            │
│  • visualization.py        │
└──────────────┬─────────────┘
               │ interacts via stores + background jobs
┌──────────────▼─────────────┐
│ Pipeline (pipeline.py)     │
│  • data_loader             │
│  • normalization/rra/mageck│
│  • enrichment/annotations  │
│  • narrative/reporting     │
└──────────────┬─────────────┘
               │ emits AnalysisResult + artifacts
┌──────────────▼─────────────┐
│ CLI (cli.py)               │
│ Scripts/tests              │
└────────────────────────────┘
```

Core modules:

- `data_loader.py`: strict contract enforcement for counts/library/metadata; raises `DataContractError` on failure.
- `normalization.py`, `qc.py`, `rra.py`: numpy/pandas transformations with unit tests.
- `pipeline.py`: orchestrates the full analysis, persisting artifacts and narratives, using `PipelineSettings` for options.
- `background.py`: thread pool manager + dataset caching for Dash.
- `app/`: Dash layout and callbacks; state stored in `dcc.Store` and updated via polling interval.
- `reporting.py`: Jinja2 + optional WeasyPrint export.
- `config.py` / `logging_config.py`: centralised settings and loguru configuration.

## FastAPI Service

- Module: `src/crispr_screen_expert/api.py` exposes a FastAPI app with the following endpoints (all expect the `X-API-Key` header when `Settings.api_key` is set):
  - `POST /v1/analysis` – submit an analysis job. Body: `counts_path`, `library_path`, `metadata_path` (server-accessible paths) plus optional toggles (`use_mageck`, `use_native_rra`, `enrichr_libraries`, etc.). Returns `job_id`.
  - `GET /v1/analysis/{job_id}` – poll job status. Response includes `status` (`queued`, `running`, `finished`, `failed`), optional `summary`, and `warnings`/`error` fields when available.
  - `GET /v1/analysis/{job_id}/artifacts` – list named artifact paths once a job completes successfully.
  - `GET /v1/analysis/{job_id}/artifacts/{name}` – download a specific artifact file (e.g., `analysis_result.json`).
  - `GET /v1/openapi` – returns the OpenAPI schema (used by `scripts/export_openapi.py`).
- Long-running work is delegated to the shared `JobManager` thread pool. Results and errors are cached in-memory for quick polling.
- API settings derive from `Settings` (`ARTIFACTS_DIR`, `UPLOADS_DIR`, etc.). Set `API_KEY` in the environment (or `.env`) to enforce header-based authentication.
- Launch options:
  - CLI: `crispr-studio serve-api --host 0.0.0.0 --port 8000`
  - Uvicorn entrypoint: `python app_api.py`
  - Docker Compose service: `docker-compose up api`
- `scripts/export_openapi.py` emits `artifacts/api_schema.json` for documentation portals or client generation.

## Native Accelerators

- `src/crispr_screen_expert/native/rra.py` wraps the Rust crate `crispr_native_rust` (see `rust/`).
- Enable the accelerated path with `PipelineSettings(use_native_rra=True)` or `crispr-studio run-pipeline ... --use-native-rra` after building the native wheels.
- When the backend is unavailable or raises an exception, the pipeline emits a warning and falls back to the Python implementation in `rra.py`.
- Native parity tests live in `tests/test_native_rra.py` and compare outputs against the Python baseline.
- `src/crispr_screen_expert/native/enrichment.py` uses the C++ module `crispr_native` to perform batch hypergeometric enrichment. Toggle via `PipelineSettings(use_native_enrichment=True)`/`--use-native-enrichment` (libraries default to the bundled `native_demo`).
- The wrapper provides synchronous and async APIs, applies Benjamini–Hochberg correction in Python, and falls back to the gseapy-powered implementation when the native backend is unavailable.
- Environment overrides: `CRISPR_STUDIO_USE_NATIVE_RRA/CRISPR_STUDIO_USE_NATIVE_ENRICHMENT` opt-in to native paths, while `CRISPR_STUDIO_FORCE_PYTHON=1` disables them globally.

## Coding Conventions

- Use type hints and descriptive docstrings.
- Prefer `Path` objects to raw strings for file IO.
- All new functions should log meaningful events via `get_logger`.
- Tests live under `tests/`; add fixtures in `conftest.py` when sharing setup.
- Keep uploads and artifacts under directories supplied by `Settings` to respect environment overrides.

## Adding New Scoring Methods

1. Implement the scoring function in a dedicated module (e.g., `src/.../scoring_new.py`).
2. Update `PipelineSettings` to expose toggles if needed.
3. Modify `pipeline.run_analysis` to branch based on settings and merge DataFrame output with the existing schema (columns: gene, score, p_value, fdr, rank).
4. Add unit tests covering edge cases; extend integration test if behaviour changes.

## Extending Pathway Catalogs

- Use `enrichment.run_enrichr` for Enrichr libraries or `run_gsea` for custom `.gmt` sets.
- To add local gene sets, drop files into `resources/pathways/` (create directory) and point `run_gsea` at the path via CLI option or settings.
- Update docs to reflect new options.

## Gene Annotation Fetching

- `annotations.fetch_gene_annotations` batches MyGene.info requests in groups of ≤500 symbols and reuses a shared `requests.Session` to avoid triggering rate limits. Set `MYGENE_BATCH_SIZE` (clamped to 500) if you need smaller bursts for constrained networks.
- Each successful batch updates `.cache/gene_cache.json` immediately so the cache stays warm even if later batches fail. When a cache file is corrupted, it is renamed to `cache.json.bak_<timestamp>` before being rewritten.
- Warning messages are aggregated per run and include the batch index, HTTP status (when available), and the number of skipped genes, e.g., `batch 3 (HTTP 503, 200 genes skipped)`. Missing annotations still trigger a single summary warning.
- For air‑gapped demos, use the CLI `--skip-annotations` flag or `PipelineSettings(cache_annotations=False)` to bypass MyGene.info entirely. The Dash UI inherits the cached annotations and warning summaries from the pipeline artifacts.

## Writing Tests

- Unit tests should cover success + failure paths (e.g., contract violations).
- Integration tests (`tests/test_pipeline_demo.py`) run the full pipeline on the synthetic dataset; ensure they remain fast (<5 s).
- Run `pytest --cov=crispr_screen_expert` before submitting changes.

## Benchmark Script

- `scripts/benchmark_pipeline.py` now generates synthetic datasets under `benchmarks/data/<size>/` (small, medium, large) and benchmarks the pipeline end-to-end.
- Key CLI options:
  - `--dataset-size {small,medium,large}` selects guide/replicate counts.
  - `--repeat N` averages metrics over multiple runs.
  - `--use-native-rra/--no-use-native-rra` toggles native benchmarking alongside the Python baseline.
- Outputs are written to `artifacts/benchmarks/<timestamp>/` as `metrics.json` (machine readable) and `summary.md` (human summary). Per-run metrics include wall-clock runtime, CPU seconds, CPU%, and RSS memory via `psutil`.
- When the native backend is executed, the script performs a parity check against the Python results and surfaces the maximum absolute delta.
- Large CSV/JSON datasets are generated on demand and ignored by git via `benchmarks/data/.gitignore`.

## Profiling Tooling

- Set `ENABLE_PROFILING=1` before running any profiling scripts to avoid accidental use in production environments.
- `scripts/profile_python.sh [counts library metadata]` captures a cProfile dump and (if available) a `py-spy` flamegraph of the Python orchestration layer. Outputs land in `artifacts/profiles/python/<timestamp>/`.
- `scripts/profile_native.sh [counts library metadata]` drives system profilers (`perf` and `valgrind --tool=callgrind`) against the native backends, writing artefacts to `artifacts/profiles/native/<timestamp>/`. When the `FLAMEGRAPH_DIR` environment variable points to the Brendan Gregg FlameGraph utilities, a perf flamegraph SVG is also generated.
- Optional environment variables: `PROFILING_OUTPUT` overrides the artefact root, `PERF_FREQ` tunes the perf sampling frequency.
- Review outputs with tools such as `snakeviz`/`runsnake`, `py-spy top`, `kcachegrind`, or `speedscope`. Delete or archive large artefacts after use to keep the repository tidy.

## Logging & Troubleshooting

- Logs are stored in `logs/crispr_studio.log` (rotation weekly). Adjust level via `LOG_LEVEL` env var.
- Dash callbacks rely on background jobs; if UI appears idle, inspect `STORE_JOB` values via browser dev-tools or review logs for exceptions.

## Non-Goals

- Single-cell CRISPR analytics, CRISPRi/a design, and active learning are out of scope for this repo.
- SaaS multi-tenant auth, billing, or production hosting scripts are not part of this prototype.
