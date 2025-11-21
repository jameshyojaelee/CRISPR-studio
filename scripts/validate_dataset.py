"""Validate counts/library/metadata inputs against the CRISPR-studio contract."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

import typer

from crispr_screen_expert.data_loader import (
    load_counts,
    load_library,
    load_metadata,
    match_counts_to_library,
    validate_metadata_against_counts,
)
from crispr_screen_expert.exceptions import DataContractError
from crispr_screen_expert.models import ExperimentConfig, SampleConfig

app = typer.Typer(add_completion=False, help=__doc__)

FIX_CHECKLIST = [
    "Ensure every sample column named in metadata exists in the counts header.",
    "Deduplicate guide_id rows in both counts and library files.",
    "Use uppercase HGNC-style gene symbols in the library annotation.",
    "Coerce counts to non-negative integers; replace blanks with 0.",
]


def normalise_samples(config: ExperimentConfig) -> List[Dict[str, str]]:
    """Return a stable sample manifest with only the expected keys."""
    manifest: List[Dict[str, str]] = []
    for sample in config.samples:
        assert isinstance(sample, SampleConfig)
        manifest.append(
            {
                "sample_id": sample.sample_id,
                "file_column": sample.file_column,
                "role": sample.role.value,
                "condition": sample.condition,
                "replicate": sample.replicate,
            }
        )
    return manifest


def validate_dataset(
    counts_path: Path,
    library_path: Path,
    metadata_path: Path,
    *,
    skip_annotations: bool = True,
    export_samples: Optional[Path] = None,
) -> Dict[str, object]:
    """Run validation and return structured results."""
    summary: Dict[str, object] = {"warnings": [], "suggestions": list(FIX_CHECKLIST)}

    try:
        counts = load_counts(counts_path)
    except DataContractError as exc:
        summary["error"] = f"Counts validation failed: {exc}"
        return summary

    try:
        library = load_library(library_path)
    except DataContractError as exc:
        summary["error"] = f"Library validation failed: {exc}"
        return summary

    try:
        metadata = load_metadata(metadata_path)
    except DataContractError as exc:
        summary["error"] = f"Metadata validation failed: {exc}"
        return summary
    except ValueError as exc:
        summary["error"] = f"Metadata schema rejected the payload: {exc}"
        return summary

    try:
        validate_metadata_against_counts(metadata, counts)
    except DataContractError as exc:
        summary["error"] = f"Metadata references missing columns: {exc}"
        return summary

    _, missing_guides, merged = match_counts_to_library(counts, library)
    missing_count = len(missing_guides)
    if missing_count:
        summary["warnings"].append(
            f"{missing_count} guides are mismatched between counts and library (see issue column)."
        )
        if (missing_guides["issue"] == "missing_in_library").any():
            summary["suggestions"].append("Add missing guides to the library or drop them from the counts matrix.")
        if (missing_guides["issue"] == "missing_in_counts").any():
            summary["suggestions"].append("Fill missing count columns or remove orphaned guides from the library.")

    summary["counts_shape"] = counts.shape
    summary["library_rows"] = len(library)
    summary["sample_columns"] = metadata.sample_columns
    summary["skip_annotations"] = skip_annotations

    if export_samples:
        manifest = normalise_samples(metadata)
        export_samples.parent.mkdir(parents=True, exist_ok=True)
        export_samples.write_text(json.dumps(manifest, indent=2))
        summary["exported_manifest"] = str(export_samples)

    summary["message"] = "Validation successful."
    return summary


@app.command()
def main(
    counts: Path = typer.Argument(..., exists=True, readable=True, help="Counts CSV/TSV with guide_id + sample columns."),
    library: Path = typer.Argument(..., exists=True, readable=True, help="Library CSV with guide_id and gene_symbol."),
    metadata: Path = typer.Argument(..., exists=True, readable=True, help="Metadata JSON matching the contract."),
    skip_annotations: bool = typer.Option(True, help="Flag downstream runs to avoid annotation fetches."),
    export_samples: Optional[Path] = typer.Option(None, "--export-samples", help="Write a normalised sample manifest JSON."),
) -> None:
    result = validate_dataset(
        counts_path=counts,
        library_path=library,
        metadata_path=metadata,
        skip_annotations=skip_annotations,
        export_samples=export_samples,
    )

    if "error" in result:
        typer.secho(result["error"], fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho(result.get("message", "Validation complete."), fg=typer.colors.GREEN)
    typer.echo(f"Counts shape: {result['counts_shape']}")
    typer.echo(f"Library rows: {result['library_rows']}")
    typer.echo(f"Samples: {', '.join(result['sample_columns'])}")
    if result.get("exported_manifest"):
        typer.echo(f"Normalised sample manifest written to {result['exported_manifest']}")

    if result.get("warnings"):
        typer.secho("Warnings:", fg=typer.colors.YELLOW)
        for warning in result["warnings"]:
            typer.echo(f"- {warning}")

    typer.secho("Fix checklist:", fg=typer.colors.CYAN)
    for suggestion in result["suggestions"]:
        typer.echo(f"- {suggestion}")


if __name__ == "__main__":
    main()
