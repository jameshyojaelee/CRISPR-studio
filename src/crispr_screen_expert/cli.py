"""Command line interface for CRISPR-studio."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from .data_loader import load_counts, load_library, load_metadata
from .models import ExperimentConfig, load_experiment_config
from .pipeline import DataPaths, PipelineSettings, run_analysis
from .logging_config import get_logger
from .analytics import summarise_events
from .config import get_settings

app = typer.Typer(add_completion=False, no_args_is_help=True)
logger = get_logger(__name__)
settings = get_settings()


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
    enrichr: Optional[str] = typer.Option(None, "--enrichr-libraries", help="Comma-separated Enrichr libraries."),
    enable_llm: bool = typer.Option(False, help="Enable LLM narrative generation if API key configured."),
    narrative_model: Optional[str] = typer.Option(None, help="Override LLM model name."),
    narrative_temperature: float = typer.Option(0.2, help="LLM sampling temperature."),
) -> None:
    """Execute the CRISPR-studio analysis pipeline."""
    counts_path = _resolve_path(counts)
    library_path = _resolve_path(library)
    metadata_path = _resolve_path(metadata)
    config = _load_config(metadata_path)

    output_dir = output_root or settings.artifacts_dir
    libraries = [item.strip() for item in enrichr.split(",")] if enrichr else None

    settings = PipelineSettings(
        use_mageck=use_mageck,
        enable_llm=enable_llm,
        output_root=output_dir,
        enrichr_libraries=libraries,
        narrative_model=narrative_model,
        narrative_temperature=narrative_temperature,
    )
    result = run_analysis(
        config=config,
        paths=DataPaths(counts=counts_path, library=library_path, metadata=metadata_path),
        settings=settings,
    )

    typer.secho("Analysis completed.", fg=typer.colors.GREEN)
    logger.info("Analysis completed", artifacts=result.artifacts)
    typer.echo(json.dumps(result.summary.model_dump(mode="json"), indent=2))
    typer.echo("Artifacts:")
    for key, value in result.artifacts.items():
        typer.echo(f"  {key}: {value}")
    if result.warnings:
        typer.secho("Warnings:", fg=typer.colors.YELLOW)
        for warning in result.warnings:
            typer.echo(f"  - {warning}")


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


def main() -> None:
    """Entry point for setuptools."""
    app()


if __name__ == "__main__":
    main()
