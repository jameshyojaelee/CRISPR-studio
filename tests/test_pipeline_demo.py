from __future__ import annotations

from pathlib import Path

from crispr_screen_expert.pipeline import DataPaths, PipelineSettings, run_analysis


def test_pipeline_demo_run(tmp_path):
    result = run_analysis(
        config=None,
        paths=DataPaths(
            counts=Path("sample_data/demo_counts.csv"),
            library=Path("sample_data/demo_library.csv"),
            metadata=Path("sample_data/demo_metadata.json"),
        ),
        settings=PipelineSettings(use_mageck=False, output_root=tmp_path, enrichr_libraries=[]),
    )

    assert result.summary.total_guides == 14
    assert any("BRCA2" in gene.gene_symbol for gene in result.gene_results)
    assert all(metric.name for metric in result.qc_metrics)
