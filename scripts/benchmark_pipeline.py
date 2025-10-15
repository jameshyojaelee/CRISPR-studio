#!/usr/bin/env python3
"""Benchmark CRISPR-studio pipeline on the demo dataset."""

from __future__ import annotations

import time
from pathlib import Path

from crispr_screen_expert.models import load_experiment_config
from crispr_screen_expert.pipeline import DataPaths, PipelineSettings, run_analysis


def main() -> None:
    config = load_experiment_config(Path("sample_data/demo_metadata.json"))
    start = time.time()
    run_analysis(
        config=config,
        paths=DataPaths(
            counts=Path("sample_data/demo_counts.csv"),
            library=Path("sample_data/demo_library.csv"),
            metadata=Path("sample_data/demo_metadata.json"),
        ),
        settings=PipelineSettings(use_mageck=False),
    )
    duration = time.time() - start
    print(f"Pipeline completed in {duration:.2f} seconds")


if __name__ == "__main__":
    main()
