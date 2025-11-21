# Contributing to CRISPR-studio

Thanks for helping improve CRISPR-studio! This guide covers how to propose changes and what information helps us review quickly.

## Quickstart
- Use Python 3.11+.
- Create a virtualenv: `python3.11 -m venv .venv && source .venv/bin/activate`.
- Install deps: `make install` (pulls dev + docs extras).
- Format/lint: `make lint` and `make lint-fix` (ruff + mypy).
- Tests: `make test`. Dash UI tests are marked `-m dash`; run selectively for UI changes.
- API smoke: `make api-example` exercises the FastAPI client against a local uvicorn server.

## PR Checklist
- Describe the bug/feature and link to any issues.
- Include reproduction details and sample data paths (e.g., `sample_data/demo_counts.csv`) or attach minimal CSV/JSON snippets.
- Add/adjust tests for new behaviors; keep runtime short (<5s for unit tests).
- For data contract or pipeline changes, update docs (`docs/data_contract.md`, `docs/user_guide.md`) and templates under `templates/data_contract/`.
- For UI work, note any new Dash elements and ensure accessibility (tooltips/helptext where relevant).

## Issue Reports
- Include steps to reproduce, expected vs actual behavior, stack traces/log snippets, and environment details (`python --version`, OS).
- Provide sample files or point to `sample_data/` equivalents that trigger the issue.
- For performance issues, share dataset size, repeat count, and whether native backends were enabled.

## Code Style & Tooling
- Ruff handles formatting (`make lint-fix`); mypy is configured for type checks.
- Target Python 3.11+; keep code ASCII unless there is a strong reason otherwise.
- Prefer small, focused commits; avoid force-pushing after review has started unless requested.

## Security & Conduct
- Follow the [Code of Conduct](CODE_OF_CONDUCT.md).
- Do not commit secrets or proprietary data. Use `.env` for local secrets and `.gitignore` respects `artifacts/` by default.
