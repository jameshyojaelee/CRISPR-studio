from __future__ import annotations

from crispr_screen_expert.rra import run_rra


def test_run_rra_returns_gene_dataframe(counts_df, library_df, experiment_config):
    from crispr_screen_expert.normalization import normalize_counts_cpm, compute_log2_fold_change

    cpm = normalize_counts_cpm(counts_df)
    log2fc = compute_log2_fold_change(cpm, experiment_config)
    df = run_rra(log2fc, library_df)
    assert "gene" in df.columns
    assert "p_value" in df.columns
    assert len(df) > 0
