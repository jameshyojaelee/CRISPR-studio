# Codex Prompts for Multilanguage Enhancements

Use these prompts sequentially once the Python pipeline is stable. Each assumes prior steps are completed. Keep existing Python artefacts intact; add new languages through additive modules and wrappers.

## Prompt M01 – Multilanguage Architecture Plan

Read `README.md`, `codex_prompts.md`, and the `src/crispr_screen_expert` package. Produce a design brief describing which components benefit most from C++ or Rust acceleration (e.g., scoring algorithms, enrichment permutations), how to expose them through Python bindings (pybind11, cffi), and how to preserve the current CLI/UI contracts. Include build tooling considerations (CMake, maturin), testing strategy, and rollback plan. Output sections: Candidate Hotspots, Language/Tooling Choices, Binding Strategy, Testing & CI, Migration Risks.

## Prompt M02 – Repository Prep for Native Modules

Create a `cpp/` (or `rust/`) directory with scaffolding for a `crispr_native` library. Add build scripts (CMakeLists.txt or Cargo.toml), declare dependencies (Eigen, OpenMP, etc.), and update `.gitignore` for build artefacts. Modify `pyproject.toml` to include optional extras (e.g., `native`) and document build prerequisites in `README.md`.

## Prompt M03 – Implement Native Scoring Prototype

Port the robust rank aggregation routine to C++ (or Rust) for performance benchmarking. Expose a function `run_rra_native(log2fc, gene_ids, guide_weights)` returning a structure compatible with the existing pandas DataFrame. Integrate bindings into Python (e.g., `src/crispr_screen_expert/native/rra.py`) and add a feature flag in `PipelineSettings` to toggle native vs. pure Python execution.

## Prompt M04 – Benchmark & Profile Harness

Extend `scripts/benchmark_pipeline.py` to compare Python vs. native implementations on synthetic large datasets. Capture runtime, memory usage (psutil), and output parity (assert close). Store results under `artifacts/benchmarks/` and update docs with guidance on choosing the native path.

## Prompt M05 – Enrichment Accelerator (Optional)

Implement a native module for permutation-heavy enrichment (e.g., GSEA). Provide both synchronous and batch APIs, with fallbacks to Python when native library unavailable.

## Prompt M06 – Memory & Performance Profiling

Add profilers (line_profiler, perf, valgrind callgrind instructions) to `docs/developer_guide.md`. Include scripts for generating flamegraphs and interpreting hotspots.

## Prompt M07 – CI & Packaging Updates

Modify `.github/workflows/ci.yml` to build/test the native module on Linux (and optionally macOS), caching compiler artefacts. Update Dockerfile and docker-compose to include necessary compilers/libraries. Document how to enable the `native` extra during installation.

## Prompt M08 – Documentation Refresh

Update `README.md`, `docs/user_guide.md`, and `docs/developer_guide.md` with instructions for building native extensions, enabling performance mode, troubleshooting compiler errors, and switching between pure Python and native paths. Add a note about environment variables controlling the fallback.

## Prompt M09 – Monetisation & Licensing Considerations

Review third-party library licenses (Eigen, OpenMP, Rust crates). Document compatibility with MIT licensing and update `docs/security_privacy.md` if the native path introduces new distribution concerns.
