"""Native-backed robust rank aggregation utilities."""

from __future__ import annotations

from typing import Callable, Dict, List, Optional, cast

import numpy as np
import pandas as pd

from ..exceptions import DataContractError
from ..logging_config import get_logger

logger = get_logger(__name__)

_rust_run_rra: Optional[Callable[..., List[Dict[str, object]]]] = None
_backend_info_rust: Optional[Callable[[], Dict[str, object]]] = None
_IMPORT_ERROR: Optional[Exception] = None

try:
    from crispr_native_rust import _backend_info as _backend_info_impl, run_rra_native as _rust_run_rra_impl

    _NATIVE_AVAILABLE = True
    _backend_info_rust = cast(Callable[[], Dict[str, object]], _backend_info_impl)
    _rust_run_rra = cast(Callable[..., List[Dict[str, object]]], _rust_run_rra_impl)
except ImportError as exc:  # pragma: no cover - executed when native module missing
    _NATIVE_AVAILABLE = False
    _IMPORT_ERROR = exc


def is_available() -> bool:
    """Return True when the Rust RRA backend is importable."""
    return _NATIVE_AVAILABLE


def backend_info() -> dict[str, object]:
    """Return metadata describing the loaded native backend."""
    if not _NATIVE_AVAILABLE or _backend_info_rust is None:
        raise ImportError(
            "crispr_native_rust is not available. Install native extras and build the extension.",
        ) from _IMPORT_ERROR
    return dict(_backend_info_rust())


def run_rra_native(
    log2fc: pd.Series,
    library: pd.DataFrame,
    guide_pvalues: Optional[pd.Series] = None,
    *,
    min_guides: int = 2,
    higher_is_better: bool = True,
) -> pd.DataFrame:
    """Execute the Rust RRA backend and return a pandas DataFrame."""
    if not _NATIVE_AVAILABLE or _rust_run_rra is None:
        raise ImportError(
            "crispr_native_rust is not available. Reinstall with native extras and build the Rust module.",
        ) from _IMPORT_ERROR

    if log2fc.empty:
        raise DataContractError("log2 fold-change series is empty.")

    required_columns = {"guide_id", "gene_symbol"}
    missing = required_columns - set(library.columns)
    if missing:
        missing_str = ", ".join(sorted(missing))
        raise DataContractError(f"Library is missing required columns: {missing_str}")

    merged = (
        library.set_index("guide_id")
        .join(log2fc.rename("log2fc"), how="inner")
        .dropna(subset=["log2fc"])
    )
    if merged.empty:
        raise DataContractError("No overlapping guides between log2 fold-change values and library.")

    guide_ids = merged.index.to_numpy(copy=False)
    if "weight" in merged.columns:
        weight_array = merged["weight"].to_numpy(dtype=np.float64, copy=False)
    else:
        weight_array = np.ones(len(merged), dtype=np.float64)

    if guide_pvalues is not None:
        guide_pvalues = guide_pvalues.reindex(guide_ids)
        p_value_array: Optional[np.ndarray] = guide_pvalues.to_numpy(dtype=np.float64, copy=False)
    else:
        p_value_array = None

    log_values = merged["log2fc"].to_numpy(dtype=np.float64, copy=False)
    gene_symbols = merged["gene_symbol"].astype(str).tolist()

    logger.debug(
        "Running native RRA backend on %d guides (%d genes)",
        log_values.size,
        merged["gene_symbol"].nunique(),
    )

    result = _rust_run_rra(
        log_values,
        gene_symbols,
        weight_array,
        p_value_array,
        min_guides,
        higher_is_better,
    )

    df = pd.DataFrame(result)
    expected_columns = [
        "gene",
        "score",
        "p_value",
        "fdr",
        "rank",
        "n_guides",
        "mean_log2fc",
        "median_log2fc",
        "var_log2fc",
    ]
    missing_cols = [column for column in expected_columns if column not in df.columns]
    if missing_cols:
        raise RuntimeError(f"Native RRA result missing expected columns: {', '.join(missing_cols)}")

    df = df[expected_columns].copy()
    df["rank"] = df["rank"].astype(int)
    df["n_guides"] = df["n_guides"].astype(int)
    return df
