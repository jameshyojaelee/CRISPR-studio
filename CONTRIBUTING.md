# Contributing to CRISPR-studio

Thanks for helping improve CRISPR-studio! This guide covers environments, testing, and expectations for pull requests.

## Environment
- Python 3.11+ (CI runs 3.11 & 3.12). Create a venv with `python3.11 -m venv .venv && source .venv/bin/activate`.
- Install dev dependencies: `make install` (installs `. [dev,docs]`).
- Optional lint autofix: `make lint-fix` (runs `ruff --fix`). Set up `pre-commit` with `pre-commit install` to keep hooks consistent.
- Sample data lives in `sample_data/`; templates are under `templates/data_contract/`. Validate new datasets with:  
  `python scripts/validate_dataset.py sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json`

## Development workflow
- Lint/type-check: `make lint` (ruff + mypy).
- Tests: `make test` (pytest). Dash UI tests are marked `@pytest.mark.dash`; run them with `pytest -m dash` when changing layout/callbacks.
- Benchmarks (optional): `python scripts/benchmark_pipeline.py --dataset-size small --repeat 1 --jsonl artifacts/benchmarks/dev.jsonl --plot`.
- API example: `make api-example` spins up uvicorn briefly and exercises `examples/api_client.py`.

## Pull requests
- Describe the user-facing change and include repro info if fixing a bug (sample file paths help).
- Add/adjust tests and docs for new behavior.
- Keep commits focused; avoid reformatting unrelated files.
- Adhere to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Reporting issues
When filing bugs, include:
- OS, Python version, and extras installed.
- Exact command or UI action taken.
- Sample counts/library/metadata files or redacted snippets.
- Logs (`logs/crispr_studio.log`) and any warnings from the UI/CLI.
