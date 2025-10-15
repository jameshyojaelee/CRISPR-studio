"""Plotly visualization utilities for CRISPR-studio."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def volcano_plot(
    gene_df: pd.DataFrame,
    lfc_column: str = "median_log2fc",
    fdr_column: str = "fdr",
    top_genes: int = 10,
    significance_threshold: float = 0.1,
) -> go.Figure:
    """Create a volcano plot highlighting significant genes."""
    if lfc_column not in gene_df.columns:
        if "mean_log2fc" in gene_df.columns:
            lfc_column = "mean_log2fc"
        elif "log2fc" in gene_df.columns:
            lfc_column = "log2fc"
        else:
            raise ValueError("Unable to locate log2 fold-change column for volcano plot.")

    if fdr_column not in gene_df.columns:
        raise ValueError("Volcano plot requires an FDR column.")

    df = gene_df.copy()
    df["-log10_fdr"] = -np.log10(df[fdr_column].replace(0, np.nan))
    df["is_significant"] = df[fdr_column] <= significance_threshold

    fig = px.scatter(
        df,
        x=lfc_column,
        y="-log10_fdr",
        color="is_significant",
        hover_data={"gene": True, fdr_column: True, lfc_column: True},
        labels={lfc_column: "log2 fold-change", "-log10_fdr": "-log10(FDR)", "is_significant": "Significant"},
    )

    top_labels = df.sort_values(fdr_column).head(top_genes)
    for _, row in top_labels.iterrows():
        fig.add_annotation(
            x=row[lfc_column],
            y=row["-log10_fdr"],
            text=row.get("gene") or row.get("gene_symbol"),
            showarrow=True,
            arrowhead=2,
            ax=0,
            ay=-20,
        )

    fig.update_layout(title="Volcano Plot", legend_title="Significant")
    fig.update_traces(marker=dict(size=8, line=dict(width=0)))
    return fig


def replicate_correlation_scatter(
    counts: pd.DataFrame,
    sample_a: str,
    sample_b: str,
) -> go.Figure:
    """Scatter plot comparing guide counts between two replicates."""
    if sample_a not in counts.columns or sample_b not in counts.columns:
        raise ValueError("Requested replicate columns missing from counts matrix.")

    df = counts[[sample_a, sample_b]].copy()
    df = np.log2(df + 1)

    fig = px.scatter(
        df,
        x=sample_a,
        y=sample_b,
        labels={sample_a: f"log2 counts {sample_a}", sample_b: f"log2 counts {sample_b}"},
        opacity=0.6,
    )
    fig.add_trace(
        go.Scatter(
            x=[df[sample_a].min(), df[sample_a].max()],
            y=[df[sample_a].min(), df[sample_a].max()],
            mode="lines",
            line=dict(color="black", dash="dash"),
            showlegend=False,
        )
    )
    fig.update_layout(title=f"Replicate Correlation: {sample_a} vs {sample_b}")
    return fig


def guide_coverage_bar(library: pd.DataFrame, counts: pd.DataFrame) -> go.Figure:
    """Bar chart showing number of detected guides per gene."""
    merged = library.set_index("guide_id").join((counts > 0).sum(axis=1).rename("detected"))
    coverage = merged.groupby("gene_symbol")["detected"].sum().sort_values(ascending=False)

    fig = px.bar(
        coverage,
        labels={"index": "Gene", "value": "Detected guides"},
        title="Guide Detection per Gene",
    )
    return fig


def pathway_enrichment_bubble(pathways: Iterable[dict], max_bubbles: int = 20) -> go.Figure:
    """Bubble chart summarizing pathway enrichment results."""
    df = pd.DataFrame(pathways)
    if df.empty:
        fig = go.Figure()
        fig.update_layout(title="No pathway enrichment results")
        return fig

    df = df.sort_values("fdr").head(max_bubbles)
    df["-log10_fdr"] = -np.log10(df["fdr"].replace(0, np.nan))
    df["gene_count"] = df["genes"].apply(lambda genes: len(genes) if isinstance(genes, list) else 0)

    fig = px.scatter(
        df,
        x="-log10_fdr",
        y="name",
        size="gene_count",
        color="source",
        hover_data={"fdr": True, "gene_count": True, "pathway_id": True},
        labels={"-log10_fdr": "-log10(FDR)", "name": "Pathway"},
    )
    fig.update_layout(title="Pathway Enrichment")
    return fig


def detection_heatmap(counts: pd.DataFrame, min_count: int = 10) -> go.Figure:
    """Heatmap of guide detection (above threshold) across samples."""
    detection = (counts >= min_count).astype(int)
    fig = px.imshow(
        detection,
        color_continuous_scale="Viridis",
        aspect="auto",
        labels=dict(x="Sample", y="sgRNA", color=f"Count ≥ {min_count}"),
        title="Guide Detection Heatmap",
    )
    return fig
