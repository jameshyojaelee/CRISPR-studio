"""Example API client for the CRISPR-studio FastAPI surface.

Run against a local server:

    python examples/api_client.py --host http://127.0.0.1:8000

The script submits a job using the bundled sample_data, polls until completion,
and downloads available artifacts into ``artifacts/api_client/``.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import requests

DEFAULT_HOST = "http://127.0.0.1:8000"
SAMPLE_DATA_DIR = Path(__file__).resolve().parents[1] / "sample_data"


def build_submit_payload(
    *,
    counts_path: Path,
    library_path: Path,
    metadata_path: Path,
    use_mageck: bool = False,
    use_native_rra: bool = False,
    use_native_enrichment: bool = False,
    enrichr_libraries: Optional[Iterable[str]] = None,
    skip_annotations: bool = True,
) -> Dict[str, object]:
    """Construct a request body for POST /v1/analysis."""
    libraries = ",".join(enrichr_libraries) if enrichr_libraries else None
    return {
        "counts_path": str(counts_path),
        "library_path": str(library_path),
        "metadata_path": str(metadata_path),
        "use_mageck": use_mageck,
        "use_native_rra": use_native_rra,
        "use_native_enrichment": use_native_enrichment,
        "enrichr_libraries": libraries,
        "skip_annotations": skip_annotations,
    }


def build_headers(api_key: Optional[str] = None) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["X-API-Key"] = api_key
    return headers


def submit_job(host: str, payload: Dict[str, object], api_key: Optional[str] = None) -> str:
    response = requests.post(
        f"{host.rstrip('/')}/v1/analysis",
        json=payload,
        headers=build_headers(api_key),
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    return data["job_id"]


def poll_status(
    host: str,
    job_id: str,
    *,
    api_key: Optional[str] = None,
    timeout_seconds: int = 240,
    poll_interval: float = 2.0,
) -> Dict[str, object]:
    """Poll /v1/analysis/{job_id} until completion or timeout."""
    deadline = time.time() + timeout_seconds
    status_url = f"{host.rstrip('/')}/v1/analysis/{job_id}"
    last_payload: Dict[str, object] = {}

    while time.time() < deadline:
        response = requests.get(status_url, headers=build_headers(api_key), timeout=15)
        response.raise_for_status()
        last_payload = response.json()
        status_value = (last_payload.get("status") or "").lower()
        if status_value in {"finished", "failed"}:
            return last_payload
        time.sleep(poll_interval)

    raise TimeoutError(f"Job {job_id} did not finish within {timeout_seconds}s")  # pragma: no cover - defensive


def download_artifacts(
    host: str,
    job_id: str,
    destination: Path,
    api_key: Optional[str] = None,
) -> List[Path]:
    """Download available artifacts for a completed job."""
    artifacts_url = f"{host.rstrip('/')}/v1/analysis/{job_id}/artifacts"
    response = requests.get(artifacts_url, headers=build_headers(api_key), timeout=30)
    response.raise_for_status()
    artifact_mapping: Dict[str, str] = response.json().get("artifacts", {})

    destination.mkdir(parents=True, exist_ok=True)
    downloaded: List[Path] = []
    for name, url in artifact_mapping.items():
        artifact_resp = requests.get(url if url.startswith("http") else f"{host.rstrip('/')}/v1/analysis/{job_id}/artifacts/{name}", stream=True, timeout=60)
        artifact_resp.raise_for_status()
        target_path = destination / Path(name).name
        target_path.write_bytes(artifact_resp.content)
        downloaded.append(target_path)
    return downloaded


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Submit a CRISPR-studio analysis job via FastAPI.")
    parser.add_argument("--host", default=DEFAULT_HOST, help="API host (default: http://127.0.0.1:8000)")
    parser.add_argument("--api-key", default=None, help="Optional API key for authenticated deployments")
    parser.add_argument("--counts", type=Path, default=SAMPLE_DATA_DIR / "demo_counts.csv", help="Path to counts CSV/TSV")
    parser.add_argument("--library", type=Path, default=SAMPLE_DATA_DIR / "demo_library.csv", help="Path to library CSV")
    parser.add_argument("--metadata", type=Path, default=SAMPLE_DATA_DIR / "demo_metadata.json", help="Path to metadata JSON")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/api_client"), help="Where to store downloaded artifacts")
    parser.add_argument("--use-mageck", action="store_true", help="Enable MAGeCK scoring (off by default)")
    parser.add_argument("--with-annotations", action="store_true", help="Fetch annotations instead of skipping them")
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    payload = build_submit_payload(
        counts_path=args.counts,
        library_path=args.library,
        metadata_path=args.metadata,
        use_mageck=args.use_mageck,
        skip_annotations=not args.with_annotations,
    )

    print(f"Submitting analysis to {args.host} using sample_data...")
    job_id = submit_job(args.host, payload, api_key=args.api_key)
    print(f"Job queued: {job_id}")

    status_payload = poll_status(args.host, job_id, api_key=args.api_key)
    status_value = (status_payload.get("status") or "").lower()
    print(f"Job status: {status_value}")

    if status_value != "finished":
        raise SystemExit(f"Job failed: {status_payload.get('error')}")

    summary = status_payload.get("summary") or {}
    print(f"Hits: {summary.get('significant_genes')}  Runtime: {summary.get('runtime_seconds')}s")

    artifacts_dir = args.output_dir
    downloaded = download_artifacts(args.host, job_id, artifacts_dir, api_key=args.api_key)
    print(f"Downloaded {len(downloaded)} artifacts to {artifacts_dir}")


if __name__ == "__main__":
    main()
