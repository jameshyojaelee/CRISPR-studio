#!/usr/bin/env python3
"""Benchmark CRISPR-studio pipeline across synthetic datasets."""

from __future__ import annotations

import argparse
import gc
import json
import math
import statistics
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import plotly.express as px

try:
    import psutil
except ImportError as exc:  # pragma: no cover - guarded import
    raise SystemExit(
        "psutil is required for benchmarking. Install with `pip install .[benchmark]` or "
        "`pip install crispr_screen_expert[benchmark]`."
    ) from exc

from crispr_screen_expert.models import ExperimentConfig, load_experiment_config
from crispr_screen_expert.native import rra as native_rra
from crispr_screen_expert.pipeline import DataPaths, PipelineSettings, run_analysis

BENCHMARK_DATA_DIR = Path("benchmarks/data")
ARTIFACT_ROOT = Path("artifacts/benchmarks")
RUN_OUTPUT_DIR = ARTIFACT_ROOT / "runs"


@dataclass(frozen=True)
class DatasetSpec:
    name: str
    guides: int
    guides_per_gene: int
    replicates: int
    seed: int


DATASET_SPECS: Dict[str, DatasetSpec] = {
    "small": DatasetSpec(name="small", guides=1_000, guides_per_gene=4, replicates=4, seed=42),
    "medium": DatasetSpec(name="medium", guides=20_000, guides_per_gene=4, replicates=6, seed=4242),
    "large": DatasetSpec(name="large", guides=100_000, guides_per_gene=4, replicates=8, seed=424_242),
}


