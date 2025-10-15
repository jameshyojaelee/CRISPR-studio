"""Data loading utilities for CRISPR-studio."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd

from .exceptions import DataContractError
from .models import ExperimentConfig, load_experiment_config


logger = logging.getLogger(__name__)


def _detect_delimiter(path: Path) -> str:
    """Attempt to detect delimiter from the first line."""
    with path.open("r", encoding="utf-8") as handle:
        sample = handle.readline()
    if "\t" in sample and "," in sample:
        # Fallback to csv.Sniffer when both are present.
        dialect = csv.Sniffer().sniff(sample)
        return dialect.delimiter
    if "\t" in sample:
        return "\t"
    return ","


def load_counts(path: Path) -> pd.DataFrame:
    """Load sgRNA count matrix with guides as index and samples as columns."""
    if not path.exists():
        raise DataContractError(f"Counts file not found: {path}")

    delimiter = _detect_delimiter(path)
    try:
        df = pd.read_csv(path, sep=delimiter, dtype={"guide_id": str})
    except Exception as exc:
        raise DataContractError(f"Failed to parse counts file {path}: {exc}") from exc

    if "guide_id" not in df.columns:
        raise DataContractError("Counts file must include a 'guide_id' column.")

    if df["guide_id"].duplicated().any():
        raise DataContractError("Duplicate guide_id entries detected in counts file.")

    counts_df = df.set_index("guide_id")

    # Coerce values to numeric, reporting any failures.
    for column in counts_df.columns:
        try:
            counts_df[column] = pd.to_numeric(counts_df[column], errors="raise")
        except Exception as exc:
            raise DataContractError(f"Counts column '{column}' contains non-numeric values: {exc}") from exc

    if (counts_df < 0).any().any():
        raise DataContractError("Counts matrix contains negative values.")

    return counts_df


def load_library(path: Path) -> pd.DataFrame:
    """Load library annotation ensuring unique guide IDs."""
    if not path.exists():
        raise DataContractError(f"Library file not found: {path}")

    try:
        df = pd.read_csv(path, dtype={"guide_id": str, "gene_symbol": str})
    except Exception as exc:
        raise DataContractError(f"Failed to parse library file {path}: {exc}") from exc

    required_cols = {"guide_id", "gene_symbol"}
    missing = required_cols - set(df.columns)
    if missing:
        raise DataContractError(f"Library file is missing required columns: {', '.join(sorted(missing))}")

    if df["guide_id"].duplicated().any():
        raise DataContractError("Duplicate guide_id entries detected in library file.")

    df["gene_symbol"] = df["gene_symbol"].str.upper()
    if "weight" not in df.columns:
        df["weight"] = 1.0
    else:
        df["weight"] = pd.to_numeric(df["weight"], errors="coerce").fillna(1.0)

    return df


def load_metadata(path: Path) -> ExperimentConfig:
    """Load experiment metadata JSON and validate using Pydantic models."""
    if not path.exists():
        raise DataContractError(f"Metadata file not found: {path}")

    try:
        return load_experiment_config(path)
    except ValueError as exc:
        raise DataContractError(str(exc)) from exc


def match_counts_to_library(
    counts: pd.DataFrame,
    library: pd.DataFrame,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Align counts to the library definitions.

    Returns
    -------
    aligned_counts : pd.DataFrame
        Counts filtered to guides present in the library, preserving original order.
    missing_guides : pd.DataFrame
        Rows describing guides absent from either source. Columns: ``guide_id`` and ``issue``.
    merged : pd.DataFrame
        Library rows joined with count values (guides as index).
    """
    library_guides = set(library["guide_id"])
    count_guides = set(counts.index)

    missing_entries: List[Dict[str, str]] = []

    missing_in_library = sorted(count_guides - library_guides)
    if missing_in_library:
        logger.warning(
            "Counts include %d guides that are not present in the library annotation. They will be dropped.",
            len(missing_in_library),
        )
        missing_entries.extend(
            {"guide_id": guide_id, "issue": "missing_in_library"} for guide_id in missing_in_library
        )

    missing_in_counts = sorted(library_guides - count_guides)
    if missing_in_counts:
        logger.warning(
            "Library includes %d guides that are absent from the counts matrix. "
            "Downstream analysis will treat their counts as NaN.",
            len(missing_in_counts),
        )
        missing_entries.extend(
            {"guide_id": guide_id, "issue": "missing_in_counts"} for guide_id in missing_in_counts
        )

    aligned_counts = counts.loc[[guide for guide in counts.index if guide in library_guides]]
    merged = library.set_index("guide_id").join(aligned_counts, how="left")

    missing_report = pd.DataFrame(missing_entries, columns=["guide_id", "issue"])

    return aligned_counts, missing_report, merged


def validate_metadata_against_counts(metadata: ExperimentConfig, counts: pd.DataFrame) -> None:
    """Ensure metadata sample columns exist in counts matrix."""
    missing_columns = [col for col in metadata.sample_columns if col not in counts.columns]
    if missing_columns:
        raise DataContractError(
            f"Counts matrix is missing sample columns referenced in metadata: {', '.join(missing_columns)}"
        )
