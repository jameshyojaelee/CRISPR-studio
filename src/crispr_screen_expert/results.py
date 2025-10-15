"""Utilities for assembling analysis results into domain models."""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd

from .models import (
    AnalysisResult,
    AnalysisSummary,
    ExperimentConfig,
    GeneResult,
    GuideRecord,
    NarrativeSnippet,
    PathwayResult,
    QCMetric,
    ScoringMethod,
    ScreenType,
)


def _maybe_float(value: object) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (float, int)):
        if isinstance(value, (float, np.floating)) and np.isnan(value):
            return None
        return float(value)
    if isinstance(value, str):
        try:
            numeric = float(value)
        except ValueError:
            return None
        return None if np.isnan(numeric) else numeric
    return None


def build_analysis_summary(
    total_guides: int,
    total_genes: int,
    significant_genes: int,
    screen_type: ScreenType,
    scoring_method: ScoringMethod,
    runtime_seconds: Optional[float] = None,
    notes: Optional[Iterable[str]] = None,
) -> AnalysisSummary:
    """Create an AnalysisSummary model from primitive values."""
    return AnalysisSummary(
        total_guides=int(total_guides),
        total_genes=int(total_genes),
        significant_genes=int(significant_genes),
        runtime_seconds=_maybe_float(runtime_seconds),
        screen_type=screen_type,
        scoring_method=scoring_method,
        notes=list(notes or []),
    )


def dataframe_to_gene_results(
    gene_df: pd.DataFrame,
    fdr_threshold: float,
    guide_lookup: Optional[Dict[str, List[GuideRecord]]] = None,
) -> List[GeneResult]:
    """Convert a gene-level dataframe into a list of GeneResult models."""
    if "gene" in gene_df.columns:
        symbol_column = "gene"
    elif "gene_symbol" in gene_df.columns:
        symbol_column = "gene_symbol"
    else:
        raise ValueError("gene_df must contain a 'gene' or 'gene_symbol' column.")

    results: List[GeneResult] = []
    for row in gene_df.itertuples(index=False):
        symbol = getattr(row, symbol_column)
        score = _maybe_float(getattr(row, "score", None))
        log2fc = _maybe_float(
            getattr(row, "log2fc", None)
            if hasattr(row, "log2fc")
            else (
                getattr(row, "median_log2fc", None)
                if hasattr(row, "median_log2fc")
                else getattr(row, "mean_log2fc", None)
            )
        )
        p_value = _maybe_float(getattr(row, "p_value", None))
        fdr_value = _maybe_float(getattr(row, "fdr", None))
        rank_val = getattr(row, "rank", None)
        rank = int(rank_val) if rank_val is not None and not pd.isna(rank_val) else None
        n_guides = int(getattr(row, "n_guides", 0)) if hasattr(row, "n_guides") else 0

        result = GeneResult(
            gene_symbol=str(symbol),
            score=score,
            log2_fold_change=log2fc,
            p_value=p_value,
            fdr=fdr_value,
            rank=rank,
            n_guides=n_guides,
            guides=guide_lookup.get(symbol, []) if guide_lookup else [],
            is_significant=fdr_value is not None and fdr_value <= fdr_threshold,
        )
        results.append(result)
    return results


def select_top_hits(gene_df: pd.DataFrame, fdr_threshold: float, limit: int = 20) -> pd.DataFrame:
    """Return a filtered DataFrame of the top significant genes."""
    if "fdr" not in gene_df.columns:
        raise ValueError("gene_df must include 'fdr' column to select top hits.")

    filtered = gene_df[(gene_df["fdr"].notna()) & (gene_df["fdr"] <= fdr_threshold)]
    filtered = filtered.sort_values("fdr", kind="mergesort")
    return filtered.head(limit)


def prepare_volcano_payload(
    gene_df: pd.DataFrame,
    lfc_column: str = "median_log2fc",
    score_column: str = "score",
    significance_column: str = "fdr",
    significance_threshold: float = 0.1,
) -> Dict[str, List[object]]:
    """Build a payload for Plotly volcano plot rendering."""
    if lfc_column not in gene_df.columns:
        if "mean_log2fc" in gene_df.columns:
            lfc_column = "mean_log2fc"
        elif "log2fc" in gene_df.columns:
            lfc_column = "log2fc"
        else:
            raise ValueError("Unable to locate a log2 fold-change column for volcano plot.")

    y_values = -np.log10(gene_df[score_column].replace({0: np.nan})) if score_column in gene_df.columns else None
    if y_values is None or y_values.isna().all():
        # Fall back to inverse FDR if score absent.
        y_values = -np.log10(gene_df[significance_column].replace({0: np.nan}))

    payload: Dict[str, List[object]] = {
        "x": gene_df[lfc_column].tolist(),
        "y": y_values.tolist(),
        "labels": gene_df["gene"].tolist() if "gene" in gene_df.columns else gene_df["gene_symbol"].tolist(),
        "is_significant": (
            gene_df[significance_column] <= significance_threshold
            if significance_column in gene_df.columns
            else pd.Series([False] * gene_df.shape[0])
        ).tolist(),
    }
    return payload


ConditionStat = Dict[str, float | None | str]


def compute_condition_statistics(
    counts: pd.DataFrame,
    metadata: ExperimentConfig,
) -> List[ConditionStat]:
    """Summarize per-condition library size statistics."""
    stats: List[ConditionStat] = []
    for condition in metadata.control_conditions + metadata.treatment_conditions:
        columns = [s.file_column for s in metadata.samples if s.condition == condition]
        if not columns:
            continue
        subset = counts[columns]
        total = subset.sum(axis=0)
        stats.append(
            {
                "condition": condition,
                "mean": float(total.mean()) if not total.empty else None,
                "median": float(total.median()) if not total.empty else None,
                "min": float(total.min()) if not total.empty else None,
                "max": float(total.max()) if not total.empty else None,
            }
        )
    return stats


def merge_gene_results(
    config: ExperimentConfig,
    summary: AnalysisSummary,
    gene_df: pd.DataFrame,
    qc_metrics: List[QCMetric],
    narratives: List[NarrativeSnippet],
    pathway_results: Optional[List[PathwayResult]] = None,
    guide_lookup: Optional[Dict[str, List[GuideRecord]]] = None,
    artifacts: Optional[Dict[str, str]] = None,
    warnings: Optional[List[str]] = None,
) -> AnalysisResult:
    """Assemble all components into an AnalysisResult instance."""
    gene_results = dataframe_to_gene_results(
        gene_df,
        fdr_threshold=config.analysis.fdr_threshold,
        guide_lookup=guide_lookup,
    )

    significant_count = sum(g.is_significant for g in gene_results)
    summary.significant_genes = significant_count

    return AnalysisResult(
        config=config,
        summary=summary,
        gene_results=gene_results,
        qc_metrics=qc_metrics,
        qc_flags=[],
        pathway_results=pathway_results or [],
        narratives=narratives,
        artifacts=artifacts or {},
        warnings=warnings or [],
    )
