from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import plotly.io as pio
import pytest

from crispr_screen_expert.models import (
    AnalysisResult,
    AnalysisSummary,
    ExperimentConfig,
    GeneResult,
    GuideRecord,
    NarrativeSnippet,
    PipelineWarning,
    QCMetric,
    QCSeverity,
    SampleConfig,
    ScoringMethod,
    ScreenType,
)
from crispr_screen_expert.reporting import export_pdf, render_html


def _build_sample_result(tmp_path: Path) -> AnalysisResult:
    samples = [
        SampleConfig(sample_id="CTRL1", condition="control", replicate="1", role="control", file_column="CTRL1"),
        SampleConfig(sample_id="TREAT1", condition="treatment", replicate="1", role="treatment", file_column="TREAT1"),
    ]

    config = ExperimentConfig(samples=samples, experiment_name="Demo Experiment")
    summary = AnalysisSummary(
        total_guides=2,
        total_genes=1,
        significant_genes=1,
        runtime_seconds=12.3,
        screen_type=ScreenType.DROPOUT,
        scoring_method=ScoringMethod.RRA,
    )

    guides = [
        GuideRecord(guide_id="g1", gene_symbol="GENE1", log2_fold_change=-1.2),
        GuideRecord(guide_id="g2", gene_symbol="GENE1", log2_fold_change=-0.8),
    ]

    gene = GeneResult(
        gene_symbol="GENE1",
        score=5.0,
        log2_fold_change=-1.0,
        fdr=0.02,
        rank=1,
        n_guides=2,
        guides=guides,
        is_significant=True,
    )

    qc_metrics = [
        QCMetric(name="Library coverage", value=0.95, severity=QCSeverity.OK, details="1/20 guides missing", recommendation=None),
        QCMetric(name="Replicate correlation", value=0.6, severity=QCSeverity.WARNING, details="CTRL1 vs TREAT1", recommendation="Investigate batch"),
    ]

    narratives = [NarrativeSnippet(title="Summary", body="Example narrative.", source="system")]

    counts_path = tmp_path / "normalized_counts.csv"
    pd.DataFrame({"guide_id": ["g1", "g2"], "CTRL1": [100, 80], "TREAT1": [50, 40]}).to_csv(counts_path, index=False)
    analysis_result_path = tmp_path / "analysis_result.json"
    analysis_result_path.write_text("{}")

    return AnalysisResult(
        config=config,
        summary=summary,
        gene_results=[gene],
        qc_metrics=qc_metrics,
        qc_flags=[],
        pathway_results=[],
        narratives=narratives,
        artifacts={
            "normalized_counts": str(counts_path),
            "analysis_result": str(analysis_result_path),
        },
        warnings=[PipelineWarning(code="legacy_warning", message="Example warning")],
    )


def test_render_html_snapshot(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pio, "to_image", lambda *args, **kwargs: b"<svg class='placeholder'></svg>")
    result = _build_sample_result(tmp_path)
    html = render_html(result)
    normalized = re.sub(r"\s+", " ", html).strip()
    snapshot = Path("tests/snapshots/report_basic_normalized.txt").read_text()
    assert normalized == snapshot


def test_export_pdf(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pio, "to_image", lambda *args, **kwargs: b"<svg class='placeholder'></svg>")
    try:
        import weasyprint  # noqa: F401
    except Exception:
        pytest.skip("WeasyPrint runtime dependencies not available")

    result = _build_sample_result(tmp_path)
    output_pdf = tmp_path / "report.pdf"
    export_pdf(result, output_pdf)
    assert output_pdf.exists()
    assert output_pdf.stat().st_size > 0
