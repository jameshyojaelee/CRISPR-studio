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


def test_pipeline_demo_warns_and_dedupes(tmp_path, monkeypatch):
    events: list[tuple[str, dict]] = []
    monkeypatch.setattr("crispr_screen_expert.pipeline.log_event", lambda name, payload=None: events.append((name, payload or {})))
    monkeypatch.setattr("crispr_screen_expert.native.rra.is_available", lambda: False)
    monkeypatch.setattr(
        "crispr_screen_expert.pipeline.fetch_gene_annotations",
        lambda genes: ({}, ["batch 1 timeout", "batch 1 timeout", "batch 2 partial"]),
    )

    result = run_analysis(
        config=None,
        paths=DataPaths(
            counts=Path("sample_data/demo_counts.csv"),
            library=Path("sample_data/demo_library.csv"),
            metadata=Path("sample_data/demo_metadata.json"),
        ),
        settings=PipelineSettings(use_mageck=False, use_native_rra=True, output_root=tmp_path, enrichr_libraries=[]),
    )

    warning_messages = [(warning.code, warning.message) for warning in result.warnings]
    expected_messages = [
        (
            "native_rra_unavailable",
            "Native RRA requested but backend not available; falling back to Python implementation.",
        ),
        ("annotations_warning", "batch 1 timeout"),
        ("annotations_warning", "batch 2 partial"),
    ]
    assert warning_messages == expected_messages

    completed_payloads = [payload for name, payload in events if name == "analysis_completed"]
    assert completed_payloads, "analysis_completed event not logged"
    event_names = [name for name, _ in events]
    assert event_names and event_names[0] == "analysis_started"
    payload_warnings = completed_payloads[-1]["warnings"]
    assert [warning.get("message") for warning in payload_warnings] == [message for _, message in expected_messages]
