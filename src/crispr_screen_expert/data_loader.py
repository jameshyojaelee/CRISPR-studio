"""Data loading utilities for CRISPR-studio."""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import pandas as pd
from pandas.errors import ParserError

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


def _format_offending_values(values: Iterable[tuple[str, object]], *, max_items: int = 5) -> str:
    collected = list(values)
    formatted = []
    for idx, value in collected[:max_items]:
        formatted.append(f"{idx}={value!r}")
    remaining = max(0, len(collected) - max_items)
    if remaining > 0:
        formatted.append(f"...(+{remaining} more)")
    return ", ".join(formatted)


def load_counts(path: Path) -> pd.DataFrame:
    """Load sgRNA count matrix with guides as index and samples as columns."""
    if not path.exists():
        raise DataContractError(f"Counts file not found: {path}")

    delimiter = _detect_delimiter(path)
    try:
        df = pd.read_csv(path, sep=delimiter, dtype={"guide_id": str}, comment="#")
    except ParserError as exc:
        details = exc.args[0] if exc.args else str(exc)
        raise DataContractError(f"Counts file appears malformed ({details}).") from exc
    except Exception as exc:
        raise DataContractError(f"Failed to parse counts file {path}: {exc}") from exc

    if "guide_id" not in df.columns:
        raise DataContractError("Counts file must include a 'guide_id' column.")

    duplicate_columns = [col for col in df.columns[df.columns.duplicated()] if col != "guide_id"]
    if duplicate_columns:
        dup_list = ", ".join(sorted(set(duplicate_columns)))
        raise DataContractError(f"Counts file contains duplicate sample columns: {dup_list}")

    if df["guide_id"].duplicated().any():
        raise DataContractError("Duplicate guide_id entries detected in counts file.")

    counts_df = df.set_index("guide_id")

    # Coerce values to integer dtype, reporting any failures with context.
    for column in counts_df.columns:
        column_series = counts_df[column]
        coerced = pd.to_numeric(column_series, errors="coerce")
        invalid_mask = coerced.isna() & column_series.notna()
        if invalid_mask.any():
            offenders = list(zip(column_series[invalid_mask].index.tolist(), column_series[invalid_mask].tolist()))
            sample = _format_offending_values(offenders)
            raise DataContractError(
                f"Counts column '{column}' contains non-numeric values at guides: {sample}"
            )

        fractional = coerced[~coerced.isna()] % 1 != 0
        if fractional.any():
            offenders = list(zip(fractional[fractional].index.tolist(), column_series[fractional].tolist()))
            sample = _format_offending_values(offenders)
            raise DataContractError(
                f"Counts column '{column}' contains non-integer values at guides: {sample}"
            )

        counts_df[column] = coerced.astype("int64")

    if (counts_df < 0).any().any():
        raise DataContractError("Counts matrix contains negative values.")

    return counts_df


def load_library(path: Path) -> pd.DataFrame:
    """Load library annotation ensuring unique guide IDs."""
    if not path.exists():
        raise DataContractError(f"Library file not found: {path}")

    try:
        df = pd.read_csv(path, dtype={"guide_id": str, "gene_symbol": str}, comment="#")
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
