from __future__ import annotations

import numpy as np

from crispr_screen_expert.normalization import (
    compute_gene_stats,
    compute_log2_fold_change,
    normalize_counts_cpm,
)


def test_normalize_counts_cpm(counts_df):
    cpm = normalize_counts_cpm(counts_df)
    assert np.isclose(cpm.sum(axis=0), 1_000_000).all()


def test_compute_log2fc_direction(counts_df, experiment_config):
    cpm = normalize_counts_cpm(counts_df)
    log2fc = compute_log2_fold_change(cpm, experiment_config)
    assert log2fc.name == "log2_fold_change"
    assert not log2fc.isna().any()


def test_compute_gene_stats(counts_df, library_df, experiment_config):
    cpm = normalize_counts_cpm(counts_df)
    log2fc = compute_log2_fold_change(cpm, experiment_config)
    stats = compute_gene_stats(log2fc, library_df)
    assert "mean_log2fc" in stats.columns
    assert (stats["n_guides"] >= 1).all()
