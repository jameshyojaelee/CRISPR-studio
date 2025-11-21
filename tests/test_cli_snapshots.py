from __future__ import annotations

from pathlib import Path
import re

import pytest

from crispr_screen_expert.cli import run_pipeline


def _normalize_output(output: str, run_dir: Path) -> str:
    normalized = output.replace(str(run_dir), "<RUN_DIR>")
    normalized = re.sub(r'"runtime_seconds":\s*[-0-9.]+', '"runtime_seconds": 0', normalized)
    return normalized.strip()


def _run_cli(
    use_mageck: bool,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    run_dir = tmp_path / ("cli_mageck_on" if use_mageck else "cli_mageck_off")
    run_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("crispr_screen_expert.pipeline._ensure_output_dir", lambda _root: run_dir)
    monkeypatch.setattr("crispr_screen_expert.pipeline.time.time", lambda: 1000.0)
    monkeypatch.setattr("crispr_screen_expert.pipeline.log_event", lambda *args, **kwargs: None)

    run_pipeline(
        counts=Path("sample_data/demo_counts.csv"),
        library=Path("sample_data/demo_library.csv"),
        metadata=Path("sample_data/demo_metadata.json"),
        output_root=run_dir,
        use_mageck=use_mageck,
        use_native_rra=False,
        use_native_enrichment=False,
        enrichr=None,
        enable_llm=False,
        narrative_model=None,
        narrative_temperature=0.2,
        skip_annotations=True,
    )

    captured = capsys.readouterr().out
    return _normalize_output(captured, run_dir)


def test_cli_snapshot_mageck_off(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch):
    output = _run_cli(False, tmp_path, capsys, monkeypatch)
    snapshot = Path("tests/snapshots/cli_mageck_off.txt").read_text().strip()
    assert output == snapshot


def test_cli_snapshot_mageck_on(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch):
    output = _run_cli(True, tmp_path, capsys, monkeypatch)
    snapshot = Path("tests/snapshots/cli_mageck_on.txt").read_text().strip()
    assert output == snapshot
