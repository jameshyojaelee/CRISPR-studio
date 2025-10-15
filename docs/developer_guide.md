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

## Writing Tests

- Unit tests should cover success + failure paths (e.g., contract violations).
- Integration tests (`tests/test_pipeline_demo.py`) run the full pipeline on the synthetic dataset; ensure they remain fast (<5 s).
- Run `pytest --cov=crispr_screen_expert` before submitting changes.

## Benchmark Script

- `scripts/benchmark_pipeline.py` measures end-to-end runtime. Use to guard regressions on HPC nodes.
- For reproducibility, pin the module load command and ensure `.venv` uses Python 3.11.

## Logging & Troubleshooting

- Logs are stored in `logs/crispr_studio.log` (rotation weekly). Adjust level via `LOG_LEVEL` env var.
- Dash callbacks rely on background jobs; if UI appears idle, inspect `STORE_JOB` values via browser dev-tools or review logs for exceptions.

## Non-Goals

- Single-cell CRISPR analytics, CRISPRi/a design, and active learning are out of scope for this repo.
- SaaS multi-tenant auth, billing, or production hosting scripts are not part of this prototype.