def append_jsonl_record(
    path: Optional[Path],
    backend: str,
    run_index: int,
    spec: DatasetSpec,
    metrics: Dict[str, float],
) -> None:
    """Append a JSONL record for a single run."""
    if path is None:
        return
    record = {
        "backend": backend,
        "run_index": run_index,
        "dataset": spec.name,
        "guides": spec.guides,
        "replicates": spec.replicates,
        **metrics,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark CRISPR-studio pipeline on synthetic datasets.")
    parser.add_argument(
        "--dataset-size",
        choices=DATASET_SPECS.keys(),
        default="small",
        help="Synthetic dataset to benchmark (default: small).",
    )
    parser.add_argument(
        "--all-sizes",
        action="store_true",
        help="Benchmark all dataset sizes (small, medium, large) in one run.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=3,
        help="Number of repetitions per backend to average metrics (default: 3).",
    )
    parser.add_argument(
        "--jsonl",
        action="store_true",
        help="Write per-run metrics to runs.jsonl in the benchmark output directory.",
    )
    parser.add_argument(
        "--jsonl-path",
        type=Path,
        default=None,
        help="Override the JSONL output path (defaults to artifacts/benchmarks/<timestamp>/runs.jsonl).",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Write a runtime_vs_size.html plot alongside the summary JSON.",
    )
    parser.add_argument(
        "--use-native-rra",
        dest="use_native_rra",
        action="store_true",
        help="Benchmark the native RRA backend in addition to the Python baseline.",
    )
    parser.add_argument(
        "--no-use-native-rra",
        dest="use_native_rra",
        action="store_false",
        help="Skip native benchmarking even if the backend is available.",
    )
    parser.set_defaults(use_native_rra=None)
    return parser.parse_args()


def ensure_dataset(size: str) -> Tuple[DatasetSpec, DataPaths, ExperimentConfig]:
    spec = DATASET_SPECS[size]
    dataset_dir = BENCHMARK_DATA_DIR / size
    counts_path = dataset_dir / "counts.csv"
    library_path = dataset_dir / "library.csv"
    metadata_path = dataset_dir / "metadata.json"

    if not (counts_path.exists() and library_path.exists() and metadata_path.exists()):
        dataset_dir.mkdir(parents=True, exist_ok=True)
        generate_dataset(spec, dataset_dir, counts_path, library_path, metadata_path)

    config = load_experiment_config(metadata_path)
    return spec, DataPaths(counts=counts_path, library=library_path, metadata=metadata_path), config


def generate_dataset(
    spec: DatasetSpec,
    output_dir: Path,
    counts_path: Path,
    library_path: Path,
    metadata_path: Path,
) -> None:
    rng = np.random.default_rng(spec.seed)

    gene_count = max(spec.guides // spec.guides_per_gene, 1)
    gene_symbols = [f"GENE_{idx:05d}" for idx in range(gene_count)]

    guide_ids: List[str] = []
    guide_genes: List[str] = []
    for gene in gene_symbols:
        for guide_index in range(spec.guides_per_gene):
            if len(guide_ids) >= spec.guides:
                break
            guide_ids.append(f"{gene}_G{guide_index + 1:02d}")
            guide_genes.append(gene)
        if len(guide_ids) >= spec.guides:
            break

    control_reps = spec.replicates // 2
    treatment_reps = spec.replicates - control_reps
    control_cols = [f"CTRL_{idx + 1}" for idx in range(control_reps)]
    treatment_cols = [f"TREAT_{idx + 1}" for idx in range(treatment_reps)]
    columns = control_cols + treatment_cols

    control_counts = rng.poisson(lam=20_000, size=(spec.guides, control_reps)) + 50
    treatment_counts = rng.poisson(lam=18_500, size=(spec.guides, treatment_reps)) + 50

    hit_fraction = max(int(gene_count * 0.05), 1)
    hit_genes = set(rng.choice(gene_symbols, size=hit_fraction, replace=False))
    hit_mask = np.array([gene in hit_genes for gene in guide_genes])

    if hit_mask.any():
        treatment_counts[hit_mask, :] = rng.poisson(lam=4_000, size=(hit_mask.sum(), treatment_reps)) + 25

    counts_matrix = np.concatenate([control_counts, treatment_counts], axis=1)
    counts_df = pd.DataFrame(counts_matrix, columns=columns)
    counts_df.insert(0, "guide_id", guide_ids)
    counts_df.to_csv(counts_path, index=False)

    library_df = pd.DataFrame(
        {
            "guide_id": guide_ids,
            "gene_symbol": guide_genes,
            "weight": np.ones(len(guide_ids), dtype=float),
        }
    )
    library_df.to_csv(library_path, index=False)

    samples: List[Dict[str, object]] = []
    for idx, column in enumerate(control_cols, start=1):
        samples.append(
            {
                "sample_id": f"CTRL_{idx}",
                "condition": "control",
                "replicate": str(idx),
                "role": "control",
                "file_column": column,
            }
        )
    for idx, column in enumerate(treatment_cols, start=1):
        samples.append(
            {
                "sample_id": f"TREAT_{idx}",
                "condition": "treatment",
                "replicate": str(idx),
                "role": "treatment",
                "file_column": column,
            }
        )

    metadata = {
        "experiment_name": f"benchmark_{spec.name}",
        "screen_type": "dropout",
        "samples": samples,
        "analysis": {
            "scoring_method": "rra",
            "fdr_threshold": 0.1,
            "min_count_threshold": 10,
        },
    }
    metadata_path.write_text(json.dumps(metadata, indent=2))

    info = {
        "generated_at": datetime.utcnow().isoformat(),
        "seed": spec.seed,
        "guides": spec.guides,
        "genes": gene_count,
        "replicates": spec.replicates,
        "hit_fraction": hit_fraction / gene_count,
    }
    (output_dir / "dataset_info.json").write_text(json.dumps(info, indent=2))


def run_single_benchmark(
    config: ExperimentConfig,
    data_paths: DataPaths,
    use_native_rra: bool,
    process: psutil.Process,
) -> Tuple[Dict[str, float], object]:
    gc.collect()
    start_cpu = process.cpu_times()
    start_time = time.perf_counter()

    result = run_analysis(
        config=config,
        paths=data_paths,
        settings=PipelineSettings(
            use_mageck=False,
            use_native_rra=use_native_rra,
            output_root=RUN_OUTPUT_DIR,
            enrichr_libraries=[],
        ),
    )

    runtime = time.perf_counter() - start_time
    end_cpu = process.cpu_times()
    cpu_seconds = (end_cpu.user - start_cpu.user) + (end_cpu.system - start_cpu.system)
    rss_mb = process.memory_info().rss / (1024 * 1024)
    cpu_percent = (cpu_seconds / runtime * 100.0) if runtime > 0 else 0.0

    metrics = {
        "runtime_seconds": runtime,
        "cpu_seconds": cpu_seconds,
        "cpu_percent": cpu_percent,
        "rss_mb": rss_mb,
    }
    return metrics, result


def summarise_runs(runs: List[Dict[str, float]]) -> Dict[str, float]:
    summary: Dict[str, float] = {}
    for key in ("runtime_seconds", "cpu_seconds", "cpu_percent", "rss_mb"):
        values = [run[key] for run in runs]
        summary[f"mean_{key}"] = statistics.mean(values)
        summary[f"stdev_{key}"] = statistics.pstdev(values) if len(values) > 1 else 0.0
    return summary


def run_backend_benchmark(
    spec: DatasetSpec,
    config: ExperimentConfig,
    data_paths: DataPaths,
    repeats: int,
    use_native_rra: bool,
    jsonl_path: Optional[Path] = None,
    backend_label: str = "python",
) -> Tuple[Dict[str, object], object]:
    process = psutil.Process()
    runs: List[Dict[str, float]] = []
    first_result: Optional[object] = None

    for idx in range(repeats):
        metrics, result = run_single_benchmark(config, data_paths, use_native_rra, process)
        runs.append(metrics)
        append_jsonl_record(jsonl_path, backend_label, idx + 1, spec, metrics)
        if first_result is None:
            first_result = result

    summary = summarise_runs(runs)
    summary.update(
        {
            "use_native_rra": use_native_rra,
            "repeats": repeats,
            "runs": [round_metrics(run) for run in runs],
        }
    )
    return summary, first_result


def round_metrics(metrics: Dict[str, float], digits: int = 6) -> Dict[str, float]:
    return {key: round(value, digits) for key, value in metrics.items()}


def gene_results_dataframe(result: object) -> pd.DataFrame:
    data = [gene.model_dump() for gene in result.gene_results]
    if not data:
        return pd.DataFrame()
    frame = pd.DataFrame(data)
    if "gene" in frame.columns and "gene_symbol" not in frame.columns:
        frame = frame.rename(columns={"gene": "gene_symbol"})
    return frame


def compare_results(python_result: object, native_result: object, tolerance: float = 1e-6) -> Dict[str, object]:
    python_df = gene_results_dataframe(python_result)
    native_df = gene_results_dataframe(native_result)

    info: Dict[str, object] = {
        "matched": True,
        "max_abs_delta": {},
        "missing_in_native": [],
        "missing_in_python": [],
        "tolerance": tolerance,
    }

    if python_df.empty and native_df.empty:
        return info

    python_df = python_df.set_index("gene_symbol").sort_index()
    native_df = native_df.set_index("gene_symbol").sort_index()

    missing_in_native = sorted(set(python_df.index) - set(native_df.index))
    missing_in_python = sorted(set(native_df.index) - set(python_df.index))

    if missing_in_native or missing_in_python:
        info["matched"] = False
    info["missing_in_native"] = missing_in_native[:10]
    info["missing_in_python"] = missing_in_python[:10]

    shared_genes = python_df.index.intersection(native_df.index)
    if shared_genes.empty:
        info["matched"] = False
        return info

    columns = [
        "score",
        "p_value",
        "fdr",
        "log2_fold_change",
        "rank",
        "n_guides",
    ]
    max_delta_overall = 0.0

    for column in columns:
        python_values = python_df.loc[shared_genes, column].to_numpy(dtype=float, copy=True)
        native_values = native_df.loc[shared_genes, column].to_numpy(dtype=float, copy=True)

        mask = np.isfinite(python_values) & np.isfinite(native_values)
        if not mask.any():
            delta = 0.0
        else:
            delta = float(np.max(np.abs(python_values[mask] - native_values[mask])))
        info["max_abs_delta"][column] = delta
        max_delta_overall = max(max_delta_overall, delta)
        if delta > tolerance:
            info["matched"] = False

    info["max_abs_delta_overall"] = max_delta_overall
    return info


def write_report(
    report_dir: Path,
    timestamp: str,
    spec: DatasetSpec,
    repeats: int,
    python_summary: Dict[str, object],
    native_summary: Optional[Dict[str, object]],
    parity: Optional[Dict[str, object]],
) -> None:
    report_dir.mkdir(parents=True, exist_ok=True)

    payload: Dict[str, object] = {
        "timestamp": timestamp,
        "dataset": {
            "size": spec.name,
            "guides": spec.guides,
            "guides_per_gene": spec.guides_per_gene,
            "replicates": spec.replicates,
            "seed": spec.seed,
        },
        "repeats": repeats,
        "python": round_nested(python_summary),
    }

    if native_summary is not None:
        payload["native"] = round_nested(native_summary)
    if parity is not None:
        payload["parity"] = parity

    (report_dir / "metrics.json").write_text(json.dumps(payload, indent=2))
    (report_dir / "summary.md").write_text(render_markdown(payload))


def round_nested(data: Dict[str, object]) -> Dict[str, object]:
    rounded: Dict[str, object] = {}
    for key, value in data.items():
        if isinstance(value, list):
            rounded[key] = [round_nested(item) if isinstance(item, dict) else item for item in value]
        elif isinstance(value, dict):
            rounded[key] = round_nested(value)
        elif isinstance(value, float):
            rounded[key] = round(value, 6)
        else:
            rounded[key] = value
    return rounded


def render_markdown(payload: Dict[str, object]) -> str:
    dataset = payload["dataset"]
    python_summary = payload["python"]
    native_summary = payload.get("native")
    parity = payload.get("parity")

    lines = [
        f"# Benchmark Summary — {payload['timestamp']}",
        "",
        f"- Dataset: {dataset['size']} (guides: {dataset['guides']:,}, replicates: {dataset['replicates']})",
        f"- Repeats: {payload['repeats']}",
        f"- Python runtime (mean ± stdev): {python_summary['mean_runtime_seconds']:.4f}s ± {python_summary['stdev_runtime_seconds']:.4f}s",
        f"- Python RSS (mean): {python_summary['mean_rss_mb']:.2f} MB",
    ]

    if native_summary:
        speedup = python_summary['mean_runtime_seconds'] / native_summary['mean_runtime_seconds'] if native_summary['mean_runtime_seconds'] else float('nan')
        lines.append(
            f"- Native runtime (mean ± stdev): {native_summary['mean_runtime_seconds']:.4f}s ± {native_summary['stdev_runtime_seconds']:.4f}s",
        )
        lines.append(f"- Native RSS (mean): {native_summary['mean_rss_mb']:.2f} MB")
        if not math.isnan(speedup):
            lines.append(f"- Speedup vs Python: {speedup:.2f}×")
        if parity:
            status = "✅ Matched" if parity.get("matched") else "⚠️ Divergence"
            max_delta = parity.get("max_abs_delta_overall", float('nan'))
            lines.append(f"- Parity: {status} (max |Δ| = {max_delta:.2e})")
    else:
        lines.append("- Native backend: not benchmarked")

    lines.append("")
    lines.append("## Per-run Metrics")
    lines.append("")
    headers = "| Backend | Run | Runtime (s) | CPU (s) | CPU (%) | RSS (MB) |"
    separator = "| --- | --- | --- | --- | --- | --- |"
    lines.extend([headers, separator])

    def emit_rows(label: str, runs: List[Dict[str, float]]):
        for idx, run in enumerate(runs, start=1):
            lines.append(
                f"| {label} | {idx} | {run['runtime_seconds']:.4f} | {run['cpu_seconds']:.4f} | {run['cpu_percent']:.2f} | {run['rss_mb']:.2f} |"
            )

    emit_rows("Python", python_summary["runs"])
    if native_summary:
        emit_rows("Native", native_summary["runs"])

    return "\n".join(lines)


def write_runtime_plot(report_dir: Path, points: List[Dict[str, object]]) -> Optional[Path]:
    if not points:
        return None
    df = pd.DataFrame(points)
    fig = px.line(
        df,
        x="guides",
        y="runtime_seconds",
        color="backend",
        markers=True,
        hover_data=["dataset", "backend", "replicates"],
        title="Runtime vs dataset size",
    )
    fig.update_layout(xaxis_title="Guides", yaxis_title="Mean runtime (s)")
    plot_path = report_dir / "runtime_vs_size.html"
    fig.write_html(plot_path)
    return plot_path


def main() -> None:
    args = parse_args()
    sizes = list(DATASET_SPECS.keys()) if args.all_sizes else [args.dataset_size]
    RUN_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    benchmark_root = ARTIFACT_ROOT / timestamp
    benchmark_root.mkdir(parents=True, exist_ok=True)

    repeats = max(args.repeat, 1)
    jsonl_path: Optional[Path] = args.jsonl_path or (benchmark_root / "runs.jsonl" if args.jsonl else None)
    plot_points: List[Dict[str, object]] = []

    for size in sizes:
        spec, data_paths, config = ensure_dataset(size)

        python_summary, python_result = run_backend_benchmark(
            spec,
            config,
            data_paths,
            repeats,
            use_native_rra=False,
            jsonl_path=jsonl_path,
            backend_label="python",
        )
        plot_points.append(
            {
                "backend": "python",
                "runtime_seconds": python_summary["mean_runtime_seconds"],
                "guides": spec.guides,
                "dataset": spec.name,
                "replicates": spec.replicates,
            }
        )

        native_requested = args.use_native_rra
        if native_requested is None:
            native_requested = native_rra.is_available()

        native_summary: Optional[Dict[str, object]] = None
        native_result: Optional[object] = None

        if native_requested:
            if native_rra.is_available():
                native_summary, native_result = run_backend_benchmark(
                    spec,
                    config,
                    data_paths,
                    repeats,
                    use_native_rra=True,
                    jsonl_path=jsonl_path,
                    backend_label="native",
                )
            else:
                print("Native backend unavailable — skipping native benchmark.")

        parity_info: Optional[Dict[str, object]] = None
        if native_result is not None:
            parity_info = compare_results(python_result, native_result)

        report_dir = benchmark_root / spec.name
        write_report(
            report_dir,
            timestamp,
            spec,
            repeats,
            python_summary,
            native_summary,
            parity_info,
        )
        if native_summary:
            plot_points.append(
                {
                    "backend": "native",
                    "runtime_seconds": native_summary["mean_runtime_seconds"],
                    "guides": spec.guides,
                    "dataset": spec.name,
                    "replicates": spec.replicates,
                }
            )

        print(f"Dataset: {spec.name} (guides={spec.guides:,}, replicates={spec.replicates})")
        print(f"Python mean runtime: {python_summary['mean_runtime_seconds']:.4f}s")
        if native_summary:
            speedup = (
                python_summary['mean_runtime_seconds'] / native_summary['mean_runtime_seconds']
                if native_summary['mean_runtime_seconds']
                else float('nan')
            )
            print(f"Native mean runtime: {native_summary['mean_runtime_seconds']:.4f}s (speedup {speedup:.2f}×)")
            if parity_info:
                status = "passed" if parity_info.get("matched") else "FAILED"
                print(f"Parity check: {status} (max |Δ| = {parity_info.get('max_abs_delta_overall', float('nan')):.2e})")
        else:
            print("Native backend not benchmarked.")
        print(f"Benchmark artifacts written to {report_dir}")

    if args.plot:
        write_runtime_plot(benchmark_root, plot_points)

    if jsonl_path:
        print(f"Per-run metrics appended to {jsonl_path}")


if __name__ == "__main__":
    main()
