"""Pipeline orchestrator for CRISPR-studio."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

import pandas as pd

import os

from .analytics import log_event
from .annotations import fetch_gene_annotations
from .config import get_settings
from .data_loader import load_counts, load_library
from .enrichment import run_enrichr
from .exceptions import DataContractError
from .logging_config import get_logger
from .mageck_adapter import MageckExecutionError, run_mageck
from .models import AnalysisResult, ExperimentConfig, NarrativeSnippet
from .narrative import NarrativeSettings, generate_narrative
from .normalization import compute_log2_fold_change, normalize_counts_cpm
from .native import enrichment as native_enrichment
from .native import rra as native_rra
from .qc import run_all_qc
from .results import build_analysis_summary, merge_gene_results
from .rra import run_rra

logger = get_logger(__name__)


class DataPaths(NamedTuple):
    counts: Path
    library: Path
    metadata: Path


@dataclass
class PipelineSettings:
    use_mageck: bool = True
    enable_llm: bool = False
    output_root: Path = field(default_factory=lambda: get_settings().artifacts_dir)
    enrichr_libraries: Optional[List[str]] = None
    narrative_model: Optional[str] = None
    narrative_temperature: float = 0.2
    narrative_max_tokens: int = 400
    cache_annotations: bool = True
    use_native_rra: bool = False
    use_native_enrichment: bool = False


def _run_gene_scoring(
    log2fc: pd.Series,
    library: pd.DataFrame,
    *,
    use_native_rra: bool,
    warnings: List[str],
) -> pd.DataFrame:
    """Execute gene-level scoring using native RRA when requested."""
    if use_native_rra:
        if native_rra.is_available():
            try:
                native_df = native_rra.run_rra_native(log2fc, library)
                logger.info("Using native RRA backend.")
                return native_df
            except DataContractError:
                raise
            except Exception as exc:  # pragma: no cover - defensive path
                message = f"Native RRA failed ({exc}); falling back to Python implementation."
                warnings.append(message)
                logger.warning(message)
        else:
            message = "Native RRA requested but backend not available; falling back to Python implementation."
            warnings.append(message)
            logger.warning(message)

    return run_rra(log2fc, library)


def _ensure_output_dir(root: Path) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_dir = root / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _prepare_mageck_input(
    counts: pd.DataFrame,
    library: pd.DataFrame,
    output_dir: Path,
) -> Path:
    """Create a MAGeCK-compatible count matrix with sgRNA and Gene columns."""
    df = counts.reset_index().rename(columns={"guide_id": "sgRNA"})
    gene_map = library.set_index("guide_id")["gene_symbol"]
    df.insert(1, "Gene", df["sgRNA"].map(gene_map).fillna("UNKNOWN"))
    mageck_input_path = output_dir / "mageck_input.tsv"
    df.to_csv(mageck_input_path, sep="\t", index=False)
    return mageck_input_path


def _env_flag(name: str) -> Optional[bool]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def _apply_env_overrides(settings: PipelineSettings) -> PipelineSettings:
    force_python = _env_flag("CRISPR_STUDIO_FORCE_PYTHON")
    if force_python:
        settings.use_native_rra = False
        settings.use_native_enrichment = False
        return settings

    native_rra = _env_flag("CRISPR_STUDIO_USE_NATIVE_RRA")
    if native_rra is not None:
        settings.use_native_rra = native_rra

    native_enrichment = _env_flag("CRISPR_STUDIO_USE_NATIVE_ENRICHMENT")
    if native_enrichment is not None:
        settings.use_native_enrichment = native_enrichment

    return settings


def run_analysis(
    config: ExperimentConfig,
    paths: DataPaths,
    settings: Optional[PipelineSettings] = None,
) -> AnalysisResult:
    """Execute the full CRISPR-studio analysis pipeline."""
    settings = settings or PipelineSettings()
    settings = _apply_env_overrides(settings)
    start_time = time.time()

    output_dir = _ensure_output_dir(settings.output_root)
    logger.info("Writing analysis artifacts to {}", output_dir)
    log_event(
        "analysis_started",
        {
            "output_dir": str(output_dir),
            "use_mageck": settings.use_mageck,
            "use_native_rra": settings.use_native_rra,
            "use_native_enrichment": settings.use_native_enrichment,
            "enrichr_libraries": ",".join(settings.enrichr_libraries or []),
        },
    )

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
    gene_df: Optional[pd.DataFrame] = None
    artifacts: Dict[str, str] = {}
    warnings: List[str] = []

    if settings.use_mageck:
        mageck_input_path = _prepare_mageck_input(counts, library, output_dir)
        artifacts["mageck_input"] = str(mageck_input_path)
        mageck_failed = False
        try:
            mageck_df = run_mageck(mageck_input_path, metadata, output_dir=output_dir)
        except MageckExecutionError as exc:
            logger.warning("MAGeCK execution failed: %s", exc)
            warnings.append(f"MAGeCK execution failed ({exc}); falling back to RRA.")
            mageck_failed = True
            mageck_df = None
        if mageck_df is not None:
            gene_df = mageck_df
        elif not mageck_failed:
            warnings.append("MAGeCK not available or failed; using RRA fallback.")

    if gene_df is None:
        gene_df = _run_gene_scoring(
            log2fc,
            library,
            use_native_rra=settings.use_native_rra,
            warnings=warnings,
        )

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
        significant_genes = (
            gene_df[gene_df["fdr"] <= metadata.analysis.fdr_threshold]["gene"].tolist()
            if "gene" in gene_df.columns
            else []
        )
        if settings.use_native_enrichment:
            background_genes = library["gene_symbol"].astype(str).tolist()
            try:
                enrichment_results = native_enrichment.run_enrichment_native(
                    significant_genes,
                    settings.enrichr_libraries,
                    background=background_genes,
                    fdr_threshold=metadata.analysis.fdr_threshold,
                )
                logger.info("Native enrichment backend executed for libraries: %s", settings.enrichr_libraries)
            except DataContractError:
                raise
            except ImportError as exc:
                message = (
                    "Native enrichment requested but backend unavailable; falling back to Python implementation."
                )
                warnings.append(message)
                logger.warning("Native enrichment unavailable: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive path
                message = f"Native enrichment failed ({exc}); falling back to Python implementation."
                warnings.append(message)
                logger.warning(message)
        if not enrichment_results:
            enrichment_results = run_enrichr(
                significant_genes,
                libraries=settings.enrichr_libraries,
                cutoff=metadata.analysis.fdr_threshold,
            )

    annotation_data = {}
    if settings.cache_annotations:
        genes = gene_df["gene"].tolist() if "gene" in gene_df.columns else gene_df["gene_symbol"].tolist()
        annotation_data = fetch_gene_annotations(genes)
        annotations_path = output_dir / "gene_annotations.json"
        annotations_path.write_text(json.dumps(annotation_data, indent=2))
        artifacts["gene_annotations"] = str(annotations_path)

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

    log_event(
        "analysis_completed",
        {
            "output_dir": str(output_dir),
            "runtime_seconds": round(runtime, 2),
            "significant_genes": analysis_result.summary.significant_genes,
        },
    )

    return analysis_result
