from __future__ import annotations

import json
from importlib import reload
from typing import Dict

import pandas as pd
import pytest

from crispr_screen_expert.models import (
    AnalysisResult,
    AnalysisSummary,
    ExperimentConfig,
    GeneResult,
    GuideRecord,
    NarrativeSnippet,
    PipelineWarning,
    SampleConfig,
    ScoringMethod,
    ScreenType,
)
from crispr_screen_expert.pipeline import PipelineSettings

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
        warnings=[PipelineWarning(code="legacy_warning", message="Example warning")],
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
    (run_dir / "pipeline_settings.json").write_text(
        json.dumps(
            {
                "use_mageck": False,
                "use_native_rra": True,
                "use_native_enrichment": True,
                "enrichr_libraries": ["native_demo"],
                "skip_annotations": True,
            },
            indent=2,
        )
    )

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
    history_badges = dash_duo.find_element(".history-item .job-settings-pill-row").text
    assert "Native RRA" in history_badges
    assert "Native enrichment" in history_badges

    dash_duo.find_element(".history-item").click()

    dash_duo.wait_for_text_to_equal("#table-genes tbody tr:nth-child(1) td:nth-child(1) div", "GENE1")

    dash_duo.find_element("#table-genes tbody tr").click()

    dash_duo.wait_for_element(".gene-modal")
    dash_duo.wait_for_element(".gene-sparkline")
    assert dash_duo.find_element(".gene-download-btn").is_displayed()


@pytest.mark.dash
def test_pipeline_settings_toggle_passthrough(dash_duo, tmp_path, monkeypatch):
    artifacts_dir = tmp_path / "artifacts"
    uploads_dir = tmp_path / "uploads"
    logs_dir = tmp_path / "logs"
    artifacts_dir.mkdir()
    uploads_dir.mkdir()
    logs_dir.mkdir()

    counts_path = tmp_path / "counts.csv"
    pd.DataFrame(
        {
            "guide_id": ["g1", "g2"],
            "CTRL1": [100, 120],
            "TREAT1": [80, 60],
        }
    ).to_csv(counts_path, index=False)

    library_path = tmp_path / "library.csv"
    pd.DataFrame(
        {
            "guide_id": ["g1", "g2"],
            "gene_symbol": ["GENE1", "GENE2"],
        }
    ).to_csv(library_path, index=False)

    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "experiment_name": "Toggle Test",
                "samples": [
                    {"sample_id": "CTRL1", "condition": "control", "replicate": "1", "role": "control", "file_column": "CTRL1"},
                    {"sample_id": "TREAT1", "condition": "treatment", "replicate": "1", "role": "treatment", "file_column": "TREAT1"},
                ],
                "analysis": {"fdr_threshold": 0.1},
            },
            indent=2,
        )
    )

    captured: Dict[str, PipelineSettings] = {}

    def _fake_run_analysis(config, paths, settings):
        captured["settings"] = settings
        summary = AnalysisSummary(
            total_guides=2,
            total_genes=2,
            significant_genes=1,
            runtime_seconds=1.2,
            screen_type=ScreenType.DROPOUT,
            scoring_method=ScoringMethod.RRA,
        )
        gene = GeneResult(gene_symbol="GENE1", score=4.2, log2_fold_change=-1.1, fdr=0.02, rank=1, n_guides=2, guides=[])
        result = AnalysisResult(
            config=config,
            summary=summary,
            gene_results=[gene],
            qc_metrics=[],
            qc_flags=[],
            narratives=[],
            artifacts={"raw_counts": str(counts_path)},
            warnings=[],
        )
        run_dir = artifacts_dir / "20240202_020202"
        run_dir.mkdir(parents=True, exist_ok=True)
        analysis_json = run_dir / "analysis_result.json"
        analysis_json.write_text(json.dumps(result.model_dump(mode="json"), indent=2))
        pipeline_settings_path = run_dir / "pipeline_settings.json"
        pipeline_settings_path.write_text(
            json.dumps(
                {
                    "use_mageck": settings.use_mageck,
                    "use_native_rra": settings.use_native_rra,
                    "use_native_enrichment": settings.use_native_enrichment,
                    "enrichr_libraries": list(settings.enrichr_libraries or []),
                    "skip_annotations": not settings.cache_annotations,
                },
                indent=2,
            )
        )
        result.artifacts["analysis_result"] = str(analysis_json)
        return result

    monkeypatch.setenv("CRISPR_STUDIO__ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("CRISPR_STUDIO__UPLOADS_DIR", str(uploads_dir))
    monkeypatch.setenv("CRISPR_STUDIO__LOGS_DIR", str(logs_dir))

    import crispr_screen_expert.app.callbacks as callbacks
    import crispr_screen_expert.app.layout as layout
    import crispr_screen_expert.app as app_module

    reload(callbacks)
    reload(layout)
    reload(app_module)
    monkeypatch.setattr(callbacks, "run_analysis", _fake_run_analysis)

    app = app_module.create_app()
    dash_duo.start_server(app)

    dash_duo.wait_for_element("#upload-counts input[type='file']").send_keys(str(counts_path))
    dash_duo.wait_for_element("#upload-library input[type='file']").send_keys(str(library_path))
    dash_duo.wait_for_element("#upload-metadata input[type='file']").send_keys(str(metadata_path))
    dash_duo.wait_for_text_contains("#upload-status", "Metadata uploaded")

    dash_duo.find_element("input#switch-use-mageck").click()
    dash_duo.find_element("input#switch-native-rra").click()
    dash_duo.find_element("input#switch-native-enrichment").click()
    dash_duo.find_element("input#switch-skip-annotations").click()
    dash_duo.select_dcc_dropdown("#dropdown-enrichr-libraries", "native_demo")

    dash_duo.find_element("#button-run-analysis").click()
    dash_duo.wait_for_text_to_equal("#job-status-text", "Analysis complete")

    settings_text = dash_duo.find_element("#job-status-settings").text
    assert "RRA only" in settings_text
    assert "Native RRA" in settings_text
    assert "Native enrichment" in settings_text
    assert "Skip annotations" in settings_text
    assert "native_demo" in settings_text

    settings_obj = captured["settings"]
    assert settings_obj.use_mageck is False
    assert settings_obj.use_native_rra is True
    assert settings_obj.use_native_enrichment is True
    assert settings_obj.enrichr_libraries == ["native_demo"]
    assert settings_obj.cache_annotations is False
