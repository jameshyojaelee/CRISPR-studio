from __future__ import annotations

import asyncio
from pathlib import Path

import numpy as np
import pytest
from scipy.stats import hypergeom

from crispr_screen_expert.exceptions import DataContractError
from crispr_screen_expert.models import PathwayResult
from crispr_screen_expert.native import enrichment as native_enrichment
from crispr_screen_expert.pipeline import DataPaths, PipelineSettings, run_analysis


@pytest.mark.skipif(not native_enrichment.is_available(), reason="Native enrichment backend not built")
def test_native_enrichment_hypergeom_matches_scipy():
    libs = {"demo": {"SET1": ["A", "B", "C"], "SET2": ["D", "E", "F"]}}
    hits = ["A", "B"]
    frame = native_enrichment._compute_enrichment_frame(hits, libs)  # type: ignore[attr-defined]
    frame = frame.sort_values("name").reset_index(drop=True)

    universe_size = 6
    sample_size = 2

    expected_set1 = hypergeom.sf(2 - 1, universe_size, 3, sample_size)
    expected_set2 = hypergeom.sf(0 - 1, universe_size, 3, sample_size)

    np.testing.assert_allclose(frame.loc[0, "p_value"], expected_set1)
    np.testing.assert_allclose(frame.loc[1, "p_value"], expected_set2)
    assert frame.loc[0, "overlap"] == 2
    assert frame.loc[1, "overlap"] == 0


@pytest.mark.skipif(not native_enrichment.is_available(), reason="Native enrichment backend not built")
def test_native_enrichment_async_matches_sync(monkeypatch):
    libs = {"demo": {"SET": ["X", "Y", "Z"]}}
    hits = ["X", "Z"]
    monkeypatch.setattr(native_enrichment, "load_gene_sets", lambda _: libs)
    sync_results = native_enrichment.run_enrichment_native(hits, ["demo"], background=["X", "Y", "Z", "W"], fdr_threshold=1.0)
    async_results = asyncio.run(
        native_enrichment.run_enrichment_native_async(
            hits,
            ["demo"],
            background=["X", "Y", "Z", "W"],
            fdr_threshold=1.0,
        )
    )
    assert async_results == sync_results


def test_pipeline_native_enrichment_integration(monkeypatch, tmp_path, experiment_config):
    fake_result = [
        PathwayResult(
            pathway_id="demo:SET",
            name="SET",
            source="demo",
            enrichment_score=5.0,
            p_value=1e-4,
            fdr=1e-4,
            genes=["BRCA2"],
            direction=None,
            description=None,
        )
    ]

    monkeypatch.setattr(native_enrichment, "run_enrichment_native", lambda *args, **kwargs: fake_result)

    result = run_analysis(
        config=experiment_config,
        paths=DataPaths(
            counts=Path("sample_data/demo_counts.csv"),
            library=Path("sample_data/demo_library.csv"),
        ),
        settings=PipelineSettings(
            use_mageck=False,
            use_native_rra=False,
            use_native_enrichment=True,
            enrichr_libraries=["native_demo"],
            output_root=tmp_path,
        ),
    )

    assert any(pathway.pathway_id == "demo:SET" for pathway in result.pathway_results)


def test_pipeline_native_enrichment_fallback(monkeypatch, tmp_path, experiment_config):
    monkeypatch.setattr(
        native_enrichment,
        "run_enrichment_native",
        lambda *args, **kwargs: (_ for _ in ()).throw(ImportError("no backend")),
    )
    fallback_calls = {"count": 0}

    def _fake_enrichr(genes, libraries, cutoff):
        fallback_calls["count"] += 1
        return []

    monkeypatch.setattr("crispr_screen_expert.pipeline.run_enrichr", _fake_enrichr)

    result = run_analysis(
        config=experiment_config,
        paths=DataPaths(
            counts=Path("sample_data/demo_counts.csv"),
            library=Path("sample_data/demo_library.csv"),
        ),
        settings=PipelineSettings(
            use_mageck=False,
            use_native_rra=False,
            use_native_enrichment=True,
            enrichr_libraries=["native_demo"],
            output_root=tmp_path,
        ),
    )

    assert fallback_calls["count"] == 1
    assert any(warning.code == "native_enrichment_backend_missing" for warning in result.warnings)


def test_pipeline_native_enrichment_bad_library(monkeypatch, tmp_path, experiment_config):
    monkeypatch.setattr(
        native_enrichment,
        "run_enrichment_native",
        lambda *args, **kwargs: (_ for _ in ()).throw(DataContractError("library foo missing")),
    )
    fallback_calls = {"count": 0}

    def _fake_enrichr(genes, libraries, cutoff):
        fallback_calls["count"] += 1
        return []

    monkeypatch.setattr("crispr_screen_expert.pipeline.run_enrichr", _fake_enrichr)

    result = run_analysis(
        config=experiment_config,
        paths=DataPaths(
            counts=Path("sample_data/demo_counts.csv"),
            library=Path("sample_data/demo_library.csv"),
        ),
        settings=PipelineSettings(
            use_mageck=False,
            use_native_rra=False,
            use_native_enrichment=True,
            enrichr_libraries=["custom"],
            output_root=tmp_path,
        ),
    )

    assert fallback_calls["count"] == 1
    assert any(warning.code == "native_enrichment_library_missing" for warning in result.warnings)
