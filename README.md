# CRISPR-studio

CRISPR-studio is a next-generation analysis and visualization toolkit that turns pooled CRISPR screen data into interactive biological insights. The planning brief in `overview.md` drives the scope: automated QC, MAGeCK-compatible hit calling, pathway enrichment, curated gene context, and narrative-ready reporting for demos and admissions showcases.

![CI](https://img.shields.io/badge/ci-pending-lightgrey?label=GitHub%20Actions)

> **Status:** Repository scaffolding only. Use the prompts in `codex_prompts.md` to continue building the system module-by-module.

## Getting Started

### Prerequisites
- Python 3.11 (recommended to manage via `pyenv` or system package manager)
- A virtual environment tool such as `python3 -m venv` or `conda`
- (Optional) Native toolchains for performance modules:
  - GCC ≥ 11 or Clang ≥ 14 (or MSVC 2019 on Windows)
  - CMake ≥ 3.22 and Ninja ≥ 1.11
  - Rust toolchain (`rustup` recommended)

### Installation
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install .
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
1. Create or activate a Python 3.11 virtual environment.
2. Install the package and extras using `make install`.
3. Use the Typer CLI via `crispr-studio`:
   - `crispr-studio validate-data sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json`
   - `crispr-studio run-pipeline sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json --enrichr-libraries Reactome_2022`
   - `crispr-studio run-pipeline sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json --use-native-rra` (requires the Rust backend)
   - `crispr-studio run-pipeline sample_data/demo_counts.csv sample_data/demo_library.csv sample_data/demo_metadata.json --use-native-enrichment --enrichr-libraries native_demo` (requires the C++ backend)
   - `crispr-studio list-artifacts`
4. Follow the build prompts in `codex_prompts.md` to generate data contracts, pipeline components, and the Dash UI.

### Environment Configuration
- Create a `.env` file for secrets and overrides:
  - `OPENAI_API_KEY` (optional) to enable narrative LLM summaries.
  - `LOG_LEVEL` to adjust log verbosity (`DEBUG`, `INFO`, etc.).
  - `CRISPR_STUDIO__ARTIFACTS_DIR`, `CRISPR_STUDIO__UPLOADS_DIR`, `CRISPR_STUDIO__LOGS_DIR` to customise storage paths (pydantic nested setting syntax).
- Application logs are written to `logs/crispr_studio.log` via Loguru; rotate weekly with four-week retention.

#### Demo Dataset
- Sample inputs live in `sample_data/` (`demo_counts.csv`, `demo_library.csv`, `demo_metadata.json`) and adhere to the contract in `docs/data_contract.md`.
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
- **MAGeCK succeeds but native RRA import fails** – confirm `maturin develop --manifest-path rust/Cargo.toml` completed successfully and `pip show crispr_native_rust` lists the extension. Set `CRISPR_STUDIO_FORCE_PYTHON=1` to continue with the Python fallback while debugging.
- **Native enrichment returns empty results** – verify the requested libraries exist (`native_demo` ships with the repo) and that significant genes overlap the gene sets. Use `--use-native-enrichment --enrichr-libraries native_demo` for the bundled demo.
- **Disable native features temporarily** – set `CRISPR_STUDIO_FORCE_PYTHON=1` or remove `BUILD_NATIVE=1` from Docker builds.
- **Where do profiling artefacts go?** – scripts write to `artifacts/profiles/<python|native>/<timestamp>/`. Remove large artefacts after analysis to keep worktrees lean.

## Documentation Roadmap

| Document | Purpose | Status |
| --- | --- | --- |
| `docs/data_contract.md` | Define input expectations for counts, library, metadata. | Planned |
| `docs/user_guide.md` | Walkthrough for CLI and Dash usage. | Planned |
| `docs/developer_guide.md` | Architecture and contribution guidance. | Planned |
| `docs/roadmap.md` | Milestones and success metrics. | Planned |
| `docs/security_privacy.md` | Data handling checklist. | Planned |

Refer to `overview.md` for the full product vision, demo script, and go-to-market context guiding subsequent development prompts.
