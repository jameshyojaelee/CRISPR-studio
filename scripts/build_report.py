"""Build a showcase report bundle from the demo dataset."""

from __future__ import annotations

import shutil
from pathlib import Path

from crispr_screen_expert.pipeline import DataPaths, PipelineSettings, run_analysis
from crispr_screen_expert.reporting import export_html, export_pdf
from scripts.export_openapi import export_schema


def build_demo_report() -> None:
    root = Path.cwd()
    latest_dir = root / "artifacts" / "latest_report"
    sample_dir = root / "artifacts" / "sample_report"
    latest_dir.mkdir(parents=True, exist_ok=True)
    sample_dir.mkdir(parents=True, exist_ok=True)

    counts = root / "sample_data" / "demo_counts.csv"
    library = root / "sample_data" / "demo_library.csv"
    metadata = root / "sample_data" / "demo_metadata.json"

    result = run_analysis(
        config=None,
        paths=DataPaths(counts=counts, library=library, metadata=metadata),
        settings=PipelineSettings(
            use_mageck=False,
            output_root=latest_dir,
            enrichr_libraries=[],
        ),
    )

    html_path = latest_dir / "crispr_studio_report.html"
    pdf_path = latest_dir / "crispr_studio_report.pdf"

    export_html(result, html_path)
    try:
        export_pdf(result, pdf_path)
    except RuntimeError as exc:
        print(f"[build-report] Warning: {exc}. Skipping PDF export.")
        pdf_path = None

    sample_html = sample_dir / html_path.name
    shutil.copy2(html_path, sample_html)
    if pdf_path:
        sample_pdf = sample_dir / Path(pdf_path).name
        shutil.copy2(pdf_path, sample_pdf)

    bundle_tmp = sample_dir.parent / "crispr_studio_report_bundle"
    if (sample_dir / "crispr_studio_report_bundle.zip").exists():
        (sample_dir / "crispr_studio_report_bundle.zip").unlink()
    archive_path = shutil.make_archive(str(bundle_tmp), "zip", root_dir=sample_dir)
    shutil.move(archive_path, sample_dir / "crispr_studio_report_bundle.zip")

    export_path = export_schema()
    print(f"[build-report] Exported OpenAPI schema to {export_path}")


if __name__ == "__main__":
    build_demo_report()
