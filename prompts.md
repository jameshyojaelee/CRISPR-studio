# Prompt: Polish Packaging & Releases
You are Codex working in the repo root. Complete the following:
1) Enforce Python 3.11+ across tooling: update README, setup.cfg classifiers if needed, and any scripts referencing python version. Add a short note about using `python3.11 -m venv` in Getting Started. Ensure Makefile and docs reference the minimum version consistently.
2) Prepare for PyPI publication: add a `pyproject`/README badge section describing extras (`[native]`, `[reports]`, `[benchmark]`), long_description content type is already set via README. Add `LICENSE`/`keywords` if missing. Ensure `project.urls` are present (homepage/repo/issues). Add a `CHANGELOG` entry for this release.
3) Add a slim Dockerfile target for CPU-only demo: multistage build, final image installs core + reports extra only, exposes Dash/API ports, uses a non-root user. Keep native builds optional as a build arg toggle (off by default).
4) Update CI: new job matrix for Python 3.11/3.12 (lint + tests) and keep packaging install checks. Ensure native job remains optional/flagged. Fail fast on unsupported Python.
5) Validate with `python3.11 -m pytest` (or python3.12) for core tests and `pip install .[reports]` in a fresh venv. Do not publish artifacts, just ensure tree is ready.

# Prompt: Colab/Notebook Quickstart
You are Codex working in the repo root. Build a Colab-friendly onboarding:
1) Add `notebooks/quickstart.ipynb` (or .py if preferred) that loads sample_data, runs validation and a short pipeline call (Mageck off), then visualizes top genes/warnings using plotly. Keep runtime <2 min and no external data fetches. If using notebook, keep outputs cleared.
2) Add a short `docs/notebooks.md` explaining how to launch in Colab/local, required extras (`pip install crispr_screen_expert[reports]`), and how to adapt to personal data paths.
3) Link this from README Quickstart and developer_guide. Include a badge/button for “Open in Colab” if feasible (pointing to repo notebook URL).
4) Add a minimal test (e.g., `tests/test_notebooks.py`) that ensures the notebook exists and can be executed headless with nbformat+nbconvert (skip on CI if too heavy).

# Prompt: API & Client Examples
You are Codex working in the repo root. Improve API consumability:
1) Add a `examples/api_client.py` demonstrating: submit job via FastAPI, poll status until finished, download artifacts. Use sample_data paths. Make it runnable via `python examples/api_client.py --host http://localhost:8000`.
2) Update `docs/developer_guide.md` and README API section with the example usage and curl equivalent.
3) Add a Makefile target `make api-example` that starts uvicorn in a bg (or instructs user) and runs the client script against it (lightweight).
4) Add a small test `tests/test_api_client_example.py` that imports the helper functions (no network) and validates payload construction; mark as unit/lightweight.

# Prompt: Data Contract & Validator UX
You are Codex working in the repo root. Strengthen researcher onboarding:
1) Add template files under `templates/data_contract/`: `counts_template.csv`, `library_template.csv`, `metadata_template.json` with commented headers/examples. Ensure they align with current Pydantic model expectations.
2) Create `scripts/validate_dataset.py` that wraps `data_loader`/`load_experiment_config`, prints actionable errors/warnings, and suggests fixes. Support `--skip-annotations` and optional output of normalized sample config.
3) Document this script in README and `docs/data_contract.md` with a quick “fix checklist” (duplicates, missing columns, non-numeric counts).
4) Add tests covering happy path + common failures (missing guide_id, duplicate columns, invalid metadata). Keep runtime fast and no network.

# Prompt: Dash UI & Demo Polish
You are Codex working in the repo root. Elevate the demo experience:
1) Add tooltips/helptext for QC metrics and warning badges in Dash (callbacks/layout), explaining severity and remediation hints.
2) Add a one-click “rerun last dataset” button that reuses cached uploads/settings (no re-upload). Ensure background JobManager handles it safely.
3) Bundle a sample HTML report link in the UI (download button pointing to artifacts/sample_report).
4) Update `docs/demo_runbook.md` and `docs/user_guide.md` to showcase the new controls and the warning de-duplication behavior.
5) Add UI snapshot/integration tests (Dash testing markers) covering the new buttons/tooltips, gated behind `-m dash`.

# Prompt: Performance & Native Benchmarks
You are Codex working in the repo root. Benchmark and document performance:
1) Extend `scripts/benchmark_pipeline.py` to optionally emit JSONL per run and summary plots (runtime vs size). Keep psutil guard intact. Add CLI flags for `--jsonl` and `--plot`.
2) Add docs page `docs/performance.md` summarizing expected runtimes/memory for small/medium/large, with and without native backends, citing benchmark script usage.
3) Add CI artifact upload for benchmark JSON (optional, nightly-only or behind a flag). Keep default CI fast.
4) Include recommendations for annotation cache prewarming and MyGene batch sizing for flaky networks.

# Prompt: Community & Contribution Readiness
You are Codex working in the repo root. Open up for contributors:
1) Add `CONTRIBUTING.md` and issue/PR templates (`.github/ISSUE_TEMPLATE/bug_report.md`, `feature_request.md`, `.github/pull_request_template.md`) tailored to this project (data repro steps, sample files).
2) Add `CODE_OF_CONDUCT.md` (Contributor Covenant) and reference from README.
3) Add a small roadmap/“help wanted” section in README pointing to issues.
4) Wire up a `make lint-fix` target (ruff --fix) and mention pre-commit hook advice (optional).
