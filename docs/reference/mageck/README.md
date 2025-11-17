# MAGeCK Reference Templates

The CRISPR-studio pipeline primarily relies on automated reporting, but some
teams still prefer the stock MAGeCK HTML notebook for secondary review. The
files in this directory are the upstream MAGeCK report template and a small
helper script that renders it without leaving stray artefacts in the project
root.

## Usage

```bash
Rscript docs/reference/mageck/generate_report.R demo_run 0.05
```

This command renders `report_template.Rmd` with `comparison_name = "demo_run"`
and writes a `demo_run_report.html` notebook to the current working directory.
The optional second argument sets the FDR cutoff used in the diagnostic plots.

These resources are not wired into the automated build; they are here purely as
documentation for the original MAGeCK workflow.

## Native Enrichment vs. Enrichr Sets

CRISPR-studio ships a tiny set of curated “native” pathway libraries under
`resources/enrichment/native_demo.json`. These are bundled purely for offline
demos and are separate from the much larger Enrichr collections fetched via the
Python fallback. When the pipeline runs with `--use-native-enrichment`, it first
looks for those bundled libraries and, when present, uses the C++ backend for a
fast hypergeometric test. If a requested native library is missing or the native
backend cannot load, the pipeline records a structured warning (e.g.,
`native_enrichment_library_missing` or `native_enrichment_backend_failed`) and
automatically falls back to the Enrichr API so analyses continue without
interruption. These warnings are also emitted in telemetry (`analysis_completed`
/ `analysis_failed`) so dashboards can explain whether native resources were
unavailable or if the backend crashed mid-run.
