# Performance Guide

Benchmarks run on synthetic datasets bundled with `scripts/benchmark_pipeline.py`. The figures below are indicative for a modern laptop (8 vCPU, 16 GB RAM) using Python-only backends; native paths typically deliver 3–8× faster runtimes.

| Dataset | Guides | Replicates | Python runtime (mean) | Native runtime (mean) | Notes |
| --- | --- | --- | --- | --- | --- |
| small | 1k | 4 | < 20 s | < 10 s | Good for smoke tests and CI |
| medium | 20k | 6 | ~90 s | ~35 s | Approaches demo scale |
| large | 100k | 8 | 5–7 min | 2–3 min | Use native RRA/enrichment and warmed caches |

## Running the benchmark suite

```bash
pip install .[benchmark]
python scripts/benchmark_pipeline.py --dataset-size medium --repeat 2 --use-native-rra --jsonl artifacts/benchmarks/runs.jsonl --plot
```

- `--jsonl` appends per-run metrics (runtime, CPU%, RSS) for downstream aggregation.
- `--plot` writes `runtime_vs_size.html` alongside `metrics.json`/`summary.md`.
- `--use-native-rra/--no-use-native-rra` toggles Rust backend benchmarking.

Nightly CI (scheduled) runs the small dataset and uploads `artifacts/benchmarks/*.jsonl` as an artifact for quick regressions. For local experiments, keep datasets under `benchmarks/data/<size>/` to avoid re-generating fixtures on every run.

## Reliability tips

- **Annotation cache prewarm:** run once with network access so `.cache/gene_cache.json` is populated; subsequent offline runs avoid MyGene.info entirely.
- **MyGene batch sizing:** set `MYGENE_BATCH_SIZE=250` (max 500) on flaky networks to reduce request failures; warnings stay deduplicated in the UI.
- **Skip annotations when needed:** pass `--skip-annotations` (or uncheck annotations in the Dash UI) for air-gapped demos; enrichment is still available for bundled libraries.
- **Native backends:** enable `--use-native-rra` and `--use-native-enrichment` for >20k guides to keep runtimes predictable; the pipeline falls back automatically when extensions are missing.
