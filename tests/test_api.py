from __future__ import annotations

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from crispr_screen_expert.api import create_app


@pytest.fixture()
def api_client(tmp_path, counts_path, library_path, metadata_path, monkeypatch: pytest.MonkeyPatch):
    artifacts_dir = tmp_path / "artifacts"
    uploads_dir = tmp_path / "uploads"
    logs_dir = tmp_path / "logs"
    artifacts_dir.mkdir()
    uploads_dir.mkdir()
    logs_dir.mkdir()

    monkeypatch.setenv("ARTIFACTS_DIR", str(artifacts_dir))
    monkeypatch.setenv("UPLOADS_DIR", str(uploads_dir))
    monkeypatch.setenv("LOGS_DIR", str(logs_dir))
    monkeypatch.setenv("API_KEY", "secret-token")

    from crispr_screen_expert import config as config_module

    config_module.get_settings.cache_clear()
    app = create_app()
    client = TestClient(app)
    yield client
    config_module.get_settings.cache_clear()


def _auth_headers() -> dict[str, str]:
    return {"X-API-Key": "secret-token"}


def test_submit_and_download_artifacts(api_client: TestClient, counts_path: Path, library_path: Path, metadata_path: Path):
    response = api_client.post(
        "/v1/analysis",
        json={
            "counts_path": str(counts_path),
            "library_path": str(library_path),
            "metadata_path": str(metadata_path),
            "use_mageck": False,
        },
        headers=_auth_headers(),
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]

    for _ in range(30):
        poll = api_client.get(f"/v1/analysis/{job_id}", headers=_auth_headers())
        body = poll.json()
        if body["status"] in {"finished", "failed"}:
            break
        time.sleep(0.2)
    else:
        pytest.fail("Job did not finish in time")

    assert body["status"] == "finished"
    assert body["summary"]["significant_genes"] >= 0

    artifacts_response = api_client.get(f"/v1/analysis/{job_id}/artifacts", headers=_auth_headers())
    assert artifacts_response.status_code == 200
    artifacts = artifacts_response.json()["artifacts"]
    assert "analysis_result" in artifacts

    artifact_name, artifact_path = next(iter(artifacts.items()))
    download = api_client.get(f"/v1/analysis/{job_id}/artifacts/{artifact_name}", headers=_auth_headers())
    assert download.status_code == 200
    assert download.content


def test_requires_api_key_when_configured(api_client: TestClient, counts_path: Path, library_path: Path, metadata_path: Path):
    response = api_client.post(
        "/v1/analysis",
        json={
            "counts_path": str(counts_path),
            "library_path": str(library_path),
            "metadata_path": str(metadata_path),
        },
    )
    assert response.status_code == 401


def test_invalid_paths_raise_validation_error(api_client: TestClient):
    response = api_client.post(
        "/v1/analysis",
        json={
            "counts_path": "missing.csv",
            "library_path": "missing.csv",
            "metadata_path": "missing.json",
        },
        headers=_auth_headers(),
    )
    assert response.status_code == 422


def test_unknown_job_returns_not_found(api_client: TestClient):
    status_resp = api_client.get("/v1/analysis/unknown", headers=_auth_headers())
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "unknown"

    artifacts_resp = api_client.get("/v1/analysis/unknown/artifacts", headers=_auth_headers())
    assert artifacts_resp.status_code == 404
