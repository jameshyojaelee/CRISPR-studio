# Changelog

## 0.2.0 — Polished Reporting Suite

- Reimagined the HTML report template with executive summary KPIs, SVG charts, and severity-grouped QC tables.
- Added multi-page PDF export (cover, summaries, appendix) powered by WeasyPrint with Plotly SVG embeds.
- Introduced `make build-report` to generate `artifacts/latest_report/` and a shareable sample bundle.
- Surfaced the sample bundle in the Dash Reporting Studio tab for one-click download.
- Bumped the package to `0.2.0` and added `kaleido` plus Dash testing support to dependencies.
- Released a secured FastAPI service (`/v1`) with CLI/docker entrypoints, OpenAPI export, and integration tests.
