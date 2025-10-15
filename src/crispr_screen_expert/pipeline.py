"""Pipeline orchestrator for CRISPR-studio."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

import pandas as pd

from .annotations import fetch_gene_annotations
from .data_loader import load_counts, load_library, load_metadata, match_counts_to_library
from .enrichment import run_enrichr
from .exceptions import DataContractError
from .mageck_adapter import run_mageck
from .models import AnalysisResult, ExperimentConfig, NarrativeSnippet
from .narrative import NarrativeSettings, generate_narrative
from .normalization import (
    compute_gene_stats,
    compute_log2_fold_change,
    normalize_counts_cpm,
)
from .qc import run_all_qc
from .results import build_analysis_summary, merge_gene_results
from .rra import run_rra

logger = logging.getLogger(__name__)


class DataPaths(NamedTuple):
    counts: Path
    library: Path
    metadata: Path


@dataclass
class PipelineSettings:
    use_mageck: bool = True
    enable_llm: bool = False
    output_root: Path = Path("artifacts")
    enrichr_libraries: Optional[List[str]] = None
    narrative_model: Optional[str] = None
    narrative_temperature: float = 0.2
    narrative_max_tokens: int = 400
    cache_annotations: bool = True


def _ensure_output_dir(root: Path) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_dir = root / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def run_analysis(
    config: ExperimentConfig,
    paths: DataPaths,
    settings: Optional[PipelineSettings] = None,
) -> AnalysisResult:
    """Execute the full CRISPR-studio analysis pipeline."""
    settings = settings or PipelineSettings()
    start_time = time.time()

    output_dir = _ensure_output_dir(settings.output_root)
    logger.info("Writing analysis artifacts to %s", output_dir)

    counts = load_counts(paths.counts)
    library = load_library(paths.library)
    metadata = config

    qc_metrics = run_all_qc(
        counts,
        library,
        metadata,
        min_count=metadata.analysis.min_count_threshold,
    )

    counts_cpm = normalize_counts_cpm(counts)
    log2fc = compute_log2_fold_change(counts_cpm, metadata)
    gene_stats = compute_gene_stats(log2fc, library)

    gene_df: Optional[pd.DataFrame] = None
    artifacts: Dict[str, str] = {}
    warnings: List[str] = []

    if settings.use_mageck:
        mageck_df = run_mageck(paths.counts, metadata, output_dir=output_dir)
        if mageck_df is not None:
            gene_df = mageck_df
        else:
            warnings.append("MAGeCK not available; using RRA fallback.")

    if gene_df is None:
        gene_df = run_rra(log2fc, library)

    gene_df_path = output_dir / "gene_results.csv"
    gene_df.to_csv(gene_df_path, index=False)
    artifacts["gene_results"] = str(gene_df_path)

    counts_path = output_dir / "normalized_counts.csv"
    counts_cpm.to_csv(counts_path)
    artifacts["normalized_counts"] = str(counts_path)

    qc_path = output_dir / "qc_metrics.json"
    qc_path.write_text(json.dumps([metric.model_dump() for metric in qc_metrics], indent=2))
    artifacts["qc_metrics"] = str(qc_path)

    enrichment_results = []
    if settings.enrichr_libraries:
        significant_genes = gene_df[gene_df["fdr"] <= metadata.analysis.fdr_threshold]["gene"].tolist() if "gene" in gene_df.columns else []
        enrichment_results = run_enrichr(
            significant_genes,
            libraries=settings.enrichr_libraries,
            cutoff=metadata.analysis.fdr_threshold,
        )

    annotation_data = {}
    if settings.cache_annotations:
        genes = gene_df["gene"].tolist() if "gene" in gene_df.columns else gene_df["gene_symbol"].tolist()
        annotation_data = fetch_gene_annotations(genes)

    runtime = time.time() - start_time
    summary = build_analysis_summary(
        total_guides=counts.shape[0],
        total_genes=gene_df.shape[0],
        significant_genes=0,
        screen_type=metadata.screen_type,
        scoring_method=metadata.analysis.scoring_method,
        runtime_seconds=runtime,
    )

    narratives: List[NarrativeSnippet] = []
    analysis_result = merge_gene_results(
        config=metadata,
        summary=summary,
        gene_df=gene_df,
        qc_metrics=qc_metrics,
        narratives=narratives,
        pathway_results=enrichment_results,
        artifacts=artifacts,
        warnings=warnings,
    )

    narrative_settings = NarrativeSettings(
        enable_llm=settings.enable_llm,
        llm_model=settings.narrative_model or "gpt-4o-mini",
        temperature=settings.narrative_temperature,
        max_tokens=settings.narrative_max_tokens,
    )
    analysis_result.narratives = generate_narrative(analysis_result, narrative_settings)

    result_path = output_dir / "analysis_result.json"
    result_path.write_text(json.dumps(analysis_result.model_dump(mode="json"), indent=2))
    artifacts["analysis_result"] = str(result_path)
    analysis_result.artifacts = artifacts

    return analysis_result
