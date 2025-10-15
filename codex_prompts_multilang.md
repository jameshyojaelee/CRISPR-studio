# Codex Prompts for Multilanguage Enhancements

Use these prompts sequentially after the primary Python implementation is feature-complete. Each prompt builds on the previous ones to introduce high-performance native modules (C++ or Rust) while preserving all existing Python contracts (CLI, Dash UI, reporting, tests). Never delete or regress current functionality; add wrapper layers so Python remains the orchestrator. Document all changes thoroughly.

## Prompt M01 – Multilanguage Architecture Master Plan

1. Read `README.md`, `codex_prompts.md`, `docs/developer_guide.md`, and the entire `src/crispr_screen_expert` package to understand the current pipeline, CLI, tests, and UI dependencies.
2. Produce a detailed architecture brief (Markdown) covering:
   - **Candidate Hotspots**: Identify specific modules where Python becomes a bottleneck (e.g., robust rank aggregation, enrichment permutations, QC aggregation). Include estimated data sizes and desired speedups.
   - **Language/Tooling Choices**: Compare C++ vs. Rust for each hotspot (ecosystem maturity, existing libraries like Eigen/BLAS vs. ndarray/serde, threading models, FFI maturity). Justify the chosen language per component.
   - **Binding Strategy**: Outline how to expose native code to Python (pybind11, cffi, Rust `pyo3`/maturin). Detail naming conventions, memory ownership, and error propagation back to Python exceptions.
   - **Build & Packaging Considerations**: Describe how to integrate CMake/Cargo with `pyproject.toml`, wheel building, optional extras, and platform-specific handling (Linux/macOS/Windows). Mention compiler/toolchain prerequisites.
   - **Testing & CI Strategy**: Plan unit/integration tests comparing native vs. Python outputs, profiling strategy, and CI matrix updates to ensure reproducible builds.
   - **Rollback/Feature Flags**: Define environment variables or config flags to toggle native features on/off safely. Include monitoring metrics for runtime, memory, and error frequency to decide when to fallback.
3. Save the architecture brief as `docs/native_architecture_plan.md`.

## Prompt M02 – Repository Scaffolding for Native Modules

1. Create language-specific directories (`cpp/` and/or `rust/`) housing native source code.
2. For C++:
   - Add `cpp/CMakeLists.txt` configuring a shared library `crispr_native` with pybind11 (or nanobind) integration.
   - Configure compiler flags for optimization (`-O3`, `-march=native` optional), thread support (OpenMP), and sanitizers toggled via environment variables.
3. For Rust:
   - Add `rust/Cargo.toml` with library crate configuration using `pyo3`/`maturin`.
   - Set up feature flags for optional SIMD, Rayon parallelism, and expose a FFI boundary for Python.
4. Update `.gitignore` to exclude build artefacts (`cpp/build/`, `rust/target/`, generated `.so/.dylib/.pyd` files).
5. Modify `pyproject.toml` to:
   - Introduce a `[project.optional-dependencies.native]` section listing build helpers (`pybind11`, `maturin`, `setuptools-rust`, etc.).
   - Add entry points or build hooks if required (e.g., `build-system` enhancements for scikit-build-core or maturin).
6. Update `README.md` with prerequisites (compilers, CMake version, Rust toolchain) and quick-start commands for building native extensions.

## Prompt M03 – Native Robust Rank Aggregation Prototype

1. Implement the robust rank aggregation algorithm in the chosen native language:
   - Operate on arrays of log2 fold-changes, gene identifiers, weights, and optional p-values.
   - Ensure deterministic ordering and support for missing values matching the Python RRA behaviour.
2. Wrap the native function with Python bindings exposing `run_rra_native(log2fc: np.ndarray, gene_ids: np.ndarray, guide_weights: np.ndarray, p_values: Optional[np.ndarray]) -> Dict/Struct`.
3. Add a new module `src/crispr_screen_expert/native/rra.py` that:
   - Imports the native extension if available, else raises a clear `ImportError`.
   - Provides a Pythonic facade returning a pandas DataFrame identical to the existing `run_rra`.
4. Extend `PipelineSettings` with a flag `use_native_rra: bool` defaulting to `False`. When enabled and native module present, pipeline uses the native path; otherwise falls back to Python implementation with a warning.
5. Write unit tests verifying:
   - Native vs. Python outputs match within tolerance for multiple datasets (small, medium, edge cases).
   - Feature flag toggles correctly and raises informative errors if native module missing.
