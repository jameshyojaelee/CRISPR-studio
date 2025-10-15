from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from crispr_screen_expert.native import rra as native_rra
from crispr_screen_expert.normalization import compute_log2_fold_change, normalize_counts_cpm
from crispr_screen_expert.pipeline import DataPaths, PipelineSettings, run_analysis
from crispr_screen_expert.rra import run_rra as run_rra_python


@pytest.fixture()
def log2fc_series(counts_df, experiment_config):
    cpm = normalize_counts_cpm(counts_df)
    return compute_log2_fold_change(cpm, experiment_config)


@pytest.mark.skipif(not native_rra.is_available(), reason="Native RRA backend not built")
def test_native_rra_matches_python(log2fc_series, library_df):
    native_df = native_rra.run_rra_native(log2fc_series, library_df)
    python_df = run_rra_python(log2fc_series, library_df)

    native_df = native_df.sort_values("gene").reset_index(drop=True)
    python_df = python_df.sort_values("gene").reset_index(drop=True)

    numeric_cols = [
        "score",
        "p_value",
        "fdr",
        "mean_log2fc",
        "median_log2fc",
        "var_log2fc",
    ]
    np.testing.assert_allclose(native_df[numeric_cols], python_df[numeric_cols], rtol=1e-8, atol=1e-10)
    pd.testing.assert_series_equal(native_df["rank"], python_df["rank"], check_names=False)
    pd.testing.assert_series_equal(native_df["n_guides"], python_df["n_guides"], check_names=False)


def test_native_rra_import_error(monkeypatch, log2fc_series, library_df):
    monkeypatch.setattr(native_rra, "_NATIVE_AVAILABLE", False, raising=False)
    monkeypatch.setattr(native_rra, "_IMPORT_ERROR", ImportError("missing backend"), raising=False)

    with pytest.raises(ImportError) as excinfo:
        native_rra.run_rra_native(log2fc_series, library_df)
    assert "native" in str(excinfo.value).lower()


def test_pipeline_native_flag_fallback(monkeypatch, tmp_path, experiment_config):
    monkeypatch.setattr(native_rra, "is_available", lambda: False)

    result = run_analysis(
        config=experiment_config,
        paths=DataPaths(
            counts=Path("sample_data/demo_counts.csv"),
            library=Path("sample_data/demo_library.csv"),
            metadata=Path("sample_data/demo_metadata.json"),
        ),
        settings=PipelineSettings(use_mageck=False, use_native_rra=True, output_root=tmp_path, enrichr_libraries=[]),
    )

    assert any("native rra" in warning.lower() for warning in result.warnings)


def test_pipeline_uses_native_backend(monkeypatch, tmp_path, experiment_config):
    fake_df = pd.DataFrame(
        {
            "gene": ["FAKE1"],
            "score": [5.0],
            "p_value": [1e-5],
            "fdr": [1e-5],
            "rank": [1],
            "n_guides": [3],
            "mean_log2fc": [0.5],
            "median_log2fc": [0.5],
            "var_log2fc": [0.0],
        }
    )

    monkeypatch.setattr(native_rra, "is_available", lambda: True)

    def _fake_run_rra(log2fc, library, guide_pvalues=None, *, min_guides=2, higher_is_better=True):
        return fake_df.copy()

    monkeypatch.setattr(native_rra, "run_rra_native", _fake_run_rra)

    result = run_analysis(
        config=experiment_config,
        paths=DataPaths(
            counts=Path("sample_data/demo_counts.csv"),
            library=Path("sample_data/demo_library.csv"),
            metadata=Path("sample_data/demo_metadata.json"),
        ),
        settings=PipelineSettings(use_mageck=False, use_native_rra=True, output_root=tmp_path, enrichr_libraries=[]),
    )

    assert any(gene.gene_symbol == "FAKE1" for gene in result.gene_results)
    assert not any("native rra" in warning.lower() for warning in result.warnings)
