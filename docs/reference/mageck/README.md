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
