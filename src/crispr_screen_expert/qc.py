"""Quality control computations for CRISPR-studio."""

from __future__ import annotations

from itertools import combinations
from typing import List

import numpy as np
import pandas as pd

from .exceptions import DataContractError
from .models import ExperimentConfig, QCMetric, QCSeverity


# Threshold defaults drawn from typical pooled CRISPR screen heuristics.
_REPLICATE_THRESHOLDS = {
    QCSeverity.OK: 0.9,
    QCSeverity.WARNING: 0.7,
}

_DETECTION_THRESHOLDS = {
    QCSeverity.OK: 0.9,
    QCSeverity.WARNING: 0.75,
}


def _classify_ratio(value: float | None, ok_threshold: float, warn_threshold: float) -> QCSeverity:
    if value is None:
        return QCSeverity.WARNING
    if value >= ok_threshold:
        return QCSeverity.OK
    if value >= warn_threshold:
        return QCSeverity.WARNING
    return QCSeverity.CRITICAL


def _classify_correlation(value: float | None) -> QCSeverity:
    if value is None:
        return QCSeverity.WARNING
    if value >= _REPLICATE_THRESHOLDS[QCSeverity.OK]:
        return QCSeverity.OK
    if value >= _REPLICATE_THRESHOLDS[QCSeverity.WARNING]:
        return QCSeverity.WARNING
    return QCSeverity.CRITICAL


def _safe_log_transform(counts: pd.DataFrame) -> pd.DataFrame:
    """Apply log-transform with pseudo-count handling."""
    return np.log2(counts + 1)


def compute_replicate_correlations(counts: pd.DataFrame, metadata: ExperimentConfig) -> List[QCMetric]:
    """Compute Pearson correlations between replicates within each condition."""
    metrics: List[QCMetric] = []
    log_counts = _safe_log_transform(counts)

    by_condition: dict[str, List[str]] = {}
    for sample in metadata.samples:
        by_condition.setdefault(sample.condition, []).append(sample.file_column)

    for condition, columns in by_condition.items():
        if len(columns) < 2:
            continue
        for left, right in combinations(columns, 2):
            corr = log_counts[left].corr(log_counts[right], method="pearson")
            severity = _classify_correlation(corr)
            metrics.append(
                QCMetric(
                    name=f"Replicate correlation ({condition}: {left} vs {right})",
                    value=float(corr) if corr is not None else None,
                    severity=severity,
                    threshold=f">= {_REPLICATE_THRESHOLDS[QCSeverity.OK]:.2f} ideal",
                    details="Pearson correlation on log2 normalized counts.",
                    recommendation="Investigate library prep or sequencing for low-correlation replicates."
                    if severity != QCSeverity.OK
                    else None,
                )
            )
    if not metrics:
        metrics.append(
            QCMetric(
                name="Replicate correlation",
                value=None,
                severity=QCSeverity.INFO,
                details="Not computed: fewer than two replicates per condition.",
            )
        )
    return metrics


def compute_guide_detection(counts: pd.DataFrame, min_count: int = 10) -> List[QCMetric]:
    """Fraction of guides detected above threshold per sample."""
    metrics: List[QCMetric] = []
    total_guides = counts.shape[0]
    if total_guides == 0:
        raise DataContractError("Counts matrix is empty; cannot compute detection metrics.")

    for column in counts.columns:
        detected = (counts[column] >= min_count).sum()
        ratio = detected / total_guides
        severity = _classify_ratio(
            ratio,
            ok_threshold=_DETECTION_THRESHOLDS[QCSeverity.OK],
            warn_threshold=_DETECTION_THRESHOLDS[QCSeverity.WARNING],
        )
        metrics.append(
            QCMetric(
                name=f"Guide detection ({column})",
                value=ratio,
                unit="fraction",
                severity=severity,
                threshold=f">= {_DETECTION_THRESHOLDS[QCSeverity.OK]:.0%} ideal",
                details=f"{detected}/{total_guides} guides above {min_count} reads.",
                recommendation="Low detection suggests library bottlenecking or sequencing issues."
                if severity != QCSeverity.OK
                else None,
            )
        )
    return metrics


def compute_library_coverage(counts: pd.DataFrame, library: pd.DataFrame) -> List[QCMetric]:
    """Summarize coverage per gene based on observed counts."""
    if counts.empty:
        raise DataContractError("Counts matrix is empty; cannot compute coverage metrics.")

    merged = library.set_index("guide_id").join(counts, how="left")
    missing_guides = merged[counts.columns].isna().any(axis=1)
    missing_count = missing_guides.sum()
    severity = QCSeverity.OK if missing_count == 0 else QCSeverity.WARNING

    metrics = [
        QCMetric(
            name="Library coverage",
            value=1 - (missing_count / library.shape[0]),
            unit="fraction",
            severity=severity,
            threshold="100% coverage ideal",
            details=f"{missing_count}/{library.shape[0]} guides missing from counts.",
            recommendation="Double-check mapping or library completeness."
            if missing_count > 0
            else None,
        )
    ]
    return metrics


def evaluate_controls(counts: pd.DataFrame, metadata: ExperimentConfig) -> List[QCMetric]:
    """Check control stability via median absolute deviation."""
    metrics: List[QCMetric] = []
    control_cols = [s.file_column for s in metadata.control_samples]
    if not control_cols:
        return [
            QCMetric(
                name="Control stability",
                value=None,
                severity=QCSeverity.INFO,
                details="No control samples defined.",
            )
        ]

    control_counts = counts[control_cols]
    medians = control_counts.median(axis=1)
    deviations = (control_counts.sub(medians, axis=0)).abs()
    mad = deviations.median().median()

    tolerance = 0.25 * (control_counts.mean().mean() + 1)
    severity = QCSeverity.OK if mad <= tolerance else QCSeverity.WARNING

    metrics.append(
        QCMetric(
            name="Control MAD",
            value=float(mad),
            severity=severity,
            details=f"Median absolute deviation across control replicates (threshold {tolerance:.2f}).",
            recommendation="Large MAD suggests inconsistent control replicates."
            if severity != QCSeverity.OK
            else None,
        )
    )
    return metrics


def run_all_qc(
    counts: pd.DataFrame,
    library: pd.DataFrame,
    metadata: ExperimentConfig,
    min_count: int = 10,
) -> List[QCMetric]:
    """Execute all QC computations and return flattened list of metrics."""
    validate_columns = set(metadata.sample_columns) - set(counts.columns)
    if validate_columns:
        raise DataContractError(
            f"Counts matrix missing expected sample columns: {', '.join(sorted(validate_columns))}"
        )

    metrics: List[QCMetric] = []
    metrics.extend(compute_replicate_correlations(counts, metadata))
    metrics.extend(compute_guide_detection(counts, min_count=min_count))
    metrics.extend(compute_library_coverage(counts, library))
    metrics.extend(evaluate_controls(counts, metadata))
    return metrics
