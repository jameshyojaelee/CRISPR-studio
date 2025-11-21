"""Reporting utilities for CRISPR-studio."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd
import plotly.io as pio
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import AnalysisResult, GeneResult
from .visualization import (
    detection_heatmap,
    replicate_correlation_scatter,
    volcano_plot,
)


@dataclass
class ReportChartBundle:
    volcano_svg: Optional[str] = None
    replicate_svg: Optional[str] = None
    detection_svg: Optional[str] = None


def _environment(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def _figure_to_svg(fig) -> Optional[str]:
    try:
        svg_bytes = pio.to_image(fig, format="svg")
    except Exception:  # pragma: no cover - kaleido issues handled gracefully
        return None
    return svg_bytes.decode("utf-8")


def _load_counts_dataframe(result: AnalysisResult) -> Optional[pd.DataFrame]:
    counts_path = result.artifacts.get("normalized_counts") or result.artifacts.get("raw_counts")
    if not counts_path:
        return None
    path = Path(counts_path)
    if not path.exists():
        return None
    try:
        df = pd.read_csv(path)
    except Exception:
        return None
    if "guide_id" in df.columns:
        df = df.set_index("guide_id")
    return df


def _build_chart_bundle(result: AnalysisResult) -> ReportChartBundle:
    charts = ReportChartBundle()

    gene_rows = [gene.model_dump() for gene in result.gene_results]
    gene_df = pd.DataFrame(gene_rows)
    if not gene_df.empty:
        if "gene_symbol" in gene_df.columns and "gene" not in gene_df.columns:
            gene_df["gene"] = gene_df["gene_symbol"]
        try:
            charts.volcano_svg = _figure_to_svg(volcano_plot(gene_df))
        except Exception:
            charts.volcano_svg = None

    counts_df = _load_counts_dataframe(result)
    if counts_df is not None and not counts_df.empty:
        try:
            replicate_cols = [sample.file_column for sample in result.config.samples]
            if len(replicate_cols) >= 2:
                charts.replicate_svg = _figure_to_svg(
                    replicate_correlation_scatter(counts_df, replicate_cols[0], replicate_cols[1])
                )
            charts.detection_svg = _figure_to_svg(detection_heatmap(counts_df))
        except Exception:
            charts.replicate_svg = charts.replicate_svg or None
            charts.detection_svg = charts.detection_svg or None

    return charts


def _group_qc_metrics(result: AnalysisResult) -> Dict[str, List]:
    groups: Dict[str, List] = defaultdict(list)
    for metric in result.qc_metrics:
        groups[metric.severity.value].append(metric)
    return groups


def _format_number(value: Optional[float], decimals: int = 2) -> str:
    if value is None:
        return "—"
    if isinstance(value, int):
        return f"{value:,}"
    try:
        return f"{value:.{decimals}f}"
    except Exception:
        return str(value)


def _cover_metadata(result: AnalysisResult) -> Dict[str, str]:
    analysis_path = result.artifacts.get("analysis_result")
    run_label = ""
    if analysis_path:
        try:
            run_dir = Path(analysis_path).parent.name
            run_label = run_dir
        except Exception:
            run_label = ""
    experiment_name = result.config.experiment_name or "Untitled Experiment"
    return {
        "title": "CRISPR-studio Analysis Report",
        "experiment": experiment_name,
        "run_label": run_label,
        "screen_type": result.summary.screen_type.value.title(),
    }


def _kpi_cards(result: AnalysisResult) -> List[Dict[str, str]]:
    kpis = [
        {"label": "Total Guides", "value": _format_number(result.summary.total_guides, 0)},
        {"label": "Total Genes", "value": _format_number(result.summary.total_genes, 0)},
        {"label": "Significant Genes", "value": _format_number(result.summary.significant_genes, 0)},
        {
            "label": "Runtime (s)",
            "value": _format_number(result.summary.runtime_seconds, 1),
        },
    ]
    return kpis


def _pathway_cards(result: AnalysisResult, limit: int = 6) -> List[Dict[str, str]]:
    cards: List[Dict[str, str]] = []
    for pathway in result.pathway_results[:limit]:
        cards.append(
            {
                "name": pathway.name,
                "source": pathway.source,
                "fdr": _format_number(pathway.fdr, 3),
                "description": ", ".join(pathway.genes[:5]) if pathway.genes else "",
            }
        )
    return cards


def build_report_context(result: AnalysisResult) -> Dict[str, object]:
    top_genes: Iterable[GeneResult] = result.top_hits(limit=20)
    charts = _build_chart_bundle(result)
    qc_groups = _group_qc_metrics(result)
    cover = _cover_metadata(result)
    narratives = result.narratives

    return {
        "cover": cover,
        "kpis": _kpi_cards(result),
        "result": result,
        "top_genes": top_genes,
        "qc_groups": qc_groups,
        "pathway_cards": _pathway_cards(result),
        "narratives": narratives,
        "volcano_svg": charts.volcano_svg,
        "replicate_svg": charts.replicate_svg,
        "detection_svg": charts.detection_svg,
        "summary_title": f"CRISPR-studio Report — {cover['screen_type']}",
    }


def render_html(result: AnalysisResult, template_dir: Path = Path("templates")) -> str:
    """Render an HTML report using Jinja2 templates."""
    env = _environment(template_dir)
    template = env.get_template("report.html")
    context = build_report_context(result)
    html = template.render(**context)
    return html


def export_html(result: AnalysisResult, output_path: Path, template_dir: Path = Path("templates")) -> Path:
    html = render_html(result, template_dir=template_dir)
    output_path.write_text(html)
    return output_path


def export_pdf(result: AnalysisResult, output_path: Path, template_dir: Path = Path("templates")) -> Path:
    try:
        from weasyprint import HTML  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "WeasyPrint is required for PDF export. Install the reports extra via "
            "`pip install crispr_screen_expert[reports]`."
        ) from exc

    html = render_html(result, template_dir=template_dir)
    HTML(string=html, base_url=str(template_dir.resolve())).write_pdf(str(output_path))
    return output_path
