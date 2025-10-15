from __future__ import annotations

from crispr_screen_expert.qc import (
    QCSeverity,
    compute_guide_detection,
    compute_replicate_correlations,
    run_all_qc,
)


def test_replicate_correlation_metrics(counts_df, experiment_config):
    metrics = compute_replicate_correlations(counts_df, experiment_config)
    assert metrics
    names = {metric.name for metric in metrics}
    assert any("Replicate correlation" in name for name in names)


def test_guide_detection_threshold(counts_df):
    metrics = compute_guide_detection(counts_df, min_count=10)
    assert all(metric.value == 1.0 for metric in metrics)


def test_run_all_qc_returns_severities(counts_df, library_df, experiment_config):
    metrics = run_all_qc(counts_df, library_df, experiment_config, min_count=10)
    severities = {metric.severity for metric in metrics}
    assert QCSeverity.OK in severities or QCSeverity.WARNING in severities
