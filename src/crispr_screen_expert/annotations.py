"""Gene annotation retrieval utilities."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple, cast

import requests

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = Path(".cache/gene_cache.json")
_BATCH_ENV_VAR = "MYGENE_BATCH_SIZE"
_MAX_BATCH_SIZE = 500
_DEFAULT_BATCH_SIZE = 500
_BATCH_SLEEP_THRESHOLD = 2
_BATCH_DELAY_SECONDS = 0.2


def _load_cache(cache_path: Path) -> Dict[str, Dict[str, object]]:
    if cache_path.exists():
        try:
            return cast(Dict[str, Dict[str, object]], json.loads(cache_path.read_text()))
        except json.JSONDecodeError:
            backup_path = _backup_corrupted_cache(cache_path)
            logger.warning(
                "Gene cache at %s is corrupted; moved to %s before rewriting.",
                cache_path,
                backup_path,
            )
    return {}


def _backup_corrupted_cache(cache_path: Path) -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    backup_path = cache_path.parent / f"{cache_path.name}.bak_{timestamp}"
    try:
        cache_path.rename(backup_path)
    except OSError:
        logger.warning("Failed to rename corrupted cache %s; attempting to overwrite.", cache_path)
        return cache_path
    return backup_path


def _save_cache(cache_path: Path, cache: Dict[str, Dict[str, object]]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2))


def _resolve_batch_size() -> int:
    raw_value = os.getenv(_BATCH_ENV_VAR)
    if raw_value is None:
        return _DEFAULT_BATCH_SIZE
    try:
        value = int(raw_value)
    except ValueError:
        logger.warning("Invalid %s value %r; using default %d.", _BATCH_ENV_VAR, raw_value, _DEFAULT_BATCH_SIZE)
        return _DEFAULT_BATCH_SIZE
    return max(1, min(value, _MAX_BATCH_SIZE))


def _chunked(items: List[str], size: int) -> Iterator[List[str]]:
    for index in range(0, len(items), size):
        yield items[index : index + size]


def _maybe_sleep_between_batches(batch_index: int, total_batches: int) -> None:
    if total_batches > _BATCH_SLEEP_THRESHOLD and batch_index < total_batches:
        time.sleep(_BATCH_DELAY_SECONDS)


def _format_batch_warning(
    batch_index: int,
    chunk_size: int,
    detail: str,
    status: Optional[int] = None,
) -> str:
    extras: List[str] = [f"{chunk_size} genes skipped"]
    if status is not None:
        extras.insert(0, f"HTTP {status}")
    extras.append(detail)
    joined = ", ".join(extras)
    return f"batch {batch_index} ({joined})"


def _normalize_gene_entry(entry: Dict[str, object]) -> Dict[str, object]:
    symbol = entry.get("symbol") or entry.get("gene") or entry.get("name")
    if symbol:
        symbol = str(symbol).upper()
    summary = entry.get("summary") or entry.get("descr") or ""
    return {
        "symbol": symbol,
        "name": entry.get("name"),
        "summary": summary,
        "entrez_id": entry.get("entrezgene"),
        "ensembl": entry.get("ensemblgene"),
        "uniprot": entry.get("uniprot") or {},
        "pathways": entry.get("pathway") or {},
    }


def fetch_gene_annotations(
    genes: Iterable[str],
    *,
    cache_path: Path = DEFAULT_CACHE_PATH,
    species: str = "human",
    fields: Optional[List[str]] = None,
    session: Optional[requests.Session] = None,
) -> Tuple[Dict[str, Dict[str, object]], List[str]]:
    """Fetch gene annotations from MyGene.info with local caching."""
    genes = [g.upper() for g in genes if g]
    if not genes:
        return {}, []

    cache = _load_cache(cache_path)
    remaining = [gene for gene in genes if gene not in cache]

    if not fields:
        fields = ["symbol", "name", "summary", "entrezgene", "uniprot", "pathway"]

    annotations: Dict[str, Dict[str, object]] = {gene: cache.get(gene, {}) for gene in genes}
    warnings: List[str] = []

    if remaining:
        batch_size = _resolve_batch_size()
        batches = list(_chunked(remaining, batch_size))
        total_batches = len(batches)
        sess = session or requests.Session()
        close_session = session is None
        batch_failures: List[str] = []
        try:
            for batch_index, chunk in enumerate(batches, start=1):
                params: Dict[str, str | int] = {
                    "q": f"symbol:({' OR '.join(chunk)})",
                    "species": species,
                    "fields": ",".join(fields),
                    "size": min(len(chunk), _MAX_BATCH_SIZE),
                }
                try:
                    response = sess.get(
                        "https://mygene.info/v3/query",
                        params=params,
                        timeout=10,
                    )
                    response.raise_for_status()
                    payload = response.json()
                    hits = payload.get("hits", []) if isinstance(payload, dict) else []
                except requests.Timeout as exc:
                    message = _format_batch_warning(batch_index, len(chunk), f"timeout: {exc}")
                    logger.warning(
                        "Gene annotation batch %d timed out after %d genes: %s",
                        batch_index,
                        len(chunk),
                        exc,
                    )
                    batch_failures.append(message)
                    _maybe_sleep_between_batches(batch_index, total_batches)
                    continue
                except requests.HTTPError as exc:
                    status_code = exc.response.status_code if exc.response is not None else None
                    message = _format_batch_warning(batch_index, len(chunk), "HTTP error", status_code)
                    logger.warning(
                        "Gene annotation batch %d failed with HTTP status %s for %d genes.",
                        batch_index,
                        status_code,
                        len(chunk),
                    )
                    batch_failures.append(message)
                    _maybe_sleep_between_batches(batch_index, total_batches)
                    continue
                except requests.RequestException as exc:
                    message = _format_batch_warning(batch_index, len(chunk), f"request error: {exc}")
                    logger.warning(
                        "Gene annotation batch %d hit a network error for %d genes: %s",
                        batch_index,
                        len(chunk),
                        exc,
                    )
                    batch_failures.append(message)
                    _maybe_sleep_between_batches(batch_index, total_batches)
                    continue

                chunk_updates = False
                for hit in hits:
                    normalized = _normalize_gene_entry(hit)
                    symbol_obj = normalized.get("symbol")
                    if isinstance(symbol_obj, str):
                        cache[symbol_obj] = normalized
                        annotations[symbol_obj] = normalized
                        chunk_updates = True

                if chunk_updates:
                    _save_cache(cache_path, cache)

                _maybe_sleep_between_batches(batch_index, total_batches)

        finally:
            if close_session:
                sess.close()

        if batch_failures:
            warnings.append("MyGene.info request issues: " + "; ".join(batch_failures))

    missing = [gene for gene, info in annotations.items() if not info]
    if missing:
        sample = ", ".join(missing[:5])
        message = (
            f"No annotations available for {len(missing)} genes" + (f" (e.g., {sample})" if sample else "")
        )
        warnings.append(message)

    return annotations, warnings
