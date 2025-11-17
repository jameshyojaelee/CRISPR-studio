from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from crispr_screen_expert.cli import app
from crispr_screen_expert.exceptions import QualityControlError
from crispr_screen_expert.models import load_experiment_config
from crispr_screen_expert.native import enrichment as native_enrichment
from crispr_screen_expert.pipeline import DataPaths, PipelineSettings, run_analysis


def _write_counts(path: Path, rows: list[tuple[str, int, int]]) -> None:
    lines = ["guide_id,CTRL1,TREAT1"]
    for guide, ctrl, treat in rows:
        lines.append(f"{guide},{ctrl},{treat}")
    path.write_text("\n".join(lines) + "\n")


def _write_library(path: Path, guides: list[tuple[str, str]]) -> None:
    lines = ["guide_id,gene_symbol"]
    for guide, gene in guides:
        lines.append(f"{guide},{gene}")
    path.write_text("\n".join(lines) + "\n")


def _write_metadata(path: Path) -> None:
    payload = {
        "experiment_name": "QC Gate",
        "screen_type": "dropout",
        "samples": [
            {"sample_id": "CTRL1", "column": "CTRL1", "condition": "control", "replicate": "1", "role": "control"},
            {"sample_id": "TREAT1", "column": "TREAT1", "condition": "treatment", "replicate": "1", "role": "treatment"},
        ],
        "analysis": {"min_count_threshold": 10},
    }
    path.write_text(json.dumps(payload))


def test_run_analysis_aborts_on_critical_qc(tmp_path: Path) -> None:
    counts_path = tmp_path / "counts.csv"
    library_path = tmp_path / "library.csv"
    metadata_path = tmp_path / "metadata.json"

    _write_counts(counts_path, [("g1", 0, 0), ("g2", 0, 0)])
    _write_library(library_path, [("g1", "GENE1"), ("g2", "GENE2")])
    _write_metadata(metadata_path)

    config = load_experiment_config(metadata_path)

    with pytest.raises(QualityControlError):
        run_analysis(
            config=config,
            paths=DataPaths(counts=counts_path, library=library_path, metadata=metadata_path),
            settings=PipelineSettings(use_mageck=False, output_root=tmp_path, cache_annotations=False),
        )


def test_cli_reports_qc_failure(tmp_path: Path) -> None:
    counts_path = tmp_path / "counts.csv"
    library_path = tmp_path / "library.csv"
    metadata_path = tmp_path / "metadata.json"

    _write_counts(counts_path, [("g1", 0, 0)])
    _write_library(library_path, [("g1", "GENE1")])
    _write_metadata(metadata_path)

    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "run-pipeline",
            str(counts_path),
            str(library_path),
            str(metadata_path),
            "--use-mageck",
            "false",
            "--skip-annotations",
        ],
    )
    assert result.exit_code == 2
    assert "Analysis aborted" in result.stdout or "Analysis aborted" in result.stderr


def test_mageck_positive_direction_updates_significant_genes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    metadata_payload = json.loads(Path("sample_data/demo_metadata.json").read_text())
    metadata_payload["screen_type"] = "enrichment"
    metadata_payload["analysis"] = metadata_payload.get("analysis", {})
    metadata_payload["analysis"]["min_count_threshold"] = 10
    metadata_payload["analysis"]["scoring_method"] = "mageck"
    metadata_payload["fdr_threshold"] = 0.05

    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(json.dumps(metadata_payload))
    config = load_experiment_config(metadata_path)

    def fake_run_mageck(*args, **kwargs):
        return pd.DataFrame(
            {
                "gene": ["GENE_A", "GENE_B"],
                "neg|score": [0.5, 0.4],
                "neg|p-value": [0.8, 0.6],
                "neg|fdr": [0.7, 0.6],
                "neg|rank": [10, 11],
                "pos|score": [2.5, 0.5],
                "pos|p-value": [0.001, 0.2],
                "pos|fdr": [0.01, 0.2],
                "pos|rank": [1, 2],
            }
        )

    monkeypatch.setattr("crispr_screen_expert.pipeline.run_mageck", fake_run_mageck)

    result = run_analysis(
        config=config,
        paths=DataPaths(
            counts=Path("sample_data/demo_counts.csv"),
            library=Path("sample_data/demo_library.csv"),
            metadata=metadata_path,
        ),
        settings=PipelineSettings(
            use_mageck=True,
            output_root=tmp_path,
            enrichr_libraries=[],
            cache_annotations=False,
        ),
    )

    assert result.summary.significant_genes == 1
    assert any(gene.gene_symbol == "GENE_A" and gene.fdr == pytest.approx(0.01) for gene in result.gene_results)


def test_native_enrichment_runtime_error_falls_back(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    config = load_experiment_config(Path("sample_data/demo_metadata.json"))

    def _fail_native(*args, **kwargs):
        raise RuntimeError("backend crashed")

    fallback_calls = {"count": 0}

    def _fake_enrichr(genes, libraries, cutoff):
        fallback_calls["count"] += 1
        return []

    monkeypatch.setattr(native_enrichment, "run_enrichment_native", _fail_native)
    monkeypatch.setattr("crispr_screen_expert.pipeline.run_enrichr", _fake_enrichr)

    result = run_analysis(
        config=config,
        paths=DataPaths(
            counts=Path("sample_data/demo_counts.csv"),
            library=Path("sample_data/demo_library.csv"),
            metadata=Path("sample_data/demo_metadata.json"),
        ),
        settings=PipelineSettings(
            use_mageck=False,
            use_native_rra=False,
            use_native_enrichment=True,
            enrichr_libraries=["native_demo"],
            output_root=tmp_path,
            cache_annotations=False,
        ),
    )

    assert fallback_calls["count"] == 1
    assert any(warning.code == "native_enrichment_backend_failed" for warning in result.warnings)
