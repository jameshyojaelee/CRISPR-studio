# Native Extension Architecture Plan

This brief outlines how CRISPR-studio will introduce native (C++/Rust) acceleration while keeping Python as the orchestration layer. The focus is on the highest-impact hotspots surfaced during code review of the existing pipeline (`README.md`, `docs/developer_guide.md`, and `src/crispr_screen_expert` package).

## Candidate Hotspots

| Hotspot | Current Python Modules | Workload Profile (typical datasets) | Bottleneck Symptoms | Target Speedup | Native Scope |
| --- | --- | --- | --- | --- | --- |
| Robust Rank Aggregation (RRA) fallback | `rra.py`, `normalization.py`, `results.py` | Genome-wide dropout screens: 100k–200k guides, 3–6 replicates → 18–36 columns; ~18k genes after aggregation | Python loop per gene and heavy sorting cause >6–8 min runtime on 120k-guide datasets; memory pressure from pandas copies | 8–12× faster RRA, <45 s for 120k guides | Implement full RRA in Rust with streaming statistics and native ranking |
| Permutation/Resampling for enrichment & QC (planned) | `enrichment.py`, `qc.py` | Future large permutations: 10k–50k iterations; gene set sizes 50–500 | Python-level loops / gseapy single-threaded flow will not scale; CPU pegged, poor multi-core usage | 5–10× faster permutations with multi-threading; linear scaling with CPU cores | Implement native hypergeometric & permutation engine in C++ backed by Eigen/OpenMP |
| QC aggregation & correlation matrices | `qc.py`, `visualization.py` | 200k guides × 8 replicates; repeated log/median/correlation per run | NumPy operations are vectorised but allocate intermediate DataFrames; repeated conversions for Dash payloads | 3× faster QC summarisation; reduce memory copies | Optional native kernels in Rust using `ndarray`, reused for Dash backends |
| Synthetic benchmark dataset generation | `scripts/generate_demo_dataset.py`, upcoming benchmarking harness | 100k–250k guides synthetic counts, repeated generation for CI and benchmarking | Pure Python random sampling slow for >100k guides; cannot easily emit binary caches | 5× faster dataset synthesis | Rust binary/tool producing Parquet/CSV for reuse |

> **Data sizing references:** MAGeCK-style genome-wide libraries typically contain ~110k guides (4–6 per gene) with count matrices of 4–12 replicates. Enrichment runs routinely evaluate 5–30 libraries (Reactome/GO) with 5k–20k gene sets each.

## Language & Tooling Choices

### Robust Rank Aggregation (RRA) — **Rust**
- **Why Rust:** Safe concurrency, rich iterator ergonomics for rank aggregation, strong ecosystem (`ndarray`, `statrs`) and `pyo3` bindings. Memory safety is critical when handling 100k-element vectors; Rust eliminates data races during Rayon-powered parallel loops.
- **Alternative (C++):** Requires manual memory management and pybind11. While feasible, RRA relies heavily on iterators and custom reductions better expressed in Rust.
- **Chosen tooling:** `pyo3` + `maturin` producing a module `crispr_native.rra`. Optional Rayon feature for parallel statistics.

### Enrichment permutations & QC kernels — **C++**
- **Why C++:** Mature linear algebra stacks (Eigen, BLAS) and direct OpenMP integration for parallel permutation loops. Native interop with existing scientific code makes it easier to port established statistical routines.
- **Alternative (Rust):** Rayon & `nalgebra` are improving but still lack some advanced probability libraries. We can revisit once prototypes stabilise.
- **Chosen tooling:** `pybind11` module `crispr_native_cpp` exposing hypergeometric calculators, permutation harness, and QC summaries. CMake controls optional SIMD (`-march=native`) and OpenMP.

### Synthetic data generation — **Rust**
- Fast binary (CLI) built with `clap` to emit CSV/Parquet. Integrates with Python via subprocess or direct FFI if needed.

## Binding Strategy

