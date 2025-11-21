# Changelog

## 0.3.0 — Packaging polish & onboarding

- Enforced Python 3.11+ across docs, Makefile, CI (3.11/3.12 matrix), and Docker; refreshed PyPI metadata (keywords, URLs, badges) and added a slim CPU-only image target with optional native build arg.
- Added Colab-friendly notebook (`notebooks/quickstart.ipynb`) with headless test, plus `docs/notebooks.md` and a new performance guide.
- Shipped FastAPI client example (`examples/api_client.py`), `make api-example`, and cURL snippets in the README/developer guide; added lightweight unit test.
- Hardened onboarding with data contract templates, `scripts/validate_dataset.py` (fix checklist + manifest export), and happy-path/failure tests.
- Polished Dash UI: QC/warning tooltips, rerun-last-dataset button reusing cached uploads, and a bundled sample report link.
- Extended benchmarking (`--jsonl`, `--plot`) with optional CI artifact upload and documented expectations in `docs/performance.md`.
- Added community readiness: Code of Conduct, contributing guide, issue/PR templates, lint-fix target, and README community/help-wanted links.

## 0.2.0 — Polished Reporting Suite

- Reimagined the HTML report template with executive summary KPIs, SVG charts, and severity-grouped QC tables.
- Added multi-page PDF export (cover, summaries, appendix) powered by WeasyPrint with Plotly SVG embeds.
- Introduced `make build-report` to generate `artifacts/latest_report/` and a shareable sample bundle.
- Surfaced the sample bundle in the Dash Reporting Studio tab for one-click download.
- Bumped the package to `0.2.0` and added `kaleido` plus Dash testing support to dependencies.
- Released a secured FastAPI service (`/v1`) with CLI/docker entrypoints, OpenAPI export, and integration tests.
