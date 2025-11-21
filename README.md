# CRISPR-studio

- [![PyPI](https://img.shields.io/pypi/v/crispr_screen_expert)](https://pypi.org/project/crispr_screen_expert/)
- ![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)
- ![License: MIT](https://img.shields.io/badge/license-MIT-green)
- ![Extras](https://img.shields.io/badge/extras-native%20%7C%20reports%20%7C%20benchmark-6B7280)

- CRISPR-studio is a next-generation analysis and visualization toolkit that turns pooled CRISPR screen data into interactive biological insights.
- Scope: automated QC, MAGeCK-compatible hit calling, pathway enrichment, curated gene context, and narrative-ready reporting for demos and admissions showcases.
- Note: This release is an active development build and is not production ready.

**Extras on PyPI**
- `[reports]` — kaleido + WeasyPrint for HTML/PDF exports.
- `[native]` — Rust/C++ accelerators for RRA and enrichment backends.
- `[benchmark]` — psutil-backed runtime + memory benchmarking helpers.

## Project Layout
- `src/crispr_screen_expert/` – core pipeline, CLI, and Dash app code.
- `docs/` – product overview, runbooks, and compliance notes; see `docs/overview.md` for positioning.
- `docs/reference/mageck/` – upstream MAGeCK report template and helper script for manual HTML notebooks.
- `sample_data/` – synthetic demo inputs that satisfy the documented data contract.
- `scripts/` – utilities for dataset generation and maintenance tasks.
- `assets/` / `templates/` – UI assets used by the Dash front-end.

## Getting Started

### Prerequisites
- Python 3.11+ (tested on 3.11/3.12; manage via `pyenv` or system package manager)
- A virtual environment tool such as `python3.11 -m venv` or `conda`
- (Optional) Native toolchains for performance modules:
  - GCC ≥ 11 or Clang ≥ 14 (or MSVC 2019 on Windows)
  - CMake ≥ 3.22 and Ninja ≥ 1.11
  - Rust toolchain (`rustup` recommended)

### Installation
```bash
python3.11 -m venv .venv  # use python3.12 if preferred; minimum version is 3.11
source .venv/bin/activate
pip install --upgrade pip
pip install .
# Optional extras:
# pip install .[reports]   # PDF export + SVG rendering (kaleido + WeasyPrint)
# pip install .[benchmark] # psutil-backed benchmarking utilities
```
Alternatively, use the provided `Makefile` targets once dependencies are installed (described below).

### Makefile Targets
| Target | Description |
| --- | --- |
| `make install` | Install the package with development extras. |
| `make lint` | Run `ruff` and `mypy` linting. |
| `make format` | Apply formatting fixes via `ruff --fix`. |
| `make test` | Execute the pytest suite with coverage once tests exist. |
| `make run-app` | Launch the Dash web application (placeholder). |
| `make build-report` | Build static reports (placeholder). |
| `make benchmark` | Install benchmark extras and run the synthetic benchmark script. |
| `make clean` | Remove build artifacts and caches. |

Manual equivalents:
- `ruff check .` / `ruff check --fix .`
- `mypy src`
- `pytest --cov=crispr_screen_expert`

### Native Extensions (Optional)
Native backends provide accelerated implementations for compute-intensive steps such as robust rank aggregation and permutation testing. Python remains the orchestrator; these modules are optional.

```bash
# Install build dependencies
pip install .[native]

# Build the Rust backend with maturin
maturin develop --manifest-path rust/Cargo.toml

# Build the C++ backend with scikit-build-core
python -m scikit_build_core.build -S cpp -b cpp/build/dev
pip install cpp/build/dev/*.whl  # install the generated wheel
```

Flags such as `CRISPR_NATIVE_ENABLE_OPENMP=0`, `CRISPR_NATIVE_SANITIZER=address`, or `CRISPR_NATIVE_USE_NATIVE_ARCH=ON` can be exported before invoking the builds to toggle OpenMP, sanitizers, or architecture-specific optimisations.

Once native wheels are installed, enable the accelerated paths via the CLI (`--use-native-rra`, `--use-native-enrichment`) or programmatically with `PipelineSettings(use_native_rra=True, use_native_enrichment=True)`. If a backend is unavailable at runtime the pipeline falls back to the pure-Python implementation and records a warning.

**Platform prerequisites**

- **Linux (Debian/Ubuntu)** – `sudo apt-get update && sudo apt-get install -y build-essential cmake ninja-build rustc cargo`
- **macOS** – `brew install cmake ninja rustup` followed by `rustup-init` (restart the shell to update `PATH`)
- **Windows** – Install [Visual Studio Build Tools](https://visualstudio.microsoft.com/downloads/), CMake, and Ninja; install Rust via [`rustup`](https://rustup.rs/). Run the above pip commands from an MSVC x64 developer prompt.

To build the Docker image with native modules precompiled, pass `--build-arg BUILD_NATIVE=1` (`BUILD_NATIVE=1 docker compose build`).

Environment toggles:

- `CRISPR_STUDIO_USE_NATIVE_RRA=1` / `CRISPR_STUDIO_USE_NATIVE_ENRICHMENT=1` force-enable native paths.
- `CRISPR_STUDIO_FORCE_PYTHON=1` disables all native extensions (useful for debugging or constrained environments).
- `ENABLE_PROFILING=1` gates profiling scripts to avoid accidental usage in production.

## Native vs Python Pipeline

| Dataset profile | Recommended backend | Notes |
| --- | --- | --- |
| < 5k guides, exploratory runs | Pure Python | Minimal overhead; native setup not required. |
| ~20k guides, 4–6 replicates | Native RRA + optional native enrichment | Expect ~3–5× faster robust rank aggregation and deterministic enrichment without network calls. |
| ≥100k guides, ≥8 replicates | Native stack strongly recommended | Rust RRA delivers 8–12× speed-ups vs. pandas; C++ enrichment removes gseapy latency and scales linearly across libraries. |

### Quickstart (Placeholder)
[![Open in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/jameshyojaelee/CRISPR-studio/blob/main/notebooks/quickstart.ipynb)
See `docs/notebooks.md` for Colab/local notebook usage.

1. Create or activate a Python 3.11+ virtual environment (`python3.11 -m venv .venv && source .venv/bin/activate`).
2. Install the package and extras using `make install`.
3. Use the Typer CLI via `crispr-studio`:
   - `crispr-studio validate-data sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json`
   - `crispr-studio run-pipeline sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json --enrichr-libraries Reactome_2022`
   - `crispr-studio run-pipeline sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json --use-native-rra` (requires the Rust backend)
   - `crispr-studio run-pipeline sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json --use-native-enrichment --enrichr-libraries native_demo` (requires the C++ backend)
   - `crispr-studio run-pipeline sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json --skip-annotations` (offline mode; skips MyGene.info requests)
   - `crispr-studio list-artifacts`
   - `make build-report` to generate refreshed HTML/PDF reports under `artifacts/latest_report/`
   - `make benchmark` to pull in psutil and run synthetic pipeline benchmarks under `artifacts/benchmarks/`
   - `crispr-studio serve-api --host 0.0.0.0 --port 8000` to expose the FastAPI surface (requires `uvicorn`)
4. Review `docs/demo_runbook.md` for a walkthrough of the end-to-end analysis flow.
5. Metadata is loaded directly from the supplied JSON path; callers no longer need to pre-parse configs. MAGeCK/native backends fall back to Python implementations when unavailable and emit de-duplicated warnings for the UI/analytics payloads.

## API Usage

- Start the service: `python app_api.py` or `crispr-studio serve-api --host 0.0.0.0 --port 8000`.
- Example client: `python examples/api_client.py --host http://127.0.0.1:8000` (uses `sample_data/` paths and skips annotations). `make api-example` will spin up uvicorn briefly and run the script for you.
- cURL equivalent:
  ```bash
  HOST=http://127.0.0.1:8000
  curl -X POST \"$HOST/v1/analysis\" \\
    -H \"Content-Type: application/json\" \\
    -d '{\"counts_path\":\"sample_data/demo_counts.csv\",\"library_path\":\"sample_data/demo_library.csv\",\"metadata_path\":\"sample_data/demo_metadata.json\",\"use_mageck\":false,\"skip_annotations\":true}'
  ```

### Environment Configuration
- Create a `.env` file for secrets and overrides:
  - `OPENAI_API_KEY` (optional) to enable narrative LLM summaries.
  - `LOG_LEVEL` to adjust log verbosity (`DEBUG`, `INFO`, etc.).
  - `CRISPR_STUDIO__ARTIFACTS_DIR`, `CRISPR_STUDIO__UPLOADS_DIR`, `CRISPR_STUDIO__LOGS_DIR` to customise storage paths (pydantic nested setting syntax).
- Application logs are written to `logs/crispr_studio.log` via Loguru; rotate weekly with four-week retention.

#### Demo Dataset
- Sample inputs live in `sample_data/` (`demo_counts.csv`, `demo_library.csv`, `demo_metadata.json`) and adhere to the contract in `docs/data_contract.md`.
- Validate your own files (or the sample set) with `python scripts/validate_dataset.py sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json --export-samples artifacts/normalized_samples.json`.
- Regenerate or customize the synthetic dataset with `python scripts/generate_demo_dataset.py --output-dir sample_data --seed 42`.
- The demo models a dropout screen with two control and two treatment replicates, highlighting DNA repair genes that deplete under drug selection.

### Docker Usage
- Build the image locally:
  ```bash
  docker build -t crispr-studio .
  ```
- Run the Dash app and mount artifact directories:
  ```bash
  docker-compose up app
  ```
- Execute the benchmark worker:
  ```bash
  docker-compose run --rm worker
  ```

## Troubleshooting & FAQ

- **`pybind11` / compiler errors during native build** – ensure platform prerequisites are installed (see above). For macOS, run `xcode-select --install` and `brew install cmake ninja rustup`. On Windows, use an MSVC developer command prompt when executing build commands.
- **"Quality control checks failed" message** – the pipeline now stops early when any QC metric reaches CRITICAL severity. Inspect the CLI output (or `qc_metrics.json`) for guide detection, replicate correlation, or coverage issues, address them, and rerun the pipeline.
- **MAGeCK succeeds but native RRA import fails** – confirm `maturin develop --manifest-path rust/Cargo.toml` completed successfully and `pip show crispr_native_rust` lists the extension. Set `CRISPR_STUDIO_FORCE_PYTHON=1` to continue with the Python fallback while debugging.
- **Native enrichment returns empty results** – verify the requested libraries exist (`native_demo` ships with the repo) and that significant genes overlap the gene sets. Use `--use-native-enrichment --enrichr-libraries native_demo` for the bundled demo.
- **Disable native features temporarily** – set `CRISPR_STUDIO_FORCE_PYTHON=1` or remove `BUILD_NATIVE=1` from Docker builds.
- **Where do profiling artefacts go?** – scripts write to `artifacts/` (ignored by git). Clear the directory when sharing the project to keep the repository lean.
- **API requests return 401** – set `API_KEY` in `.env`/environment and include `X-API-Key` with each request. Without an API key the service allows unauthenticated access (prototype mode).
- **Sample report bundle missing in the UI** – run `make build-report` to regenerate `artifacts/sample_report/` before downloading from the Dash Reporting Studio tab.

## Documentation
- `docs/overview.md` – positioning memo and market context for the product build.
- `docs/demo_runbook.md` – step-by-step instructions for demoing the pipeline.
- `docs/data_contract.md` – structured expectations for counts, library, and metadata files.
- `docs/user_guide.md` / `docs/developer_guide.md` – usage tips and architecture notes (draft).
- `docs/troubleshooting.md` – quick fixes for common warnings (native fallbacks, annotation batches, cache issues).
- `docs/runbooks/operations.md` – operational checklist for the JobManager, analytics logs, and OpenAPI exports.
- `docs/security_privacy.md` / `docs/roadmap.md` – compliance checklist and upcoming milestones.
