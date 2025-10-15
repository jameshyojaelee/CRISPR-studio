#!/usr/bin/env python3
"""Generate synthetic CRISPR-studio demo dataset.

Usage
-----
Create the default demo files in ``sample_data``:

    python scripts/generate_demo_dataset.py --output-dir sample_data --seed 42

Arguments
---------
``--output-dir`` (default: ``sample_data``)
    Directory where ``demo_counts.csv``, ``demo_library.csv`` and
    ``demo_metadata.json`` will be written. The directory is created if it
    does not exist.

``--seed`` (default: ``42``)
    Random seed for reproducibility.

``--guides-per-gene`` (default: ``3``)
    Number of guides to simulate per non-control gene.

``--ntc-guides`` (default: ``2``)
    Number of non-targeting control guides.

The generated dataset models a dropout viability screen (two control replicates
and two treatment replicates). DNA repair genes exhibit strong depletion under
drug treatment, while controls remain stable. The files adhere to the data
contract defined in ``docs/data_contract.md``.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

import numpy as np
import pandas as pd


CTRL_SAMPLES = ["CTRL_A", "CTRL_B"]
TREAT_SAMPLES = ["TREAT_A", "TREAT_B"]


@dataclass(frozen=True)
class GeneSpec:
    """Specification for a synthetic gene in the demo dataset."""

    symbol: str
    effect: str  # "strong_drop", "moderate_drop", or "neutral"


GENE_SPECS: List[GeneSpec] = [
    GeneSpec("BRCA2", "strong_drop"),
    GeneSpec("ATM", "strong_drop"),
    GeneSpec("TP53", "moderate_drop"),
    GeneSpec("RAD51", "moderate_drop"),
]


def _simulate_counts(
    rng: np.random.Generator,
    guides_per_gene: int,
    ntc_guides: int,
) -> pd.DataFrame:
    """Simulate count matrix for control and treatment samples."""

    rows: List[Dict[str, int]] = []

    def control_counts(mean: float, sd: float) -> np.ndarray:
        return np.clip(rng.normal(loc=mean, scale=sd, size=len(CTRL_SAMPLES)), a_min=0, a_max=None)

    def treatment_counts(effect: str) -> np.ndarray:
        if effect == "strong_drop":
            mean, sd = 7500, 900
        elif effect == "moderate_drop":
            mean, sd = 12000, 1100
        else:
            mean, sd = 23000, 1300
        return np.clip(rng.normal(loc=mean, scale=sd, size=len(TREAT_SAMPLES)), a_min=0, a_max=None)

    for spec in GENE_SPECS:
        for guide_idx in range(1, guides_per_gene + 1):
            guide_id = f"{spec.symbol}_G{guide_idx}"
            ctrl = control_counts(mean=23500, sd=1200).astype(int)
            treat = treatment_counts(spec.effect).astype(int)
            row = {
                "guide_id": guide_id,
                CTRL_SAMPLES[0]: ctrl[0],
                CTRL_SAMPLES[1]: ctrl[1],
                TREAT_SAMPLES[0]: treat[0],
                TREAT_SAMPLES[1]: treat[1],
            }
            rows.append(row)

    for guide_idx in range(1, ntc_guides + 1):
        guide_id = f"NTC_G{guide_idx}"
        ctrl = control_counts(mean=24500, sd=1000).astype(int)
        treat = np.clip(
            rng.normal(loc=24200, scale=900, size=len(TREAT_SAMPLES)),
            a_min=0,
            a_max=None,
        ).astype(int)
        rows.append(
            {
                "guide_id": guide_id,
                CTRL_SAMPLES[0]: ctrl[0],
                CTRL_SAMPLES[1]: ctrl[1],
                TREAT_SAMPLES[0]: treat[0],
                TREAT_SAMPLES[1]: treat[1],
            }
        )

    counts_df = pd.DataFrame(rows)
    return counts_df


def _build_library(counts_df: pd.DataFrame) -> pd.DataFrame:
    """Create sgRNA library annotations with weights."""
    library_rows: List[Dict[str, str]] = []
    for guide_id in counts_df["guide_id"]:
        if guide_id.startswith("NTC"):
            gene_symbol = "NTC"
        else:
            gene_symbol = guide_id.split("_")[0]
        library_rows.append({"guide_id": guide_id, "gene_symbol": gene_symbol, "weight": 1.0})
    return pd.DataFrame(library_rows)


def _build_metadata() -> Dict[str, object]:
    """Return experiment metadata aligned with the demo dataset."""
    samples: List[Dict[str, str]] = []
    for sample_id in CTRL_SAMPLES:
        samples.append(
            {
                "sample_id": sample_id,
                "column": sample_id,
                "condition": "control",
                "replicate": sample_id.split("_")[1],
                "role": "control",
            }
        )
    for sample_id in TREAT_SAMPLES:
        samples.append(
            {
                "sample_id": sample_id,
                "column": sample_id,
                "condition": "treatment",
                "replicate": sample_id.split("_")[1],
                "role": "treatment",
            }
        )

    return {
        "experiment_name": "Demo Dropout Screen",
        "library_name": "Synthetic DNA Repair Panel",
        "screen_type": "dropout",
        "fdr_threshold": 0.1,
        "samples": samples,
        "analysis": {
            "scoring_method": "mageck",
            "enable_pathway": True,
            "enable_llm": False,
            "min_count_threshold": 10,
        },
    }


def write_outputs(output_dir: Path, counts_df: pd.DataFrame) -> None:
    """Persist counts, library, and metadata artifacts."""
    output_dir.mkdir(parents=True, exist_ok=True)

    counts_path = output_dir / "demo_counts.csv"
    counts_df.to_csv(counts_path, index=False)

    library_df = _build_library(counts_df)
    library_df.to_csv(output_dir / "demo_library.csv", index=False)

    metadata = _build_metadata()
    metadata_path = output_dir / "demo_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Generate synthetic CRISPR-studio demo dataset.")
    parser.add_argument("--output-dir", type=Path, default=Path("sample_data"))
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--guides-per-gene", type=int, default=3)
    parser.add_argument("--ntc-guides", type=int, default=2)
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    """Entry point for CLI execution."""
    args = parse_args(argv)
    if args.guides_per_gene < 1:
        raise ValueError("guides-per-gene must be >= 1")
    if args.ntc_guides < 1:
        raise ValueError("ntc-guides must be >= 1")

    rng = np.random.default_rng(seed=args.seed)
    counts_df = _simulate_counts(rng, guides_per_gene=args.guides_per_gene, ntc_guides=args.ntc_guides)

    write_outputs(args.output_dir, counts_df)
    print(f"Synthetic dataset written to {args.output_dir.resolve()}")


if __name__ == "__main__":
    main()
