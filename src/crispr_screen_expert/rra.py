"""Robust Rank Aggregation (RRA) fallback implementation.

This module implements a simplified version of the MAGeCK RRA algorithm
described in Li et al., Genome Biology 2014 (doi:10.1186/s13059-014-0554-4).
It converts guide-level rankings into gene-level significance scores when
the external MAGeCK binary is unavailable.
"""

from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd
from scipy.stats import beta

from .exceptions import DataContractError


def _benjamini_hochberg(pvalues: np.ndarray) -> np.ndarray:
    """Perform Benjamini-Hochberg FDR correction."""
    n = pvalues.size
    order = np.argsort(pvalues)
    ranked = pvalues[order]
    adjusted = np.empty(n, dtype=float)
    cumulative = 1.0
    for i in range(n - 1, -1, -1):
        rank = i + 1
        value = ranked[i] * n / rank
        cumulative = min(cumulative, value)
        adjusted[i] = cumulative
    adjusted = np.clip(adjusted, 0.0, 1.0)
    result = np.empty(n, dtype=float)
    result[order] = adjusted
    return result


def _compute_rra_pvalue(ranks: np.ndarray, total_guides: int) -> float:
    """Compute RRA p-value using order statistics."""
    normalized = np.sort(ranks / total_guides)
    k = normalized.size
    # Compute minimal probability among order statistics Beta(i, n - i + 1).
    probs = [beta.cdf(normalized[i], i + 1, total_guides - i) for i in range(k)]
    return float(min(probs)) if probs else 1.0


def run_rra(
    log2fc: pd.Series,
    library: pd.DataFrame,
    guide_pvalues: Optional[pd.Series] = None,
    min_guides: int = 2,
    higher_is_better: bool = True,
) -> pd.DataFrame:
    """Execute RRA fallback using guide-level log2 fold-changes.

    Parameters
    ----------
    log2fc:
        Series indexed by guide identifiers containing log2 fold-change values.
    library:
        DataFrame with columns ``guide_id``, ``gene_symbol`` and optional ``weight``.
    guide_pvalues:
        Optional per-guide p-values (used to report descriptive statistics).
    min_guides:
        Minimum number of guides required per gene to compute scores.
    higher_is_better:
        If True, larger log2FC values indicate stronger hits; otherwise reversed.

    Returns
    -------
    pandas.DataFrame
        Columns: ``gene``, ``score``, ``p_value``, ``fdr``, ``rank``, ``n_guides``,
        ``mean_log2fc``, ``median_log2fc``, ``var_log2fc``.
    """
    if log2fc.empty:
        raise DataContractError("log2 fold-change series is empty.")

    if "guide_id" not in library.columns or "gene_symbol" not in library.columns:
        raise DataContractError("Library must include 'guide_id' and 'gene_symbol' columns.")

    library_df = library.set_index("guide_id")
    merged = library_df.join(log2fc.rename("log2fc"), how="inner")
    if merged.empty:
        raise DataContractError("No overlapping guides between log2 fold-change values and library.")

    if guide_pvalues is not None:
        merged = merged.join(guide_pvalues.rename("p_value"), how="left")

    if "weight" not in merged.columns:
        merged["weight"] = 1.0
    merged = merged.dropna(subset=["log2fc"])

    total_guides = merged.shape[0]
    if total_guides == 0:
        raise DataContractError("No valid guides available for RRA computation.")

    ascending = not higher_is_better
    merged["rank"] = merged["log2fc"].rank(method="average", ascending=ascending)

    grouped = merged.groupby("gene_symbol", sort=False)

    records = []
    for gene, frame in grouped:
        if frame.shape[0] < min_guides:
            continue

        ranks = frame["rank"].to_numpy()
        p_value = _compute_rra_pvalue(ranks, total_guides)
        score = -math.log10(p_value) if p_value > 0 else float("inf")

        weights = frame["weight"].to_numpy()
        log_values = frame["log2fc"].to_numpy()
        weight_sum = weights.sum()
        mean = float(np.average(log_values, weights=weights)) if weight_sum > 0 else float(np.mean(log_values))
        median = float(np.median(log_values))
        variance = float(np.var(log_values, ddof=0))

        records.append(
            {
                "gene": gene,
                "score": score,
                "p_value": p_value,
                "n_guides": int(frame.shape[0]),
                "mean_log2fc": mean,
                "median_log2fc": median,
                "var_log2fc": variance,
            }
        )

    if not records:
        raise DataContractError("No genes met the minimum guide requirement for RRA.")

    result = pd.DataFrame.from_records(records)
    result = result.sort_values("p_value", kind="mergesort")

    fdr = _benjamini_hochberg(result["p_value"].to_numpy())
    result["fdr"] = fdr
    result["rank"] = np.arange(1, result.shape[0] + 1, dtype=int)

    return result.reset_index(drop=True)
