# Security & Privacy Guidelines

## Data Handling Principles
- Uploaded files remain on the host filesystem; they are stored under the directory configured via `CRISPR_STUDIO__UPLOADS_DIR`. No automatic retention beyond analysis runs.
- Artifacts (normalised counts, QC metrics, gene results, annotations) live under `CRISPR_STUDIO__ARTIFACTS_DIR`. Users may delete runs via standard filesystem commands.
- Reports contain aggregated statistics only; raw FASTQ data is never retained by CRISPR-studio.

## Deployment Recommendations
- Serve Dash behind HTTPS with an authenticating proxy (e.g., Nginx + OAuth) when exposed beyond localhost.
- Restrict filesystem permissions so only authenticated users can read/write `uploads/`, `artifacts/`, and `logs/`.
- Rotate log files regularly (handled automatically via Loguru) and scrub logs before sharing externally.

## API Usage
- MyGene.info: queries include only gene symbols; no experimental data transmitted.
- OpenAI (optional): narratives send high-level gene summaries; never transmit raw counts. Toggle via CLI flag or `.env` key `OPENAI_API_KEY`.
- Enrichr/GSEA: only gene lists (top hits) are sent; no sample metadata.

## On-Premises Guidance
- For regulated environments, deploy the application within the organisation’s secure network.
- Provide a self-hosted Enrichr cache or run GSEA offline if external API calls are disallowed.
- Audit dependencies via `pip list --outdated` and monitor CVE feeds for core libraries (pandas, Dash, Plotly).

## Reviewer Checklist
- [ ] HTTPS enforced / reverse proxy configured
- [ ] File permissions limited to analysis team
- [ ] `.env` stored securely (never committed)
- [ ] Logs rotated & reviewed for sensitive content
- [ ] Optional analytics disabled unless explicitly approved
- [ ] LLM features disabled when handling confidential datasets
