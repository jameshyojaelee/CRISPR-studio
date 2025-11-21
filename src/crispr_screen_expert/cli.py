"""Command line interface for CRISPR-studio."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .data_loader import load_counts, load_library
from .models import ExperimentConfig, load_experiment_config
from .pipeline import DataPaths, PipelineSettings, run_analysis
from .logging_config import get_logger
from .analytics import summarise_events
from .config import get_settings
from .exceptions import DataContractError, QualityControlError

app = typer.Typer(add_completion=False, no_args_is_help=True)
logger = get_logger(__name__)
APP_SETTINGS = get_settings()


def _warning_to_text(warning: object) -> str:
    """Render pipeline warnings regardless of whether they are structured or legacy strings."""
    if hasattr(warning, "message"):
        code = getattr(warning, "code", "")
        prefix = f"[{code}] " if code else ""
        return f"{prefix}{getattr(warning, 'message')}"
    if isinstance(warning, dict):
        code = warning.get("code")
        message = warning.get("message") or warning.get("text") or ""
        prefix = f"[{code}] " if code else ""
        return f"{prefix}{message}"
    return str(warning)


def _resolve_path(path: Path) -> Path:
    path = path.expanduser().resolve()
    if not path.exists():
        raise typer.BadParameter(f"Path not found: {path}")
    return path


def _load_config(metadata_path: Path) -> ExperimentConfig:
    try:
        return load_experiment_config(metadata_path)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


@app.command("validate-data")
def validate_data(
    counts: Path = typer.Argument(..., help="Path to counts matrix CSV/TSV."),
    library: Path = typer.Argument(..., help="Path to sgRNA library CSV."),
    metadata: Path = typer.Argument(..., help="Path to experiment metadata JSON."),
) -> None:
    """Validate inputs against CRISPR-studio data contracts."""
    counts_path = _resolve_path(counts)
    library_path = _resolve_path(library)
    metadata_path = _resolve_path(metadata)

    config = _load_config(metadata_path)
    counts_df = load_counts(counts_path)
    library_df = load_library(library_path)

    missing_columns = [col for col in config.sample_columns if col not in counts_df.columns]
    if missing_columns:
        typer.secho(
            f"Counts file missing expected sample columns: {', '.join(missing_columns)}",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    missing_guides = set(library_df["guide_id"]) - set(counts_df.index)
    if missing_guides:
        typer.secho(
            f"Warning: {len(missing_guides)} guides from library absent in counts matrix.",
            fg=typer.colors.YELLOW,
        )

    typer.secho("Data validation succeeded.", fg=typer.colors.GREEN)
    logger.info("Validated data inputs", counts=counts_path, library=library_path, metadata=metadata_path)


@app.command("run-pipeline")
def run_pipeline(
    counts: Path = typer.Argument(..., help="Path to counts matrix CSV/TSV."),
    library: Path = typer.Argument(..., help="Path to sgRNA library CSV."),
    metadata: Path = typer.Argument(..., help="Path to experiment metadata JSON."),
    output_root: Optional[Path] = typer.Option(None, "--output-root", "-o", help="Directory to store analysis artifacts."),
    use_mageck: bool = typer.Option(True, help="Attempt to run MAGeCK if available."),
    use_native_rra: bool = typer.Option(False, help="Use native Rust RRA backend when built."),
    use_native_enrichment: bool = typer.Option(False, help="Use native enrichment backend when built."),
    enrichr: Optional[str] = typer.Option(None, "--enrichr-libraries", help="Comma-separated Enrichr libraries."),
    enable_llm: bool = typer.Option(False, help="Enable LLM narrative generation if API key configured."),
    narrative_model: Optional[str] = typer.Option(None, help="Override LLM model name."),
    narrative_temperature: float = typer.Option(0.2, help="LLM sampling temperature."),
    skip_annotations: bool = typer.Option(False, help="Skip gene annotation requests (offline mode)."),
) -> None:
    """Execute the CRISPR-studio analysis pipeline."""
    counts_path = _resolve_path(counts)
    library_path = _resolve_path(library)
    metadata_path = _resolve_path(metadata)

    output_dir = output_root or APP_SETTINGS.artifacts_dir
    libraries = [item.strip() for item in enrichr.split(",")] if enrichr else None

    pipeline_settings = PipelineSettings(
        use_mageck=use_mageck,
        enable_llm=enable_llm,
        output_root=output_dir,
        enrichr_libraries=libraries,
        narrative_model=narrative_model,
        narrative_temperature=narrative_temperature,
        use_native_rra=use_native_rra,
        use_native_enrichment=use_native_enrichment,
        cache_annotations=not skip_annotations,
    )
    try:
        result = run_analysis(
            config=None,
            paths=DataPaths(counts=counts_path, library=library_path, metadata=metadata_path),
            settings=pipeline_settings,
        )
    except QualityControlError as exc:
        typer.secho("Analysis aborted due to critical QC findings.", fg=typer.colors.RED)
        for metric in exc.metrics:
            detail = metric.name
            if metric.value is not None:
                detail += f" (value={metric.value})"
            if metric.recommendation:
                detail += f" — {metric.recommendation}"
            typer.echo(f"  - {detail}")
        raise typer.Exit(code=2) from exc
    except DataContractError as exc:
        typer.secho(f"Input validation failed: {exc}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    typer.secho("Analysis completed.", fg=typer.colors.GREEN)
    logger.info("Analysis completed", artifacts=result.artifacts)
    typer.echo(json.dumps(result.summary.model_dump(mode="json"), indent=2))
    typer.echo("Artifacts:")
    for key, value in result.artifacts.items():
        typer.echo(f"  {key}: {value}")
    if result.warnings:
        typer.secho("Warnings:", fg=typer.colors.YELLOW)
        for warning in result.warnings:
            typer.echo(f"  - {_warning_to_text(warning)}")


@app.command("list-artifacts")
def list_artifacts(
    root: Path = typer.Argument(Path("artifacts"), help="Root directory containing analysis artifacts."),
    limit: int = typer.Option(10, "--limit", "-l", help="Maximum number of runs to display."),
) -> None:
    """List available analysis runs and artifact files."""
    root = root.expanduser().resolve()
    if not root.exists():
        typer.secho(f"No artifact directory found at {root}", fg=typer.colors.RED)
        logger.warning("Artifact directory missing", root=root)
        raise typer.Exit(code=1)

    runs = sorted([path for path in root.iterdir() if path.is_dir()], reverse=True)
    if not runs:
        typer.secho("No analysis runs found.", fg=typer.colors.YELLOW)
        logger.info("No artifacts to list", root=root)
        raise typer.Exit(code=0)

    displayed = 0
    for run_dir in runs:
        typer.secho(f"Run: {run_dir.name}", fg=typer.colors.BLUE)
        for artifact in sorted(run_dir.glob("*")):
            typer.echo(f"  - {artifact.name}")
        typer.echo("")
        displayed += 1
        if displayed >= limit:
            break


@app.command("analytics-summary")
def analytics_summary() -> None:
    """Summarise opt-in analytics events."""
    summary = summarise_events()
    typer.echo(json.dumps(summary, indent=2))


@app.command("serve-api")
def serve_api(
    host: str = typer.Option("0.0.0.0", help="Host to bind the API server."),
    port: int = typer.Option(8000, help="Port to bind the API server."),
    reload: bool = typer.Option(False, help="Enable auto-reload (development only)."),
) -> None:
    """Launch the FastAPI service via uvicorn."""
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover - runtime dependency
        typer.secho("uvicorn is required to serve the API. Install with `pip install uvicorn`.", fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Starting CRISPR-studio API on {host}:{port} ...")
    uvicorn.run("crispr_screen_expert.api:create_app", host=host, port=port, reload=reload, factory=True)


def main() -> None:
    """Entry point for setuptools."""
    app()


if __name__ == "__main__":
    main()
