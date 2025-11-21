from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_dataset import validate_dataset


def _write_counts(path: Path, header: str, rows: list[str]) -> None:
    path.write_text("\n".join([header, *rows]))


def _write_library(path: Path, rows: list[str]) -> None:
    path.write_text("\n".join(["guide_id,gene_symbol,weight", *rows]))


def _write_metadata(path: Path, samples: list[dict]) -> None:
    payload = {"experiment_name": "demo", "screen_type": "dropout", "samples": samples}
    path.write_text(json.dumps(payload, indent=2))


def test_validate_dataset_happy_path(tmp_path: Path):
    counts = tmp_path / "counts.csv"
    _write_counts(
        counts,
        "guide_id,CTRL_1,TREAT_1",
        ["G1,100,50", "G2,120,40"],
    )

    library = tmp_path / "library.csv"
    _write_library(library, ["G1,GENE1,1.0", "G2,GENE2,1.0"])

    metadata = tmp_path / "metadata.json"
    _write_metadata(
        metadata,
        [
            {"sample_id": "CTRL_1", "condition": "control", "replicate": "1", "role": "control", "file_column": "CTRL_1"},
            {"sample_id": "TREAT_1", "condition": "treatment", "replicate": "1", "role": "treatment", "file_column": "TREAT_1"},
        ],
    )

    manifest_path = tmp_path / "manifest.json"
    result = validate_dataset(
        counts_path=counts,
        library_path=library,
        metadata_path=metadata,
        skip_annotations=True,
        export_samples=manifest_path,
    )

    assert "error" not in result
    assert result["counts_shape"] == (2, 2)
    assert manifest_path.exists()


def test_validate_dataset_requires_guide_id(tmp_path: Path):
    counts = tmp_path / "counts.csv"
    _write_counts(counts, "sgRNA,CTRL_1", ["G1,10"])
    library = tmp_path / "library.csv"
    _write_library(library, ["G1,GENE1,1.0"])
    metadata = tmp_path / "metadata.json"
    _write_metadata(
        metadata,
        [{"sample_id": "CTRL_1", "condition": "control", "replicate": "1", "role": "control", "file_column": "CTRL_1"}],
    )

    result = validate_dataset(counts_path=counts, library_path=library, metadata_path=metadata)
    assert "error" in result
    assert "guide_id" in result["error"]


def test_validate_dataset_catches_duplicate_columns(tmp_path: Path):
    counts = tmp_path / "counts.csv"
    _write_counts(counts, "guide_id,CTRL,CTRL", ["G1,10,11"])
    library = tmp_path / "library.csv"
    _write_library(library, ["G1,GENE1,1.0"])
    metadata = tmp_path / "metadata.json"
    _write_metadata(
        metadata,
        [{"sample_id": "CTRL", "condition": "control", "replicate": "1", "role": "control", "file_column": "CTRL"}],
    )

    result = validate_dataset(counts_path=counts, library_path=library, metadata_path=metadata)
    assert "error" in result
    assert "duplicate sample columns" in result["error"]


def test_validate_dataset_invalid_metadata(tmp_path: Path):
    counts = tmp_path / "counts.csv"
    _write_counts(counts, "guide_id,CTRL_1,TREAT_1", ["G1,10,5"])
    library = tmp_path / "library.csv"
    _write_library(library, ["G1,GENE1,1.0"])
    metadata = tmp_path / "metadata.json"
    # Missing treatment sample -> validation should fail.
    _write_metadata(
        metadata,
        [{"sample_id": "CTRL_1", "condition": "control", "replicate": "1", "role": "control", "file_column": "CTRL_1"}],
    )

    result = validate_dataset(counts_path=counts, library_path=library, metadata_path=metadata)
    assert "error" in result
    assert "treatment" in result["error"].lower()
