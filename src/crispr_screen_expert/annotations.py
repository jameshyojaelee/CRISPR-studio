"""Gene annotation retrieval utilities."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, Iterable, List, Optional, cast

import requests

logger = logging.getLogger(__name__)

DEFAULT_CACHE_PATH = Path(".cache/gene_cache.json")


def _load_cache(cache_path: Path) -> Dict[str, Dict[str, object]]:
    if cache_path.exists():
        try:
            return cast(Dict[str, Dict[str, object]], json.loads(cache_path.read_text()))
        except json.JSONDecodeError:
            logger.warning("Gene cache at %s is corrupted; ignoring.", cache_path)
    return {}


def _save_cache(cache_path: Path, cache: Dict[str, Dict[str, object]]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2))


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
) -> Dict[str, Dict[str, object]]:
    """Fetch gene annotations from MyGene.info with local caching."""
    genes = [g.upper() for g in genes if g]
    if not genes:
        return {}

    cache = _load_cache(cache_path)
    remaining = [gene for gene in genes if gene not in cache]

    if not fields:
        fields = ["symbol", "name", "summary", "entrezgene", "uniprot", "pathway"]

    annotations: Dict[str, Dict[str, object]] = {gene: cache.get(gene, {}) for gene in genes}

    if remaining:
        sess = session or requests.Session()
        try:
            query = " OR ".join(remaining)
            params: Dict[str, str | int] = {
                "q": f"symbol:({query})",
                "species": species,
                "fields": ",".join(fields),
                "size": len(remaining),
            }
            response = sess.get(
                "https://mygene.info/v3/query",
                params=params,
                timeout=10,
            )
            response.raise_for_status()
            payload = response.json()
            hits = payload.get("hits", []) if isinstance(payload, dict) else []
        except requests.RequestException as exc:
            logger.warning("Failed to fetch annotations from MyGene.info: %s", exc)
            hits = []

        for hit in hits:
            normalized = _normalize_gene_entry(hit)
            symbol_obj = normalized.get("symbol")
            if isinstance(symbol_obj, str):
                cache[symbol_obj] = normalized
                annotations[symbol_obj] = normalized

        _save_cache(cache_path, cache)

    return annotations
