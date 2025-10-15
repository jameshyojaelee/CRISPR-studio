"""Normalization and replicate handling utilities for CRISPR-studio."""

from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd

from .exceptions import DataContractError
from .models import ExperimentConfig, ScreenType

AggregationMethod = Literal["median", "mean"]


def normalize_counts_cpm(counts: pd.DataFrame, pseudo_count: float = 1.0) -> pd.DataFrame:
    """Normalize counts to counts-per-million (CPM) scale with pseudo-count."""
    if counts.empty:
        raise DataContractError("Counts matrix is empty; cannot normalize.")

    adjusted = counts + pseudo_count
    library_sizes = adjusted.sum(axis=0)
    if (library_sizes == 0).any():
        raise DataContractError("Encountered zero total counts for a sample; CPM undefined.")

    cpm = adjusted.divide(library_sizes, axis=1) * 1_000_000
    return cpm


def aggregate_replicates(
    counts: pd.DataFrame,
    metadata: ExperimentConfig,
    method: AggregationMethod = "median",
) -> pd.DataFrame:
    """Aggregate replicate columns per experimental condition."""
    if method not in {"median", "mean"}:
        raise ValueError("Unsupported aggregation method. Use 'median' or 'mean'.")

    condition_order: list[str] = []
    for sample in metadata.samples:
        if sample.condition not in condition_order:
            condition_order.append(sample.condition)

    aggregated_series = {}
    for condition in condition_order:
        condition_cols = [s.file_column for s in metadata.samples if s.condition == condition]
        missing_cols = [col for col in condition_cols if col not in counts.columns]
        if missing_cols:
            raise DataContractError(
                f"Counts matrix missing columns needed for condition '{condition}': {', '.join(missing_cols)}"
            )
        condition_counts = counts[condition_cols]
        if condition_counts.shape[1] == 1:
            aggregated_series[condition] = condition_counts.iloc[:, 0]
        elif method == "median":
            aggregated_series[condition] = condition_counts.median(axis=1)
        else:
            aggregated_series[condition] = condition_counts.mean(axis=1)

    aggregated_df = pd.DataFrame(aggregated_series)
    return aggregated_df


def compute_log2_fold_change(
    normalized_counts: pd.DataFrame,
    metadata: ExperimentConfig,
    pseudo_count: float = 1.0,
) -> pd.Series:
    """Compute per-guide log2 fold-change between treatment and control conditions."""
    control_cols = [s.file_column for s in metadata.control_samples]
    treatment_cols = [s.file_column for s in metadata.treatment_samples]

    if not control_cols or not treatment_cols:
        raise DataContractError("Both control and treatment conditions are required for fold-change computation.")

    missing_control = [col for col in control_cols if col not in normalized_counts.columns]
    missing_treatment = [col for col in treatment_cols if col not in normalized_counts.columns]
    missing = missing_control + missing_treatment
    if missing:
        raise DataContractError(
            f"Normalized counts missing expected sample columns: {', '.join(sorted(missing))}"
        )

    control_values = normalized_counts[control_cols].mean(axis=1)
    treatment_values = normalized_counts[treatment_cols].mean(axis=1)

    ratio = (treatment_values + pseudo_count) / (control_values + pseudo_count)
    log2fc = np.log2(ratio)

    if metadata.screen_type == ScreenType.DROPOUT:
        # For dropout screens, depletions should be positive values for downstream prioritization.
        log2fc = -log2fc

    return log2fc.rename("log2_fold_change")


def compute_gene_stats(log2fc: pd.Series, library: pd.DataFrame) -> pd.DataFrame:
    """Aggregate guide-level log2 fold-change into gene statistics."""
    if log2fc.empty:
        raise DataContractError("Log2 fold-change series is empty.")

    merged = library.set_index("guide_id").join(log2fc, how="inner")
    if merged.empty:
        raise DataContractError("No overlapping guides between log2 fold-change values and library.")

    weights = merged.get("weight", pd.Series(1.0, index=merged.index))
    weights = weights.clip(lower=0)
    weight_sum = weights.groupby(merged["gene_symbol"]).sum()

    weighted_sum = (merged["log2_fold_change"] * weights).groupby(merged["gene_symbol"]).sum()
    mean = weighted_sum / weight_sum

    grouped = merged.groupby("gene_symbol")["log2_fold_change"]
    median = grouped.median()
    variance = grouped.var(ddof=0)
    guide_count = grouped.size()

    stats = pd.DataFrame(
        {
            "mean_log2fc": mean,
            "median_log2fc": median,
            "variance_log2fc": variance.fillna(0.0),
            "n_guides": guide_count,
        }
    )
    return stats.sort_index()
