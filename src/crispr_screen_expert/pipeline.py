"""Pipeline orchestrator for CRISPR-studio."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, NamedTuple, Optional

import pandas as pd

import os

from .analytics import log_event
from .annotations import fetch_gene_annotations
from .config import get_settings
from .data_loader import load_counts, load_library, load_metadata
from .enrichment import run_enrichr
from .exceptions import DataContractError, QualityControlError
from .logging_config import get_logger
from .mageck_adapter import MageckExecutionError, run_mageck
from .models import (
    AnalysisResult,
    ExperimentConfig,
    GuideRecord,
    NarrativeSnippet,
    PipelineWarning,
    QCSeverity,
    ScoringMethod,
    ScreenType,
)
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
    metadata: Optional[Path] = None


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


def _add_warning(
    warnings: List[PipelineWarning],
    code: str,
    message: str,
    *,
    details: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a structured warning to the shared list."""
    warnings.append(PipelineWarning(code=code, message=message, details=details or {}))


def _run_gene_scoring(
    log2fc: pd.Series,
    library: pd.DataFrame,
    *,
    use_native_rra: bool,
    warnings: List[PipelineWarning],
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
                _add_warning(
                    warnings,
                    code="native_rra_failed",
                    message=message,
                    details={"error": str(exc)},
                )
                logger.warning(message)
        else:
            message = "Native RRA requested but backend not available; falling back to Python implementation."
            _add_warning(
                warnings,
                code="native_rra_unavailable",
                message=message,
            )
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


def _normalize_mageck_output(df: pd.DataFrame, screen_type: ScreenType) -> pd.DataFrame:
    """Map MAGeCK bidirectional outputs onto unified columns."""
    normalized = df.copy()
    preferred = "neg" if screen_type == ScreenType.DROPOUT else "pos"
    alternate = "pos" if preferred == "neg" else "neg"
    suffix_map = {
        "score": "score",
        "p-value": "p_value",
        "fdr": "fdr",
        "rank": "rank",
    }

    if screen_type == ScreenType.ENRICHMENT and "pos|fdr" in normalized.columns:
        mapping = {
            f"pos|{suffix}": alias for suffix, alias in suffix_map.items() if f"pos|{suffix}" in normalized.columns
        }
        directed = normalized.rename(columns=mapping).copy()
        directed["direction"] = "pos"
        return directed

    if "fdr" in normalized.columns:
        if "direction" not in normalized.columns:
            normalized["direction"] = "neg"
        return normalized

    def _apply_direction(direction: str) -> Optional[pd.DataFrame]:
        mapping = {
            f"{direction}|{suffix}": alias
            for suffix, alias in suffix_map.items()
            if f"{direction}|{suffix}" in normalized.columns
        }
        if not mapping:
            return None
        directed = normalized.rename(columns=mapping).copy()
        directed["direction"] = direction
        return directed

    directed = _apply_direction(preferred)
    if directed is None:
        directed = _apply_direction(alternate)

    return directed if directed is not None else normalized


def _build_guide_lookup(log2fc: pd.Series, library: pd.DataFrame) -> Dict[str, List[GuideRecord]]:
    """Create per-gene guide records for downstream visualisations."""
    lookup: Dict[str, List[GuideRecord]] = {}
    merged = library.set_index("guide_id").join(log2fc.rename("log2_fold_change"), how="inner")
    if merged.empty:
        return lookup

    for guide_id, row in merged.iterrows():
        gene_symbol = str(row.get("gene_symbol", "")).upper()
        if not gene_symbol:
            continue
        weight_value = row.get("weight", 1.0)
        if pd.isna(weight_value):
            weight_value = 1.0
        record = GuideRecord(
            guide_id=str(guide_id),
            gene_symbol=gene_symbol,
            weight=float(weight_value),
            log2_fold_change=float(row["log2_fold_change"]) if pd.notna(row["log2_fold_change"]) else None,
            p_value=None,
        )
        lookup.setdefault(gene_symbol, []).append(record)
    return lookup


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
    config: Optional[ExperimentConfig] = None,
    paths: DataPaths,
    settings: Optional[PipelineSettings] = None,
) -> AnalysisResult:
    """Execute the full CRISPR-studio analysis pipeline.

    When ``config`` is omitted, the experiment metadata is loaded from ``paths.metadata``.
    """
    settings = settings or PipelineSettings()
    settings = _apply_env_overrides(settings)
    start_time = time.time()

    if config is None:
        if paths.metadata is None:
            raise DataContractError("Metadata path must be provided when config is not supplied.")
        config = load_metadata(Path(paths.metadata))
    assert config is not None

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
    warnings: List[PipelineWarning] = []

    qc_metrics = run_all_qc(
        counts,
        library,
        metadata,
        min_count=metadata.analysis.min_count_threshold,
    )
    critical_metrics = [metric for metric in qc_metrics if metric.severity == QCSeverity.CRITICAL]
    if critical_metrics:
        failure_details = ", ".join(metric.name for metric in critical_metrics)
        log_event(
            "analysis_failed",
            {
                "output_dir": str(output_dir),
                "reason": "qc_failure",
                "critical_metrics": failure_details,
                "warnings": [],
            },
        )
        raise QualityControlError(
            f"Quality control checks failed: {failure_details}. Resolve issues before rerunning.",
            metrics=critical_metrics,
        )

    counts_cpm = normalize_counts_cpm(counts)
    log2fc = compute_log2_fold_change(counts_cpm, metadata)
    gene_df: Optional[pd.DataFrame] = None
    artifacts: Dict[str, str] = {}
    raw_counts_path = output_dir / "raw_counts.csv"
    counts.to_csv(raw_counts_path, index_label="guide_id")
    artifacts["raw_counts"] = str(raw_counts_path)
    guide_lookup = _build_guide_lookup(log2fc, library)
    scoring_method_used = metadata.analysis.scoring_method

    if settings.use_mageck:
        mageck_input_path = _prepare_mageck_input(counts, library, output_dir)
        artifacts["mageck_input"] = str(mageck_input_path)
        mageck_failed = False
        try:
            mageck_df = run_mageck(mageck_input_path, metadata, output_dir=output_dir)
        except MageckExecutionError as exc:
            logger.warning("MAGeCK execution failed: %s", exc)
            _add_warning(
                warnings,
                code="mageck_failed",
                message=f"MAGeCK execution failed ({exc}); falling back to RRA.",
                details={"error": str(exc)},
            )
            mageck_failed = True
            mageck_df = None
        if mageck_df is not None:
            gene_df = _normalize_mageck_output(mageck_df, metadata.screen_type)
            scoring_method_used = ScoringMethod.MAGECK
        elif not mageck_failed:
            _add_warning(
                warnings,
                code="mageck_unavailable",
                message="MAGeCK not available or failed; using RRA fallback.",
            )

    if gene_df is None:
        gene_df = _run_gene_scoring(
            log2fc,
            library,
            use_native_rra=settings.use_native_rra,
            warnings=warnings,
        )
        scoring_method_used = ScoringMethod.RRA

    gene_df_path = output_dir / "gene_results.csv"
    gene_df.to_csv(gene_df_path, index=False)
    artifacts["gene_results"] = str(gene_df_path)

    counts_path = output_dir / "normalized_counts.csv"
    counts_cpm.to_csv(counts_path, index_label="guide_id")
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
            except DataContractError as exc:
                message = (
                    "Native enrichment libraries unavailable; falling back to Enrichr results."
                )
                _add_warning(
                    warnings,
                    code="native_enrichment_library_missing",
                    message=message,
                    details={
                        "libraries": list(settings.enrichr_libraries or []),
                        "error": str(exc),
                    },
                )
                logger.warning(
                    "Native enrichment libraries %s unavailable: %s",
                    settings.enrichr_libraries,
                    exc,
                )
            except ImportError as exc:
                message = (
                    "Native enrichment requested but backend unavailable; falling back to Python implementation."
                )
                _add_warning(
                    warnings,
                    code="native_enrichment_backend_missing",
                    message=message,
                    details={"error": str(exc)},
                )
                logger.warning(
                    "Native enrichment backend missing for libraries %s: %s",
                    settings.enrichr_libraries,
                    exc,
                )
            except Exception as exc:  # pragma: no cover - defensive path
                message = f"Native enrichment failed ({exc}); falling back to Python implementation."
                _add_warning(
                    warnings,
                    code="native_enrichment_backend_failed",
                    message=message,
                    details={"error": str(exc)},
                )
                logger.warning(
                    "Native enrichment backend crashed for libraries %s: %s",
                    settings.enrichr_libraries,
                    exc,
                )
        if not enrichment_results:
            enrichment_results = run_enrichr(
                significant_genes,
                libraries=settings.enrichr_libraries,
                cutoff=metadata.analysis.fdr_threshold,
            )

    annotation_data: Dict[str, Dict[str, object]] = {}
    if settings.cache_annotations:
        genes = gene_df["gene"].tolist() if "gene" in gene_df.columns else gene_df["gene_symbol"].tolist()
        annotation_data, fetch_warnings = fetch_gene_annotations(genes)
        for warning_text in fetch_warnings:
            _add_warning(
                warnings,
                code="annotations_warning",
                message=warning_text,
            )
        annotations_path = output_dir / "gene_annotations.json"
        annotations_path.write_text(json.dumps(annotation_data, indent=2))
        artifacts["gene_annotations"] = str(annotations_path)

    runtime = time.time() - start_time
    summary = build_analysis_summary(
        total_guides=counts.shape[0],
        total_genes=gene_df.shape[0],
        significant_genes=0,
        screen_type=metadata.screen_type,
        scoring_method=scoring_method_used,
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
        guide_lookup=guide_lookup,
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

    settings_snapshot = {
        "use_mageck": settings.use_mageck,
        "use_native_rra": settings.use_native_rra,
        "use_native_enrichment": settings.use_native_enrichment,
        "enrichr_libraries": list(settings.enrichr_libraries or []),
        "cache_annotations": settings.cache_annotations,
        "skip_annotations": not settings.cache_annotations,
    }
    pipeline_settings_path = output_dir / "pipeline_settings.json"
    pipeline_settings_path.write_text(json.dumps(settings_snapshot, indent=2))
    artifacts["pipeline_settings"] = str(pipeline_settings_path)

    result_path = output_dir / "analysis_result.json"
    result_path.write_text(json.dumps(analysis_result.model_dump(mode="json"), indent=2))
    artifacts["analysis_result"] = str(result_path)
    analysis_result.artifacts = artifacts
    warning_payload = [warning.model_dump(mode="json") for warning in warnings]

    log_event(
        "analysis_completed",
        {
            "output_dir": str(output_dir),
            "runtime_seconds": round(runtime, 2),
            "significant_genes": analysis_result.summary.significant_genes,
            "warnings": warning_payload,
        },
    )

    return analysis_result
