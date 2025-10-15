"""Pathway enrichment utilities for CRISPR-studio."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional, Sequence

import gseapy as gp
import pandas as pd

from .models import PathwayResult

logger = logging.getLogger(__name__)


def _prepare_gene_list(genes: Sequence[str]) -> List[str]:
    unique = []
    seen = set()
    for symbol in genes:
        upper = symbol.upper()
        if upper not in seen:
            unique.append(upper)
            seen.add(upper)
    return unique


def run_enrichr(
    genes: Sequence[str],
    libraries: Sequence[str],
    background: Optional[Sequence[str]] = None,
    cutoff: float = 0.1,
    cache_path: Optional[Path] = None,
) -> List[PathwayResult]:
    """Run Enrichr via gseapy to compute enrichment results."""
    if not genes:
        logger.info("No genes provided for enrichment; returning empty list.")
        return []

    gene_list = _prepare_gene_list(genes)
    try:
        enr = gp.enrichr(
            gene_list=gene_list,
            gene_sets=list(libraries),
            background=_prepare_gene_list(background) if background else None,
            outdir=None,
            cutoff=cutoff,
        )
    except Exception as exc:
        logger.warning("Enrichr enrichment failed: %s", exc)
        return []

    results: List[PathwayResult] = []
    if enr is None:
        return results

    def iter_results(result):
        if isinstance(result, pd.DataFrame):
            for _, row in result.iterrows():
                yield row.to_dict()
        elif isinstance(result, pd.Series):
            yield result.to_dict()
        else:
            logger.debug("Unexpected Enrichr result type: %s", type(result))

    for lib_name, result in enr.results.items():
        for row in iter_results(result):
            term = row.get("Term")
            if not term:
                continue
            fdr = row.get("Adjusted P-value")
            fdr = row.get("Adjusted P-value") or row.get("Adjusted P-value")
            overlap = row.get("Overlap", "")
            genes_overlap: List[str] = []
            if isinstance(overlap, str) and "/" in overlap:
                try:
                    _, genes_part = overlap.split("/", 1)
                    genes_overlap = [g.strip().upper() for g in genes_part.split(",") if g]
                except ValueError:
                    genes_overlap = []
            result = PathwayResult(
                pathway_id=f"{lib_name}:{term}",
                name=term,
                source=lib_name,
                enrichment_score=row.get("Combined Score"),
                p_value=row.get("P-value"),
                fdr=fdr,
                genes=genes_overlap,
                direction=None,
                description=None,
            )
            if result.fdr is None or result.fdr <= cutoff:
                results.append(result)

    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps([result.model_dump() for result in results], indent=2)
        )

    return results


def run_gsea(
    ranked_genes: pd.Series,
    gene_sets: str,
    permutations: int = 100,
    min_size: int = 5,
    max_size: int = 500,
    fdr_threshold: float = 0.1,
) -> List[PathwayResult]:
    """Run GSEA preranked analysis using gseapy."""
    ranked_genes = ranked_genes.dropna()
    if ranked_genes.empty:
        return []

    try:
        res = gp.prerank(
            rnk=ranked_genes.sort_values(ascending=False),
            gene_sets=gene_sets,
            min_size=min_size,
            max_size=max_size,
            permutation_num=permutations,
            outdir=None,
        )
    except Exception as exc:
        logger.warning("GSEA prerank failed: %s", exc)
        return []

    if res is None or res.res2d.empty:
        return []

    df = res.res2d
    records: List[PathwayResult] = []
    for _, row in df.iterrows():
        fdr = row.get("fdr") or row.get("FDR") or row.get("padj")
        if fdr is not None and fdr > fdr_threshold:
            continue
        leading_edge = [gene for gene in str(row.get("ledge_genes", "")).split(",") if gene]
        records.append(
            PathwayResult(
                pathway_id=row["Term"],
                name=row["Term"],
                source=gene_sets,
                enrichment_score=row.get("nes"),
                p_value=row.get("pval") or row.get("Pval"),
                fdr=fdr,
                genes=leading_edge,
                direction="up" if row.get("nes", 0) > 0 else "down",
                description=None,
            )
        )
    return records
