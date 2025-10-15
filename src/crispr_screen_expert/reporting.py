"""Reporting utilities for CRISPR-studio."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .models import AnalysisResult, GeneResult


def _environment(template_dir: Path) -> Environment:
    return Environment(
        loader=FileSystemLoader(str(template_dir)),
        autoescape=select_autoescape(["html", "xml"]),
    )


def render_html(result: AnalysisResult, template_dir: Path = Path("templates")) -> str:
    """Render an HTML report using Jinja2 templates."""
    env = _environment(template_dir)
    template = env.get_template("report.html")
    top_genes: Iterable[GeneResult] = result.top_hits(limit=20)
    html = template.render(
        summary_title=f"CRISPR-studio Report — {result.summary.screen_type.value.title()} Screen",
        result=result,
        top_genes=top_genes,
        pathway_results=result.pathway_results,
        qc_metrics=result.qc_metrics,
        narratives=result.narratives,
    )
    return html


def export_html(result: AnalysisResult, output_path: Path, template_dir: Path = Path("templates")) -> Path:
    html = render_html(result, template_dir=template_dir)
    output_path.write_text(html)
    return output_path


def export_pdf(result: AnalysisResult, output_path: Path, template_dir: Path = Path("templates")) -> Path:
    try:
        from weasyprint import HTML  # type: ignore
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("WeasyPrint is required for PDF export.") from exc

    html = render_html(result, template_dir=template_dir)
    HTML(string=html).write_pdf(str(output_path))
    return output_path
