from __future__ import annotations

import json
from typing import Callable, Dict, List

import pytest
import requests

from crispr_screen_expert import annotations as annotations_module


class DummyResponse:
    def __init__(self, payload: Dict[str, object], status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> Dict[str, object]:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)


class FakeSession:
    def __init__(self, handlers: List[Callable[[Dict[str, object]], DummyResponse]]) -> None:
        self._handlers = handlers
        self.calls: List[Dict[str, object]] = []

    def get(self, url: str, params: Dict[str, object], timeout: int) -> DummyResponse:
        call_index = len(self.calls)
        handler = self._handlers[call_index]
        self.calls.append({"params": params, "timeout": timeout})
        return handler(params)


def _genes_from_params(params: Dict[str, object]) -> List[str]:
    """Extract gene symbols from the MyGene query parameter."""
    query = str(params["q"])
    trimmed = query[len("symbol:(") : -1]
    return [gene.strip() for gene in trimmed.split(" OR ") if gene.strip()]


def _success_handler(params: Dict[str, object]) -> DummyResponse:
    genes = _genes_from_params(params)
    hits = [{"symbol": gene, "name": gene.title(), "summary": ""} for gene in genes]
    return DummyResponse({"hits": hits})


def test_fetch_gene_annotations_batches_requests_and_throttles(monkeypatch, tmp_path):
    genes = [f"GENE_{idx:04d}" for idx in range(1200)]
    session = FakeSession([_success_handler, _success_handler, _success_handler])
    sleep_calls: List[tuple[int, int]] = []
    monkeypatch.setattr(
        annotations_module,
        "_maybe_sleep_between_batches",
        lambda idx, total: sleep_calls.append((idx, total)),
    )

    annotations, warnings = annotations_module.fetch_gene_annotations(
        genes,
        cache_path=tmp_path / "cache.json",
        session=session,
    )

    assert len(session.calls) == 3
    assert all(call["params"]["size"] <= 500 for call in session.calls)
    assert sleep_calls == [(1, 3), (2, 3)]
    assert annotations["GENE_0000"]["name"] == "Gene_0000"
    assert warnings == []


def test_fetch_gene_annotations_partial_failure_updates_cache(monkeypatch, tmp_path):
    genes = ["ALPHA", "BETA", "GAMMA", "DELTA"]
    monkeypatch.setenv("MYGENE_BATCH_SIZE", "2")

    def failure_handler(params: Dict[str, object]) -> DummyResponse:  # pragma: no cover - invoked in test
        response = DummyResponse({}, status_code=503)
        raise requests.HTTPError(response=response)

    session = FakeSession([_success_handler, failure_handler])
    monkeypatch.setattr(annotations_module, "_maybe_sleep_between_batches", lambda *_: None)

    cache_path = tmp_path / "cache.json"
    annotations, warnings = annotations_module.fetch_gene_annotations(
        genes,
        cache_path=cache_path,
        session=session,
    )

    cache_data = json.loads(cache_path.read_text())
    assert set(cache_data.keys()) == {"ALPHA", "BETA"}
    error_warning = next(w for w in warnings if w.startswith("MyGene.info request issues"))
    assert "batch 2" in error_warning and "HTTP 503" in error_warning and "2 genes" in error_warning
    assert annotations["ALPHA"]["symbol"] == "ALPHA"
    assert any("No annotations available for 2 genes" in warning for warning in warnings)


def test_fetch_gene_annotations_backups_corrupt_cache(monkeypatch, tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("{bad json}")
    backup_glob = f"{cache_path.name}.bak_*"
    monkeypatch.setenv("MYGENE_BATCH_SIZE", "1")
    session = FakeSession([_success_handler])
    monkeypatch.setattr(annotations_module, "_maybe_sleep_between_batches", lambda *_: None)

    annotations_module.fetch_gene_annotations(
        ["SINGLE"],
        cache_path=cache_path,
        session=session,
    )

    backups = list(cache_path.parent.glob(backup_glob))
    assert backups, "Corrupted cache should be backed up before rewrite."
    new_cache = json.loads(cache_path.read_text())
    assert "SINGLE" in new_cache


def test_fetch_gene_annotations_timeout_warnings_aggregated(monkeypatch, tmp_path):
    genes = ["ONE", "TWO", "THREE"]
    monkeypatch.setenv("MYGENE_BATCH_SIZE", "1")

    def timeout_handler(params: Dict[str, object]) -> DummyResponse:  # pragma: no cover - invoked in test
        raise requests.Timeout("timed out")

    session = FakeSession([timeout_handler, timeout_handler, timeout_handler])
    monkeypatch.setattr(annotations_module, "_maybe_sleep_between_batches", lambda *_: None)

    annotations, warnings = annotations_module.fetch_gene_annotations(
        genes,
        cache_path=tmp_path / "cache.json",
        session=session,
    )

    issue_warnings = [warning for warning in warnings if warning.startswith("MyGene.info request issues")]
    assert len(issue_warnings) == 1
    assert "batch 1" in issue_warnings[0] and "batch 3" in issue_warnings[0]
    assert all(annotations[gene] == {} for gene in genes)
    assert any("No annotations available for 3 genes" in warning for warning in warnings)
