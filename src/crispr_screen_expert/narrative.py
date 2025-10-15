"""Narrative generation utilities."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Sequence

from .models import (
    AnalysisResult,
    NarrativeSnippet,
    NarrativeType,
    PathwayResult,
    QCMetric,
    QCSeverity,
)

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore


@dataclass
class NarrativeSettings:
    """Configuration flags for narrative generation."""

    enable_llm: bool = False
    llm_model: str = "gpt-4o-mini"
    temperature: float = 0.2
    max_tokens: int = 400


def _format_hit_list(result: AnalysisResult, limit: int = 5) -> str:
    hits = result.top_hits(limit=limit)
    if not hits:
        return "No genes surpassed the significance threshold."
    formatted = []
    for gene in hits:
        entry = f"{gene.gene_symbol}"
        if gene.log2_fold_change is not None:
            entry += f" (log2FC {gene.log2_fold_change:.2f})"
        if gene.fdr is not None:
            entry += f", FDR {gene.fdr:.3f}"
        formatted.append(entry)
    return "; ".join(formatted)


def _qc_overview(metrics: Sequence[QCMetric]) -> str:
    if not metrics:
        return "No QC metrics computed."
    problems = [m for m in metrics if m.severity in {QCSeverity.WARNING, QCSeverity.CRITICAL}]
    if not problems:
        return "All QC checks passed without warnings."
    lines = []
    for metric in problems[:5]:
        detail = f"{metric.name}: {metric.value:.2f}" if metric.value is not None else metric.name
        if metric.recommendation:
            detail += f" — {metric.recommendation}"
        lines.append(detail)
    if len(problems) > 5:
        lines.append(f"{len(problems) - 5} additional warnings not shown.")
    return " ; ".join(lines)


def _pathway_summary(pathways: Sequence[PathwayResult], limit: int = 5) -> str:
    if not pathways:
        return "No pathway enrichments met the significance threshold."
    items = []
    for pw in pathways[:limit]:
        desc = pw.name
        if pw.fdr is not None:
            desc += f" (FDR {pw.fdr:.3f})"
        if pw.genes:
            desc += f" — genes: {', '.join(pw.genes[:4])}"
        items.append(desc)
    if len(pathways) > limit:
        items.append(f"{len(pathways) - limit} additional pathways not shown.")
    return "; ".join(items)


def _has_openai_credentials(settings: NarrativeSettings) -> bool:
    return bool(settings.enable_llm and OpenAI is not None and os.getenv("OPENAI_API_KEY"))


def _generate_llm_summary(result: AnalysisResult, settings: NarrativeSettings) -> Optional[NarrativeSnippet]:
    if not _has_openai_credentials(settings):
        return None

    client = OpenAI()
    top_hits_text = _format_hit_list(result)
    pathway_text = _pathway_summary(result.pathway_results)
    qc_text = _qc_overview(result.qc_metrics)

    prompt = (
        "You are assisting with CRISPR pooled screen analysis narration.\n"
        "Summarize the findings using the provided structured context.\n"
        "Stick to facts, highlight key genes/pathways, and include data-driven caveats.\n"
        "If a section is empty, note that explicitly. Keep length under 200 words.\n"
        "Context:\n"
        f"- Screen type: {result.summary.screen_type.value}\n"
        f"- Scoring method: {result.summary.scoring_method.value}\n"
        f"- Significant genes: {result.summary.significant_genes}\n"
        f"- Top hits: {top_hits_text}\n"
        f"- Pathways: {pathway_text}\n"
        f"- QC status: {qc_text}\n"
        "Respond with plain text. Include sources only if provided in context; "
        "otherwise say 'based on internal analysis'."
    )

    try:
        response = client.responses.create(
            model=settings.llm_model,
            input=prompt,
            temperature=settings.temperature,
            max_output_tokens=settings.max_tokens,
        )
    except Exception as exc:  # pragma: no cover - network errors
        return NarrativeSnippet(
            title="Automated Summary (LLM Failed)",
            body=f"LLM request failed: {exc}. Falling back to deterministic summary.",
            type=NarrativeType.SUMMARY,
            source="system",
        )

    text = ""
    for item in response.output:
        if item.type == "output_text":
            text += item.text
    text = text.strip()
    if not text:
        return None

    return NarrativeSnippet(
        title="Automated Summary",
        body=f"{text}\n\n⚠️ AI-generated content. Verify before use.",
        type=NarrativeType.SUMMARY,
        source="openai",
    )


def _fallback_summary(result: AnalysisResult) -> NarrativeSnippet:
    summary = (
        f"{result.summary.significant_genes} genes met the FDR ≤ "
        f"{result.config.analysis.fdr_threshold:.2f} threshold using "
        f"{result.summary.scoring_method.value.upper()} on the "
        f"{result.summary.screen_type.value} screen.\n"
        f"Top hits: {_format_hit_list(result)}.\n"
        f"QC status: {_qc_overview(result.qc_metrics)}."
    )
    if result.pathway_results:
        summary += f"\nPathway highlights: {_pathway_summary(result.pathway_results)}."
    return NarrativeSnippet(
        title="Analysis Summary",
        body=summary,
        type=NarrativeType.SUMMARY,
        source="system",
    )


def _qc_snippet(metrics: Sequence[QCMetric]) -> NarrativeSnippet:
    return NarrativeSnippet(
        title="Quality Control",
        body=_qc_overview(metrics),
        type=NarrativeType.QC,
        source="system",
    )


def _top_hits_snippet(result: AnalysisResult, limit: int = 10) -> NarrativeSnippet:
    return NarrativeSnippet(
        title="Gene Highlights",
        body=_format_hit_list(result, limit=limit),
        type=NarrativeType.GENE,
        source="system",
    )


def _pathway_snippet(pathways: Sequence[PathwayResult]) -> Optional[NarrativeSnippet]:
    if not pathways:
        return None
    return NarrativeSnippet(
        title="Pathway Insights",
        body=_pathway_summary(pathways),
        type=NarrativeType.PATHWAY,
        source="system",
    )


def generate_narrative(result: AnalysisResult, settings: Optional[NarrativeSettings] = None) -> List[NarrativeSnippet]:
    """Compose narrative snippets for the analysis result."""
    settings = settings or NarrativeSettings()
    snippets: List[NarrativeSnippet] = []

    llm_snippet = _generate_llm_summary(result, settings)
    if llm_snippet:
        snippets.append(llm_snippet)
    else:
        snippets.append(_fallback_summary(result))

    snippets.append(_top_hits_snippet(result))
    qp = _pathway_snippet(result.pathway_results)
    if qp:
        snippets.append(qp)
    snippets.append(_qc_snippet(result.qc_metrics))

    return snippets
