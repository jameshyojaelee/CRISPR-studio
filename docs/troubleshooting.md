# Troubleshooting Guide

Common warning codes and how to resolve them. Warnings are de-duplicated in the UI/analytics payloads, so you only see the first instance of each issue.

## Native Backends

- **`native_rra_unavailable` / `native_rra_failed`** – The Rust RRA module is missing or crashed.
  - Install the native extra (`pip install .[native]`) and rebuild wheels, or disable via CLI/Dash toggle/`CRISPR_STUDIO_FORCE_PYTHON=1`.
  - Rerun the pipeline; it will fall back to the Python RRA path automatically.
- **`native_enrichment_backend_missing` / `native_enrichment_library_missing`** – C++ enrichment backend or requested library not found.
  - Install the native extra and run with `--use-native-enrichment --enrichr-libraries <lib>`.
  - If you hit this in production, switch back to the Enrichr Python path until the build is repaired.

## Annotations

- **`annotations_warning`** with text such as `batch 2 (HTTP 503, 200 genes skipped)` – MyGene.info batch failed.
  - Retry after a short pause; only missing batches are re-fetched thanks to the incremental cache.
  - Lower `MYGENE_BATCH_SIZE` (<=500) for flaky networks, or run with `--skip-annotations`/Dash toggle in air-gapped environments.
- **Cache corruption** – The cache is renamed to `gene_cache.json.bak_<timestamp>` when parsing fails.
  - Inspect the `.bak` file, then delete it once the regenerated cache looks sane.

## Inputs & QC

- **`mageck_unavailable`** or MAGeCK CLI not found – install MAGeCK or run with `--use-mageck false` to stay on the RRA path.
- **QC failures** – The CLI aborts when any metric hits CRITICAL severity.
  - Inspect `qc_metrics.json` for the failing metric (e.g., low replicate correlation) and rerun once fixed.
  - For demos, ensure you are using the bundled metadata and rerun after addressing the warning; QC metrics remain attached to the analysis result even when you proceed.
