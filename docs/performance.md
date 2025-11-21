# Performance Benchmarks

This project ships a synthetic benchmark harness to sanity‑check runtime and memory across dataset sizes. Numbers are indicative for laptop CPUs; expect faster results on server hardware.

## Expected Runtimes (Python pipeline)
- **Small (1k guides, 4 reps)**: ~10–15s, RSS ~300–400 MB.
- **Medium (20k guides, 6 reps)**: ~75–110s, RSS ~1.2–1.6 GB.
- **Large (100k guides, 8 reps)**: ~5–7 minutes, RSS ~3–4 GB.
- Native RRA typically reduces runtime by 2–5× on medium/large datasets; enrichment acceleration depends on library size.

## Running Benchmarks
- Install extras: `pip install .[benchmark]`.
- Quick check (single dataset):  
  `python scripts/benchmark_pipeline.py --dataset-size small --repeat 2 --jsonl --plot`
- All sizes with a runtime-vs-size plot and JSONL:  
  `python scripts/benchmark_pipeline.py --all-sizes --repeat 2 --jsonl --plot`
- Include native backend: add `--use-native-rra` (requires native build).
- Override JSONL destination: `--jsonl-path /tmp/runs.jsonl`.

Outputs land under `artifacts/benchmarks/<timestamp>/<size>/` with:
- `metrics.json` and `summary.md` (aggregated stats).
- `runs.jsonl` (per-run metrics when `--jsonl` is set).
- `runtime_vs_size.html` (line chart; PNG if `kaleido` is available).

## CI & Artifacts
- Benchmarks are optional and scoped to scheduled workflows; JSONL/plots can be uploaded as artifacts without impacting default CI time.
- Keep default repeat counts low (`--repeat 1` or `2`) in automation; larger repeats are better for local profiling.

## Network & Caching Tips
- Warm the MyGene annotation cache before large runs to avoid intermittent HTTP 5xx: run `crispr-studio run-pipeline ... --skip-annotations false` once on a small dataset to hydrate `.cache/gene_cache.json`.
- For flaky networks, set `MYGENE_BATCH_SIZE=250` (clamped ≤500) to reduce request size and increase cache hits.
- If annotations remain unstable, use `--skip-annotations` or `PipelineSettings(cache_annotations=False)`; runtime benchmarks will still execute and log a warning.

## Native Build Notes
- Export `CRISPR_NATIVE_USE_NATIVE_ARCH=ON` to optimise native builds for the host CPU.
- Set `CRISPR_NATIVE_ENABLE_OPENMP=0` when running in constrained environments without OpenMP support.
- If native imports fail, benchmarking falls back to the Python implementation and logs a warning in the summary.
