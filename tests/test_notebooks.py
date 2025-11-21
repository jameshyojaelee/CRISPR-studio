from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

NOTEBOOK_PATH = Path(__file__).resolve().parents[1] / "notebooks" / "quickstart.ipynb"


def test_quickstart_notebook_exists():
    assert NOTEBOOK_PATH.exists()


@pytest.mark.skipif(os.environ.get("CI", "").lower() == "true", reason="Skip notebook execution on CI")
def test_quickstart_notebook_executes():
    if sys.version_info < (3, 11):
        pytest.skip("Notebook execution test requires Python 3.11+")

    nbformat = pytest.importorskip("nbformat")
    nbconvert = pytest.importorskip("nbconvert")

    with NOTEBOOK_PATH.open("r", encoding="utf-8") as handle:
        nb = nbformat.read(handle, as_version=4)

    executor = nbconvert.preprocessors.ExecutePreprocessor(timeout=300, kernel_name="python3")
    executor.preprocess(nb, {"metadata": {"path": str(NOTEBOOK_PATH.parent)}})
