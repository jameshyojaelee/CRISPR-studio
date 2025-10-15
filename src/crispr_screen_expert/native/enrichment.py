"""Native-backed pathway enrichment helpers."""

from __future__ import annotations

import asyncio
import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple

import numpy as np
import pandas as pd

from ..exceptions import DataContractError
from ..logging_config import get_logger
from ..models import PathwayResult

logger = get_logger(__name__)

try:
    from crispr_native import _hypergeometric_enrichment as _hypergeom_cpp

    _NATIVE_AVAILABLE = True
    _IMPORT_ERROR: Optional[Exception] = None
except ImportError as exc:  # pragma: no cover - executed when native module missing
    _NATIVE_AVAILABLE = False
    _IMPORT_ERROR = exc

_BUILTIN_LIBRARY_PATH = Path(__file__).resolve().parents[2] / "resources" / "enrichment" / "native_demo.json"


def is_available() -> bool:
    """Return True if the C++ enrichment backend is importable."""
    return _NATIVE_AVAILABLE


def _benjamini_hochberg(pvalues: np.ndarray) -> np.ndarray:
    n = len(pvalues)
    order = np.argsort(pvalues)
    ranked = pvalues[order]
    adjusted = np.empty_like(ranked)
    cumulative = 1.0
    for idx in range(n - 1, -1, -1):
        rank = idx + 1
        value = ranked[idx] * n / rank
        cumulative = min(cumulative, value)
        adjusted[idx] = cumulative
    adjusted = np.clip(adjusted, 0.0, 1.0)
    result = np.empty_like(adjusted)
    result[order] = adjusted
    return result


@lru_cache(maxsize=4)
def _load_builtin_libraries() -> Mapping[str, Mapping[str, List[str]]]:
    if not _BUILTIN_LIBRARY_PATH.exists():
        logger.debug("No builtin native enrichment library found at %s", _BUILTIN_LIBRARY_PATH)
        return {}
    data = json.loads(_BUILTIN_LIBRARY_PATH.read_text())
    return {name: {set_name: list(genes) for set_name, genes in library.items()} for name, library in data.items()}


def load_gene_sets(library_names: Sequence[str]) -> Dict[str, Dict[str, List[str]]]:
    """Load gene sets for the requested libraries."""
    libraries: Dict[str, Dict[str, List[str]]] = {}
    builtin = _load_builtin_libraries()
    for name in library_names:
        if name in builtin:
            libraries[name] = builtin[name]
        else:
            raise DataContractError(f"Native enrichment library '{name}' is not available.")
    return libraries


def _prepare_indices(
    hits: Sequence[str],
    libraries: Mapping[str, Mapping[str, Sequence[str]]],
    background: Optional[Sequence[str]] = None,
) -> Tuple[List[List[int]], List[str], List[int], Dict[str, Set[str]], int]:
    universe: Set[str] = set(background or [])
    for library in libraries.values():
        for genes in library.values():
            universe.update(g.upper() for g in genes)
    universe.update(g.upper() for g in hits)
    if not universe:
        raise DataContractError("Cannot construct enrichment universe: no genes provided.")

    sorted_universe = sorted(universe)
    gene_to_index = {gene: idx for idx, gene in enumerate(sorted_universe)}

    gene_sets_indices: List[List[int]] = []
    gene_set_names: List[str] = []
    gene_set_members: Dict[str, Set[str]] = {}

    for library_name, gene_sets in libraries.items():
        for set_name, genes in gene_sets.items():
            key = f"{library_name}:{set_name}"
            members = {gene.upper() for gene in genes if gene}
            indices = [gene_to_index[gene] for gene in members if gene in gene_to_index]
            if not indices:
                continue
            gene_sets_indices.append(indices)
            gene_set_names.append(key)
            gene_set_members[key] = members

    if not gene_sets_indices:
        raise DataContractError("No gene sets contained usable genes after preprocessing.")

    hit_indices = [gene_to_index[gene.upper()] for gene in hits if gene.upper() in gene_to_index]
    if not hit_indices:
        raise DataContractError("No significant genes overlapped the enrichment universe.")

    return gene_sets_indices, gene_set_names, hit_indices, gene_set_members, len(gene_to_index)


def _compute_enrichment_frame(
    hits: Sequence[str],
    libraries: Mapping[str, Mapping[str, Sequence[str]]],
    background: Optional[Sequence[str]] = None,
) -> pd.DataFrame:
    if not _NATIVE_AVAILABLE:
        raise ImportError(
            "crispr_native C++ module is unavailable. Rebuild the native extension to use native enrichment."
        ) from _IMPORT_ERROR

    (
        gene_sets_indices,
        gene_set_names,
        hit_indices,
        members,
        universe_size,
    ) = _prepare_indices(hits, libraries, background)

    native_rows = _hypergeom_cpp(gene_sets_indices, gene_set_names, hit_indices, universe_size)
    frame = pd.DataFrame(native_rows)
    if frame.empty:
        return frame

    frame["fdr"] = _benjamini_hochberg(frame["p_value"].to_numpy(dtype=float))
    frame["enrichment_score"] = -np.log10(frame["p_value"].clip(lower=1e-300))
    frame[["library", "set_name"]] = frame["name"].str.split(":", n=1, expand=True)
    hit_set = {gene.upper() for gene in hits}
    frame["genes"] = frame["name"].apply(lambda key: sorted(hit_set.intersection(members[key])))
    frame["overlap_ratio"] = frame["overlap"] / frame["set_size"].clip(lower=1)
    return frame


def run_enrichment_native(
    hits: Sequence[str],
    libraries: Optional[Sequence[str]] = None,
    *,
    background: Optional[Sequence[str]] = None,
    fdr_threshold: float = 0.1,
) -> List[PathwayResult]:
    """Execute native hypergeometric enrichment and return `PathwayResult` objects."""
    if not hits:
        logger.info("No significant genes provided for native enrichment; returning empty list.")
        return []

    selected_libraries = list(libraries) if libraries else ["native_demo"]
    gene_sets = load_gene_sets(selected_libraries)
    frame = _compute_enrichment_frame(hits, gene_sets, background=background)
    if frame.empty:
        return []

    results: List[PathwayResult] = []
    for row in frame.itertuples(index=False):
        if row.fdr > fdr_threshold:
            continue
        results.append(
            PathwayResult(
                pathway_id=str(row.name),
                name=row.set_name,
                source=row.library,
                enrichment_score=float(row.enrichment_score),
                p_value=float(row.p_value),
                fdr=float(row.fdr),
                genes=list(row.genes),
                direction=None,
                description=None,
            )
        )
    return results


async def run_enrichment_native_async(
    hits: Sequence[str],
    libraries: Optional[Sequence[str]] = None,
    *,
    background: Optional[Sequence[str]] = None,
    fdr_threshold: float = 0.1,
) -> List[PathwayResult]:
    """Async wrapper around `run_enrichment_native` using a thread executor."""
    return await asyncio.to_thread(
        run_enrichment_native,
        hits,
        libraries,
        background=background,
        fdr_threshold=fdr_threshold,
    )
