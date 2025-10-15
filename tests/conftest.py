from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd
import pytest

from crispr_screen_expert.models import ExperimentConfig, load_experiment_config


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return Path("sample_data").resolve()


@pytest.fixture(scope="session")
def counts_path(data_dir: Path) -> Path:
    return data_dir / "demo_counts.csv"


@pytest.fixture(scope="session")
def library_path(data_dir: Path) -> Path:
    return data_dir / "demo_library.csv"


@pytest.fixture(scope="session")
def metadata_path(data_dir: Path) -> Path:
    return data_dir / "demo_metadata.json"


@pytest.fixture(scope="session")
def experiment_config(metadata_path: Path) -> ExperimentConfig:
    return load_experiment_config(metadata_path)


@pytest.fixture()
def counts_df(counts_path: Path) -> pd.DataFrame:
    from crispr_screen_expert.data_loader import load_counts

    return load_counts(counts_path)


@pytest.fixture()
def library_df(library_path: Path) -> pd.DataFrame:
    from crispr_screen_expert.data_loader import load_library

    return load_library(library_path)
