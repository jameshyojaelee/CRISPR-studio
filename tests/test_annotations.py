from __future__ import annotations

import requests

from crispr_screen_expert.annotations import fetch_gene_annotations


def test_fetch_gene_annotations_timeout(monkeypatch, tmp_path):
    session = requests.Session()

    def fake_get(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr(session, "get", fake_get)

    annotations, warnings = fetch_gene_annotations(
        ["GENE1", "GENE2"],
        cache_path=tmp_path / "cache.json",
        session=session,
    )

    assert annotations["GENE1"] == {}
    assert any("timed out" in warning.lower() for warning in warnings)
