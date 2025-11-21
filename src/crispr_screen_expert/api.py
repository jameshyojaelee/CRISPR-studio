"""FastAPI surface for CRISPR-studio analysis pipeline."""

from __future__ import annotations
from pathlib import Path
from typing import Dict, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, validator

from .background import JobManager, JobNotFoundError, JobSnapshot
from .config import get_settings
from .models import AnalysisResult, PipelineWarning
from .pipeline import DataPaths, PipelineSettings, run_analysis


class SubmitRequest(BaseModel):
    counts_path: Path = Field(..., description="Path to counts CSV/TSV")
    library_path: Path = Field(..., description="Path to library CSV")
    metadata_path: Path = Field(..., description="Path to metadata JSON")
    use_mageck: bool = True
    use_native_rra: bool = False
    use_native_enrichment: bool = False
    enrichr_libraries: Optional[str] = None
    skip_annotations: bool = False

    @validator("counts_path", "library_path", "metadata_path")
    def _must_exist(cls, value: Path) -> Path:
        if not value.exists():
            raise ValueError(f"Path not found: {value}")
        return value


class SubmitResponse(BaseModel):
    job_id: str
    status: str


class StatusResponse(BaseModel):
    job_id: str
    status: str
    summary: Optional[Dict] = None
    warnings: Optional[list[PipelineWarning]] = None
    error: Optional[str] = None


class ArtifactResponse(BaseModel):
    job_id: str
    artifacts: Dict[str, str]


class APIConfig:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.job_manager = JobManager(max_workers=2)
        self.results: Dict[str, Dict] = {}

    def record_success(self, job_id: str, result: AnalysisResult) -> None:
        self.results[job_id] = {
            "result": result.model_dump(mode="json"),
            "warnings": [warning.model_dump(mode="json") for warning in result.warnings],
        }

    def record_failure(self, job_id: str, error: BaseException) -> None:
        self.results[job_id] = {"error": str(error)}


def create_app() -> FastAPI:
    config = APIConfig()
    app = FastAPI(title="CRISPR-studio API", version="0.2.0")

    def auth_dependency(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> None:
        configured = getattr(config.settings, "api_key", None)
        if configured and x_api_key != configured:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    @app.post("/v1/analysis", response_model=SubmitResponse, status_code=status.HTTP_202_ACCEPTED)
    def submit_analysis(payload: SubmitRequest, _: None = Depends(auth_dependency)) -> SubmitResponse:
        settings = PipelineSettings(
            use_mageck=payload.use_mageck,
            use_native_rra=payload.use_native_rra,
            use_native_enrichment=payload.use_native_enrichment,
            enrichr_libraries=payload.enrichr_libraries.split(",") if payload.enrichr_libraries else None,
            cache_annotations=not payload.skip_annotations,
        )

        def run_job() -> AnalysisResult:
            return run_analysis(
                config=None,
                paths=DataPaths(
                    counts=payload.counts_path,
                    library=payload.library_path,
                    metadata=payload.metadata_path,
                ),
                settings=settings,
            )

        def _on_complete(snapshot: JobSnapshot) -> None:
            if snapshot.status == "finished":
                try:
                    result = config.job_manager.result(snapshot.job_id)
                except JobNotFoundError:
                    return
                config.record_success(snapshot.job_id, result)
            elif snapshot.status == "failed":
                try:
                    error = config.job_manager.exception(snapshot.job_id)
                except JobNotFoundError:
                    error = RuntimeError("Job missing from history")
                config.record_failure(snapshot.job_id, error or RuntimeError("Unknown failure"))

        job_id = config.job_manager.submit(run_job, on_complete=_on_complete)

        return SubmitResponse(job_id=job_id, status="queued")

    @app.get("/v1/analysis/{job_id}", response_model=StatusResponse)
    def get_status(job_id: str, _: None = Depends(auth_dependency)) -> StatusResponse:
        status_value = config.job_manager.status(job_id)
        payload = config.results.get(job_id)
        summary = None
        warnings = None
        error = None
        if payload:
            if "result" in payload:
                result = AnalysisResult.model_validate(payload["result"])
                summary = result.summary.model_dump()
                warnings = payload.get("warnings")
            else:
                error = payload.get("error")
        return StatusResponse(job_id=job_id, status=status_value, summary=summary, warnings=warnings, error=error)

    @app.get("/v1/analysis/{job_id}/artifacts", response_model=ArtifactResponse)
    def list_artifacts(job_id: str, _: None = Depends(auth_dependency)) -> ArtifactResponse:
        payload = config.results.get(job_id)
        if not payload or "result" not in payload:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifacts unavailable for this job")
        result = AnalysisResult.model_validate(payload["result"])
        return ArtifactResponse(job_id=job_id, artifacts=result.artifacts)

    @app.get("/v1/analysis/{job_id}/artifacts/{name}")
    def download_artifact(job_id: str, name: str, _: None = Depends(auth_dependency)):
        payload = config.results.get(job_id)
        if not payload or "result" not in payload:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not available")
        result = AnalysisResult.model_validate(payload["result"])
        artifact_path = result.artifacts.get(name)
        if not artifact_path:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
        path = Path(artifact_path)
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact file missing")
        return FileResponse(path)

    @app.get("/v1/openapi")
    def export_openapi(_: None = Depends(auth_dependency)) -> JSONResponse:
        return JSONResponse(content=app.openapi())

    return app
