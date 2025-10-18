from __future__ import annotations

import pytest

from crispr_screen_expert.data_loader import load_counts, load_library, load_metadata
from crispr_screen_expert.exceptions import DataContractError


def test_load_counts_shape(counts_path):
    df = load_counts(counts_path)
    assert df.index.name == "guide_id"
    assert df.shape[1] == 4
    assert (df >= 0).all().all()


def test_load_library_uppercase(library_path):
    df = load_library(library_path)
    assert df["gene_symbol"].str.isupper().all()
    assert not df["guide_id"].duplicated().any()


def test_load_metadata_unique(metadata_path):
    config = load_metadata(metadata_path)
    assert config.screen_type.value == "dropout"
    ids = [sample.sample_id for sample in config.samples]
    assert len(ids) == len(set(ids))


def test_missing_guide_column_raises(tmp_path):
    bad_counts = tmp_path / "bad.csv"
    bad_counts.write_text("sgRNA,CTRL_A\nG1,100\n")
    with pytest.raises(DataContractError):
        load_counts(bad_counts)


def test_non_numeric_counts_error_includes_context(tmp_path):
    bad_counts = tmp_path / "bad_counts.csv"
    bad_counts.write_text("guide_id,CTRL_A\nG1,10\nG2,abc\n")
    with pytest.raises(DataContractError) as excinfo:
        load_counts(bad_counts)
    message = str(excinfo.value)
    assert "CTRL_A" in message
    assert "G2" in message


def test_non_integer_counts_error(tmp_path):
    bad_counts = tmp_path / "bad_counts_float.csv"
    bad_counts.write_text("guide_id,CTRL_A\nG1,5.5\n")
    with pytest.raises(DataContractError) as excinfo:
        load_counts(bad_counts)
    message = str(excinfo.value)
    assert "non-integer" in message


def test_malformed_csv_reports_line(tmp_path):
    malformed = tmp_path / "malformed.csv"
    malformed.write_text("guide_id,CTRL_A\nG1,10\nG2\n")
    with pytest.raises(DataContractError) as excinfo:
        load_counts(malformed)
    assert "malformed" in str(excinfo.value)
