"""Pydantic domain models for CRISPR-studio.

These models capture the primary configuration and analysis artefacts described in
``overview.md`` and enforce the data contract from ``docs/data_contract.md``.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


class ScreenType(str, Enum):
    """Supported pooled CRISPR screening modalities."""

    DROPOUT = "dropout"
    ENRICHMENT = "enrichment"


class SampleRole(str, Enum):
    """Functional role of a sample within an experiment."""

    CONTROL = "control"
    TREATMENT = "treatment"
    NEUTRAL = "neutral"
    EXCLUDE = "exclude"


class ScoringMethod(str, Enum):
    """Primary gene-level scoring algorithms supported by CRISPR-studio."""

    MAGECK = "mageck"
    RRA = "rra"
    EDGER = "edger"


class QCSeverity(str, Enum):
    """Severity tags for QC metrics."""

    OK = "ok"
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class NarrativeType(str, Enum):
    """Classification for narrative snippets used in reporting."""

    SUMMARY = "summary"
    QC = "qc"
    PATHWAY = "pathway"
    GENE = "gene"


class SampleConfig(BaseModel):
    """Metadata describing a single experimental sample column."""

    sample_id: str = Field(..., description="Unique identifier within the experiment.")
    condition: str = Field(..., description="User-defined condition label (e.g., control, drug).")
    replicate: str = Field(..., description="Biological replicate identifier.")
    role: SampleRole = Field(..., description="Functional role within the analysis.")
    file_column: str = Field(..., description="Column name in the counts matrix.")
    attributes: Dict[str, str] = Field(default_factory=dict, description="Optional extra metadata.")

    @field_validator("sample_id", "condition", "replicate", "file_column")
    @classmethod
    def _no_empty_strings(cls, value: str) -> str:
        if not value or not value.strip():
            raise ValueError("Sample fields must be non-empty strings.")
        return value

    @property
    def is_control(self) -> bool:
        """Return True if the sample should be treated as a control."""
        return self.role == SampleRole.CONTROL

    @property
    def is_treatment(self) -> bool:
        """Return True if the sample should be treated as a treatment."""
        return self.role == SampleRole.TREATMENT


class AnalysisOptions(BaseModel):
    """Advanced analysis toggles and thresholds."""

    scoring_method: ScoringMethod = Field(default=ScoringMethod.MAGECK)
    fdr_threshold: float = Field(default=0.1, gt=0, lt=1)
    enable_pathway: bool = True
    enable_llm: bool = False
    min_count_threshold: int = Field(default=10, ge=0)


class ExperimentConfig(BaseModel):
    """Top-level configuration representing a CRISPR screen analysis run."""

    experiment_name: Optional[str] = Field(default=None)
    library_name: Optional[str] = Field(default=None)
    screen_type: ScreenType = Field(default=ScreenType.DROPOUT)
    samples: List[SampleConfig]
    control_conditions: List[str] = Field(default_factory=list, description="Named control groups.")
    treatment_conditions: List[str] = Field(default_factory=list, description="Named treatment groups.")
    analysis: AnalysisOptions = Field(default_factory=AnalysisOptions)

    @model_validator(mode="after")
    def _validate_samples(self) -> "ExperimentConfig":
        if not self.samples:
            raise ValueError("At least one sample configuration is required.")

        sample_ids = [s.sample_id for s in self.samples]
        if len(sample_ids) != len(set(sample_ids)):
            raise ValueError("Sample IDs must be unique.")

        file_columns = [s.file_column for s in self.samples]
        if len(file_columns) != len(set(file_columns)):
            raise ValueError("Sample file columns must be unique.")

        if not any(s.is_control for s in self.samples):
            raise ValueError("At least one control sample is required.")
        if not any(s.is_treatment for s in self.samples):
            raise ValueError("At least one treatment sample is required.")

        # Derive condition sets if not provided explicitly.
        if not self.control_conditions:
            self.control_conditions = sorted({s.condition for s in self.samples if s.is_control})
        if not self.treatment_conditions:
            self.treatment_conditions = sorted({s.condition for s in self.samples if s.is_treatment})

        return self

    @property
    def control_samples(self) -> List[SampleConfig]:
        """Return the subset of samples tagged as controls."""
        return [s for s in self.samples if s.is_control]

    @property
    def treatment_samples(self) -> List[SampleConfig]:
        """Return the subset of samples tagged as treatments."""
        return [s for s in self.samples if s.is_treatment]

    @property
    def sample_columns(self) -> List[str]:
        """Return ordered list of counts matrix columns for this experiment."""
        return [s.file_column for s in self.samples]


class GuideRecord(BaseModel):
    """Per-guide metrics used for gene aggregation."""

    guide_id: str
    gene_symbol: str
    weight: float = 1.0
    log2_fold_change: Optional[float] = None
    p_value: Optional[float] = None


class GeneResult(BaseModel):
    """Gene-level scoring output."""

    gene_symbol: str
    score: Optional[float] = None
    log2_fold_change: Optional[float] = None
    p_value: Optional[float] = None
    fdr: Optional[float] = None
    rank: Optional[int] = None
    n_guides: int = 0
    guides: List[GuideRecord] = Field(default_factory=list)
    is_significant: bool = False

    @property
    def display_label(self) -> str:
        """Return formatted label for UI elements."""
        return f"{self.gene_symbol} (rank {self.rank})" if self.rank is not None else self.gene_symbol


class PathwayResult(BaseModel):
    """Pathway enrichment result for a gene set."""

    pathway_id: str
    name: str
    source: str
    enrichment_score: Optional[float] = None
    p_value: Optional[float] = None
    fdr: Optional[float] = None
    genes: List[str] = Field(default_factory=list)
    direction: Optional[str] = Field(default=None, description="e.g., up, down, mixed.")
    description: Optional[str] = None


class QCMetric(BaseModel):
    """Quantitative quality-control measure."""

    name: str
    value: Optional[float] = None
    unit: Optional[str] = None
    severity: QCSeverity = QCSeverity.INFO
    threshold: Optional[str] = Field(default=None, description="Human-readable threshold description.")
    details: Optional[str] = None
    recommendation: Optional[str] = None

    @property
    def ok(self) -> bool:
        """Return True when QC severity is non-actionable."""
        return self.severity in {QCSeverity.OK, QCSeverity.INFO}


class QCFlag(BaseModel):
    """Discrete QC signal for display alongside metrics."""

    code: str
    message: str
    severity: QCSeverity = QCSeverity.INFO


class NarrativeSnippet(BaseModel):
    """Narrative paragraph surfaced in reports or UI."""

    title: str
    body: str
    type: NarrativeType = NarrativeType.SUMMARY
    source: str = "system"


class AnalysisSummary(BaseModel):
    """Snapshot summary of the full analysis run."""

    total_guides: int
    total_genes: int
    significant_genes: int
    runtime_seconds: Optional[float] = None
    screen_type: ScreenType
    scoring_method: ScoringMethod
    notes: List[str] = Field(default_factory=list)


class AnalysisResult(BaseModel):
    """Container for the complete analysis output."""

    config: ExperimentConfig
    summary: AnalysisSummary
    gene_results: List[GeneResult] = Field(default_factory=list)
    qc_metrics: List[QCMetric] = Field(default_factory=list)
    qc_flags: List[QCFlag] = Field(default_factory=list)
    pathway_results: List[PathwayResult] = Field(default_factory=list)
    narratives: List[NarrativeSnippet] = Field(default_factory=list)
    artifacts: Dict[str, str] = Field(default_factory=dict, description="Named artefact paths.")
    warnings: List[str] = Field(default_factory=list)

    def top_hits(self, limit: int = 20) -> List[GeneResult]:
        """Return top-ranked significant genes up to the specified limit."""
        filtered = [gene for gene in self.gene_results if gene.is_significant]
        filtered.sort(key=lambda g: (g.rank if g.rank is not None else float("inf")))
        return filtered[:limit]


def _normalize_sample_entries(raw_samples: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    """Normalize sample dictionaries from metadata into SampleConfig-compatible payloads."""
    normalized: List[Dict[str, object]] = []
    for entry in raw_samples:
        try:
            sample_id = str(entry["sample_id"])
        except KeyError as exc:
            raise ValueError("Each sample must include a 'sample_id' field.") from exc

        column = entry.get("file_column") or entry.get("column") or sample_id
        condition = entry.get("condition") or entry.get("group")
        replicate = entry.get("replicate") or "1"
        role_value = entry.get("role", "neutral")

        normalized.append(
            {
                "sample_id": sample_id,
                "condition": str(condition),
                "replicate": str(replicate),
                "role": role_value,
                "file_column": str(column),
                "attributes": {k: v for k, v in entry.items() if k not in {"sample_id", "column", "file_column", "condition", "group", "replicate", "role"}},
            }
        )
    return normalized


def load_experiment_config(path: Path) -> ExperimentConfig:
    """Load and validate an ExperimentConfig from a JSON file."""
    payload = json.loads(path.read_text())

    raw_samples = payload.get("samples", [])
    payload["samples"] = _normalize_sample_entries(raw_samples)

    analysis = payload.get("analysis") or {}
    # Promote top-level fdr_threshold if provided.
    if "fdr_threshold" in payload and "fdr_threshold" not in analysis:
        analysis["fdr_threshold"] = payload["fdr_threshold"]
    payload["analysis"] = analysis

    try:
        return ExperimentConfig.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid experiment metadata: {exc}") from exc
