"""MAGeCK command-line integration utilities."""

from __future__ import annotations

import logging
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import pandas as pd

from .exceptions import DataContractError
from .models import ExperimentConfig

logger = logging.getLogger(__name__)

MAGECK_BINARY = "mageck"


def is_available() -> bool:
    """Return True if the MAGeCK CLI is available on PATH."""
    return shutil.which(MAGECK_BINARY) is not None


class MageckExecutionError(RuntimeError):
    """Raised when MAGeCK execution fails."""


def _format_args_from_kwargs(options: Dict[str, object]) -> List[str]:
    """Convert keyword arguments to CLI arguments."""
    args: List[str] = []
    for key, value in options.items():
        option = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                args.append(option)
        elif isinstance(value, (int, float, str)):
            args.extend([option, str(value)])
        elif isinstance(value, Iterable):
            joined = ",".join(str(v) for v in value)
            args.extend([option, joined])
        else:
            logger.warning("Ignoring unsupported MAGeCK option '%s' of type %s", key, type(value))
    return args


def _build_base_command(
    counts_path: Path,
    metadata: ExperimentConfig,
    output_prefix: str,
    library_path: Optional[Path],
) -> List[str]:
    """Construct the base MAGeCK command using metadata."""
    treatment_cols = [sample.file_column for sample in metadata.treatment_samples]
    control_cols = [sample.file_column for sample in metadata.control_samples]

    if not treatment_cols or not control_cols:
        raise DataContractError("MAGeCK requires both treatment and control samples.")

    command = [
        MAGECK_BINARY,
        "test",
        "-k",
        str(counts_path),
        "-t",
        ",".join(treatment_cols),
        "-c",
        ",".join(control_cols),
        "-n",
        output_prefix,
    ]

    if library_path:
        command.extend(["--norm-method", "control", "--control-sgrna", str(library_path)])

    return command


def parse_gene_summary(path: Path) -> pd.DataFrame:
    """Parse MAGeCK gene summary output into a DataFrame."""
    if not path.exists():
        raise MageckExecutionError(f"MAGeCK gene summary file not found: {path}")

    df = pd.read_csv(path, sep="\t")
    required_columns = {"id", "neg|score", "neg|p-value", "neg|fdr", "neg|rank"}
    missing = required_columns - set(df.columns)
    if missing:
        logger.warning("MAGeCK gene summary missing expected columns: %s", ", ".join(sorted(missing)))

    df = df.rename(
        columns={
            "id": "gene",
            "neg|score": "score",
            "neg|p-value": "p_value",
            "neg|fdr": "fdr",
            "neg|rank": "rank",
        }
    )
    return df


def run_mageck(
    counts_path: Path,
    metadata: ExperimentConfig,
    output_dir: Path,
    library_path: Optional[Path] = None,
    timeout: int = 1800,
    **kwargs: object,
) -> Optional[pd.DataFrame]:
    """Execute MAGeCK test and return gene summary dataframe.

    If MAGeCK is unavailable, returns None and logs a warning.
    Additional keyword arguments are converted into CLI options, e.g.
    ``run_mageck(..., norm_method=\"median\")`` becomes ``--norm-method median``.
    """
    if not is_available():
        logger.warning("MAGeCK binary not found on PATH. Skipping MAGeCK execution.")
        return None

    counts_path = counts_path.resolve()
    if not counts_path.exists():
        raise DataContractError(f"Counts file not found for MAGeCK run: {counts_path}")

    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    output_prefix = kwargs.pop("output_prefix", f"mageck_{timestamp}")

    command = _build_base_command(counts_path, metadata, output_prefix=str(output_prefix), library_path=library_path)
    command.extend(_format_args_from_kwargs(kwargs))

    logger.info("Running MAGeCK command: %s", " ".join(command))

    try:
        completed = subprocess.run(
            command,
            cwd=str(output_dir),
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        logger.debug("MAGeCK stdout: %s", completed.stdout)
        if completed.stderr:
            logger.debug("MAGeCK stderr: %s", completed.stderr)
    except subprocess.TimeoutExpired as exc:
        raise MageckExecutionError("MAGeCK execution timed out.") from exc
    except subprocess.CalledProcessError as exc:
        raise MageckExecutionError(f"MAGeCK execution failed: {exc.stderr}") from exc
    except FileNotFoundError as exc:
        raise MageckExecutionError("MAGeCK binary not found during execution.") from exc

    gene_summary_path = output_dir / f"{output_prefix}.gene_summary.txt"
    return parse_gene_summary(gene_summary_path)