6. Update documentation (dev guide + README) explaining how to enable the native RRA path.

## Prompt M04 – Comprehensive Benchmark & Profiling Harness

1. Enhance `scripts/benchmark_pipeline.py` to accept CLI options:
   - `--use-native-rra/--no-use-native-rra`
   - `--dataset-size` (e.g., small/medium/large synthetic datasets)
   - `--repeat` to average over multiple runs.
2. Generate synthetic datasets (counts/library/metadata) scaled to realistic sizes (e.g., 100k guides, 200k guides) for benchmarking. Store under `benchmarks/data/`.
3. Collect metrics:
   - Runtime via `time.perf_counter()`
   - Memory via `psutil.Process().memory_info()`
   - Optional CPU utilization via `psutil`.
4. Validate result parity between native and Python pipelines (numerical tolerances).
5. Persist benchmark reports (JSON + markdown summary) under `artifacts/benchmarks/<timestamp>/`.
6. Update `docs/developer_guide.md` with instructions for running benchmarks, interpreting outputs, and thresholds for enabling native paths.

## Prompt M05 – Native Enrichment Accelerator (Optional Stretch)

1. Profile existing enrichment modules (Enrichr API calls, gseapy prerank). Identify routines suitable for native acceleration (e.g., permutation tests, hypergeometric loops).
2. Implement a native enrichment engine supporting batch evaluation of gene sets with:
   - Hypergeometric probability calculation with high precision.
   - Optional GPU/SIMD acceleration considerations.
3. Expose synchronous and asynchronous APIs; ensure fallback to Python when native module or dependencies missing.
4. Extend pipeline to use native enrichment when available (`PipelineSettings.use_native_enrichment`).
5. Document mixed-mode operation (some libraries native, others Python) and testing strategy.

## Prompt M06 – Memory & Performance Profiling Toolkit

1. Add profiling scripts to `scripts/`:
   - `profile_python.sh` leveraging `line_profiler` / `py-spy`.
   - `profile_native.sh` orchestrating `perf`, `valgrind --tool=callgrind`, and generating flamegraphs (document prerequisites).
2. Update `docs/developer_guide.md` with step-by-step profiling instructions, sample commands, interpretation tips, and thresholds for raising performance issues.
3. Ensure all profiling tools respect environment variables (e.g., `ENABLE_PROFILING=1`) and avoid running in production by default.

## Prompt M07 – CI, Packaging, and Docker Enhancements

1. Modify `.github/workflows/ci.yml`:
   - Add jobs building native extensions on Ubuntu (gcc/clang) and macOS (clang). Optionally include Windows (MSVC) if feasible.
   - Cache CMake/Cargo artefacts to speed up builds.
   - Run pytest twice (native flag on/off) on at least one platform.
2. Extend Dockerfile:
   - Install compilers (`build-essential`, `cmake`, or Rust toolchain) in builder stage.
   - Provide a build arg to toggle native extension build at image build time.
3. Update docker-compose to illustrate running the app with native modules enabled.
4. Document cross-platform build instructions, including environment variables controlling toggles (e.g., `CRISPR_STUDIO_USE_NATIVE_RRA=1`).

## Prompt M08 – Documentation Refresh & Troubleshooting

1. Update `README.md`, `docs/user_guide.md`, and `docs/developer_guide.md`:
   - Step-by-step native build instructions (Linux/macOS/Windows).
   - Troubleshooting section for compiler errors, missing toolchains, and fallback behaviour.
   - Comparison table showing when to choose native vs. pure Python (dataset size thresholds, runtime benefits).
2. Add FAQs for common issues (e.g., “MAGeCK works but native RRA fails to build”).
3. Include notes on environment variables (`CRISPR_STUDIO_USE_NATIVE_RRA`, `CRISPR_STUDIO_FORCE_PYTHON`, etc.).

## Prompt M09 – Licensing, Compliance, and Monetisation Audit

1. Review licenses of all native dependencies (Eigen, BLAS, OpenMP, Rust crates). Ensure compatibility with MIT license and note any attribution requirements.
2. Update `docs/security_privacy.md`:
   - Mention native module distribution considerations (prebuilt wheels, reproducible builds).
   - Describe scanning procedures (e.g., `cargo audit`, `pip-licenses`).
3. Assess the impact of native modules on monetisation tiers (e.g., native performance as premium feature). Update `docs/go_to_market.md` if offering native mode as part of paid tier.
4. Provide guidance on redistributing binaries (signed wheels, hash verification).
