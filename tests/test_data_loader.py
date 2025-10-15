from __future__ import annotations

import pandas as pd
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
