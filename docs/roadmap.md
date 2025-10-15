# CRISPR-studio Roadmap

## Week 1 – Foundations
- ✅ Repository scaffolding, virtualenv workflow, logging configuration.
- ✅ Data contracts, demo dataset generator, unit test harness.
- ☐ Harden Dash upload experience with additional validation cues.

## Week 2 – Analysis Core
- ✅ Pipeline orchestration (MAGeCK + RRA fallback), QC metrics, enrichment, narrative generation.
- ✅ CLI with validation, run, and artifact management.
- ✅ Integration + benchmark scripts.
- ☐ Add regression tests using a published dataset to confirm accuracy parity.

## Week 3 – Experience Layer
- ✅ Dash UI skeleton with background jobs, caching, interactive gene modal, report downloads.
- ☐ Polish styling, add pathway filters and per-gene sparkline plots.
- ☐ Implement MAGeCK result visualisation once small-demo failure behaviour stabilises.

## Week 4 – Polish & Outreach
- ☐ Harden error messaging, add analytics opt-in controls.
- ☐ Prepare marketing assets and go-to-market outreach (see docs/go_to_market.md).
- ☐ Rehearse demo using `docs/demo_runbook.md`; capture screenshots for landing page.

## Success Metrics
- Hit overlap ≥80% with published reference datasets (MAGeCK parity) within Week 2.
- Sub-minute runtime on demo dataset; <5 minutes on genome-scale dataset.
- UI clarity: external tester completes workflow without guidance, no “what does this plot mean?” feedback.
- Beta interest: at least three labs commit to pilot during Week 4 outreach.

## Stretch Goals
- LLM narrative enhancements with citation extraction.
- On-prem deployment recipe (Helm chart + Airflow integration).
- Parameter sweeps / batch mode for large experiments.
