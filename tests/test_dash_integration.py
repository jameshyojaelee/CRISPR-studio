from __future__ import annotations

import json
from importlib import reload

import pandas as pd
import pytest

from crispr_screen_expert.models import (
    AnalysisResult,
    AnalysisSummary,
    ExperimentConfig,
    GeneResult,
    GuideRecord,
    NarrativeSnippet,
    SampleConfig,
    ScoringMethod,
    ScreenType,
)

pytest.importorskip("dash.testing")


@pytest.mark.dash
def test_history_panel_and_gene_modal(dash_duo, tmp_path, monkeypatch):
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    run_dir = artifacts_dir / "20240101_010101"
    run_dir.mkdir()

    samples = [
        SampleConfig(
            sample_id="CTRL1",
            condition="control",
            replicate="1",
            role="control",
            file_column="CTRL1",
        ),
        SampleConfig(
            sample_id="TREAT1",
            condition="treatment",
            replicate="1",
            role="treatment",
            file_column="TREAT1",
        ),
    ]

    config = ExperimentConfig(samples=samples)
    summary = AnalysisSummary(
        total_guides=2,
        total_genes=1,
        significant_genes=1,
        runtime_seconds=2.5,
        screen_type=ScreenType.DROPOUT,
        scoring_method=ScoringMethod.RRA,
    )

    guides = [
        GuideRecord(guide_id="g1", gene_symbol="GENE1", log2_fold_change=-1.2),
        GuideRecord(guide_id="g2", gene_symbol="GENE1", log2_fold_change=-0.8),
    ]

    gene_result = GeneResult(
        gene_symbol="GENE1",
        score=5.0,
        log2_fold_change=-1.0,
        fdr=0.01,
        rank=1,
        n_guides=2,
        guides=guides,
        is_significant=True,
    )

    analysis_result = AnalysisResult(
        config=config,
        summary=summary,
        gene_results=[gene_result],
        qc_metrics=[],
        qc_flags=[],
        narratives=[NarrativeSnippet(title="Summary", body="Test", source="system")],
        artifacts={},
        warnings=["Example warning"],
    )

    gene_results_path = run_dir / "gene_results.csv"
    pd.DataFrame(
        [
            {
                "gene": "GENE1",
                "score": 5.0,
                "fdr": 0.01,
                "log2_fold_change": -1.0,
                "rank": 1,
                "n_guides": 2,
            }
        ]
    ).to_csv(gene_results_path, index=False)

    raw_counts_path = run_dir / "raw_counts.csv"
    pd.DataFrame(
        {
            "guide_id": ["g1", "g2"],
            "CTRL1": [100, 120],
            "TREAT1": [40, 60],
        }
    ).to_csv(raw_counts_path, index=False)

    normalized_counts_path = run_dir / "normalized_counts.csv"
    pd.DataFrame(
        {
            "guide_id": ["g1", "g2"],
            "CTRL1": [50000, 60000],
            "TREAT1": [20000, 30000],
        }
    ).to_csv(normalized_counts_path, index=False)

    annotations_path = run_dir / "gene_annotations.json"
    annotations_path.write_text(json.dumps({"GENE1": {"symbol": "GENE1", "summary": "Example gene"}}))

    analysis_result.artifacts = {
        "analysis_result": str(run_dir / "analysis_result.json"),
        "gene_results": str(gene_results_path),
        "raw_counts": str(raw_counts_path),
        "normalized_counts": str(normalized_counts_path),
        "gene_annotations": str(annotations_path),
    }

    (run_dir / "analysis_result.json").write_text(json.dumps(analysis_result.model_dump(mode="json"), indent=2))

    monkeypatch.setenv("CRISPR_STUDIO__ARTIFACTS_DIR", str(artifacts_dir))

    # Reload layout/callbacks so settings pick up the temp artifacts directory
    import crispr_screen_expert.app.callbacks as callbacks
    import crispr_screen_expert.app.layout as layout
    import crispr_screen_expert.app as app_module

    reload(callbacks)
    reload(layout)
    reload(app_module)

    app = app_module.create_app()
    dash_duo.start_server(app)

    dash_duo.wait_for_element(".history-item-title")
    history_titles = [el.text for el in dash_duo.find_elements(".history-item-title")]
    assert any("GENE1" in title or "Untitled" in title for title in history_titles)

    dash_duo.find_element(".history-item").click()

    dash_duo.wait_for_text_to_equal("#table-genes tbody tr:nth-child(1) td:nth-child(1) div", "GENE1")

    dash_duo.find_element("#table-genes tbody tr").click()

    dash_duo.wait_for_element(".gene-modal")
    dash_duo.wait_for_element(".gene-sparkline")
    assert dash_duo.find_element(".gene-download-btn").is_displayed()
