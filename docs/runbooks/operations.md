# Operations Playbook

Lightweight procedures for keeping the demo instance healthy.

## Monitor JobManager
- Check the Dash history rail or `GET /v1/analysis/{job_id}` for stuck statuses (`queued`/`running` longer than expected).
- Inspect the in-memory history via `JobManager.history()` (see `src/crispr_screen_expert/background.py`) if you need to debug locally.
- Clear out orphaned uploads/artifacts periodically (`logs/`, `uploads/`, `artifacts/`) to avoid disk churn; the manager only keeps the most recent jobs in memory.

## Rotate Analytics Logs
- Opt-in analytics are written to `logs/analytics/events.csv`. The file appends in perpetuity; rotate monthly by copying to `events-<YYYYMM>.csv` and truncating the live file.
- Ensure the parent directory exists (`CRISPR_STUDIO__LOGS_DIR` controls the root). Set `LOG_LEVEL=INFO` before capture to avoid noisy logs drowning out event lines.

## Export OpenAPI Schemas
- After modifying API routes, regenerate the schema via `python scripts/export_openapi.py` (or `make build-report`, which runs it as part of the bundle).
- Artifacts land in `artifacts/api_schema.json`; publish alongside release notes so integrators can refresh their clients.
- If the API host/port moves, update `.env`/environment values before exporting so the URLs in the schema remain accurate.