- **Module layout:** `src/crispr_screen_expert/native/` will contain thin Python facades. Rust crate exports via `pyo3::prelude::*` into a wheel named `crispr_native_rust`. C++ shared library built as `crispr_native_cpp` using pybind11.
- **FFI patterns:**
  - Accept NumPy arrays (`PyReadonlyArray1/2`) for numerical inputs; convert to `ndarray::ArrayView` (Rust) or `Eigen::Map` (C++) without copying when shapes align.
  - Return `PyDict` / `PyList` or `polars`/`pandas`-ready buffers; prefer arrow-style zero-copy where feasible.
  - Raise native errors mapped to Python exceptions via `PyErr::new::<PyValueError, _>(msg)` (Rust) or `py::value_error` (pybind11).
- **Memory ownership:** Python owns incoming buffers; native code reads via borrowed views. Allocate output arrays once and hand control back to Python (`PyArray::from_owned_vec` or `py::array_t`).
- **Naming convention:** Python entrypoints under `crispr_screen_expert.native.*` mirror existing module names (e.g., `run_rra_native`). Keep snake_case API.

## Build & Packaging Considerations

- **Project layout:** Add top-level `rust/` (library crate) and `cpp/` (CMake project). Build artefacts land in `target/` and `build/`, ignored by git.
- **`pyproject.toml`:**
  - Add `[project.optional-dependencies.native]` including `maturin>=1.4`, `setuptools-rust`, `pybind11`, `scikit-build-core`, `cmake`, `ninja`.
  - Extend `[build-system]` to support PEP 517 hooks when native extras selected (e.g., `requires = ["setuptools>=67", "wheel", "maturin>=1.4", "scikit-build-core"]`).
  - Define entry points for maturin (`[tool.maturin]` with `bindings = "pyo3"`) and scikit-build settings (`[tool.scikit-build]`).
- **Wheel builds:** Support manylinux, macOS universal2, Windows. Use `auditwheel` / `delocate` in CI packaging jobs.
- **Toolchain prerequisites:** Document requirement for:
  - Rust toolchain (`rustup`, nightly optional for SIMD).
  - C++17 compiler (gcc ≥11, clang ≥14, MSVC 2019), CMake ≥3.22, Ninja optional.
  - OpenMP availability; provide toggle if missing (`CRISPR_NATIVE_OPENMP=0`).

## Testing & CI Strategy

- **Unit parity tests:** Mirror existing Python tests with fixtures that run native + Python paths, checking `np.allclose` within tolerance (`1e-8` numeric).
- **Property-based tests:** Use Hypothesis for random matrices to stress RRA parity and permutation correctness.
- **Benchmark tests:** Integrate `pytest-benchmark` or custom harness comparing runtime/memory. Fail CI if regression >20%.
- **CI matrix:** GitHub Actions covering:
  - Linux: gcc (native off/on), clang.
  - macOS: universal2 builds.
  - Windows: MSVC (if feasible).
  - Run pytest twice (`--native off/on`) using feature flag.
- **Linting:** `cargo fmt`, `cargo clippy`, `cppcheck`/`clang-tidy` (optional) executed in CI.

## Rollback & Feature Flags

- **Python toggles:** Extend `PipelineSettings` with `use_native_rra`, `use_native_enrichment`, `use_native_qc`. Default `False`.
- **Environment variables:** `CRISPR_STUDIO_USE_NATIVE_RRA`, `CRISPR_STUDIO_USE_NATIVE_ENRICHMENT`, `CRISPR_STUDIO_FORCE_PYTHON=1`. Respect these in CLI/Dash (also surface in docs).
- **Runtime detection:** On import failure fall back to Python implementation with `logger.warning`. Provide detailed `ImportError` guidance (compiler version, wheel availability).
- **Monitoring:** Emit analytics events (`log_event`) capturing runtime, selected backend, error counts. Optionally write structured logs/JSON metrics for benchmark scripts.
- **Rollback:** Keep pure-Python functions untouched; wrappers call native path only when flag enabled **and** native module successfully imports. Rolling back requires toggling flag or uninstalling native extras.

## Next Steps

1. Scaffold Rust and C++ projects with minimal bindings that expose version introspection (`get_backend_info()`).
2. Wire Python facades (`native/rra.py`, etc.) with feature flags and logging.
3. Expand CI to build optional wheels and run parity tests.
4. Iterate on profiling to prioritise further native offloads (e.g., additional QC metrics, dataset generation).

