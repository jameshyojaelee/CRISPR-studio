# Codex Execution Prompts for CRISPR-studio

Use these prompts sequentially with GPT-5-Codex. Each one assumes the prior steps are complete; never delete or overwrite existing work unless explicitly asked. Keep `overview.md` untouched.

## Prompt 01 – Project Dissection & Architecture Plan

Read `overview.md` closely and respond with a detailed architecture brief for CRISPR-studio. Summarize product requirements (QC automation, MAGeCK-based hit calling, pathway enrichment, gene annotations, LLM narratives, interactive reporting, advanced options, demo goals, monetization context, out-of-scope items). Propose a Python-centric architecture (ingestion layer, analysis pipeline, enrichment services, narrative generator, visualization layer, Dash UI) and map key data flows. List recommended dependencies and justify choices (pandas, numpy, scipy, scikit-learn, gseapy, plotly, dash, etc.). Produce a 4-week execution roadmap referencing the metrics in the overview (accuracy parity with published dataset, sub-minute demo run, UI clarity). Identify top risks (algorithm misfit, data privacy, LLM hallucinations, performance) with mitigation strategies. Output in Markdown under sections: Product Understanding, System Architecture, Data Contracts, Technology Stack, Execution Plan, Risk Register, Out-of-Scope Confirmation.

## Prompt 02 – Repository Scaffolding & Tooling

Initialize the project skeleton without disturbing existing files. Create:
- `pyproject.toml` using PEP 621 for package `crispr_screen_expert` (Python 3.11), declaring runtime deps: pandas, numpy, scipy, scikit-learn, plotly, dash, dash-bootstrap-components, gseapy, mygene, requests, typer, jinja2, weasyprint, pydantic, pydantic-settings, loguru. Add optional extras `dev` (pytest, pytest-cov, ruff, mypy, types-requests), `docs` (mkdocs, mkdocs-material), `llm` (openai).
- `.gitignore` (Python + Dash app artifacts), `LICENSE` (MIT), `README.md` with project overview, quickstart placeholders, and table referencing forthcoming docs.
- `Makefile` exposing targets: `install`, `lint` (ruff + mypy), `format` (ruff --fix), `test`, `run-app`, `build-report`, `clean`.
- `src/crispr_screen_expert/__init__.py` exporting `__version__`.
- `setup.cfg` configuring pytest, mypy strict mode, and ruff rules (enable E, F, I; select pydocstyle Google convention).
Ensure README mentions Python 3.11, virtualenv instructions, Makefile usage, and cites `overview.md` as background.

## Prompt 03 – Data Contracts & Demo Dataset

Document input expectations and create synthetic demo data.
- Write `docs/data_contract.md` describing required files: sgRNA count matrix (CSV/TSV with guides as rows, samples as columns), library annotation (guide_id,gene_symbol,optional_weight), experiment metadata (JSON with sample roles, replicate groups, screen type).
- Create `sample_data/demo_counts.csv`, `sample_data/demo_library.csv`, `sample_data/demo_metadata.json` representing a small viability screen (2 controls, 2 treatments, 12 guides targeting 4 genes plus non-targeting controls). Keep numbers plausible (counts 0-50k).
- Add `scripts/generate_demo_dataset.py` that can regenerate deterministic synthetic datasets with configurable gene hits and noise (use numpy random seed). Include CLI usage instructions in script docstring.
- Update README Quickstart with a “Demo Dataset” subsection pointing to the sample files and generator script.

## Prompt 04 – Domain Models & Validation Schema

Implement `src/crispr_screen_expert/models.py` using Pydantic models for:
- `SampleConfig` (sample_id, condition, replicate, role, file_column).
- `ExperimentConfig` (screen_type: dropout/enrichment, control_conditions, treatment_conditions, advanced options like fdr_threshold, scoring_method, enable_llm, enable_pathway).
- `GuideRecord`, `GeneResult`, `PathwayResult`, `QCMetric`, `QCFlag`, `NarrativeSnippet`, `AnalysisSummary`, `AnalysisResult`.
Include enums where appropriate, docstrings describing business meaning, and convenience methods for status labels (e.g., QCMetric.ok property). Validate metadata (unique sample ids, replicates grouped, consistent library keys). Export a helper `load_experiment_config(path: Path)`.

## Prompt 05 – Data Loading Utilities

Create `src/crispr_screen_expert/data_loader.py` with functions:
- `load_counts(path: Path) -> pd.DataFrame` (index guides, columns samples, detect delimiter, coerce numeric, handle missing guides with warnings).
- `load_library(path: Path) -> pd.DataFrame` (ensure guide_id uniqueness, uppercase gene symbols, optional weight column).
- `load_metadata(path: Path) -> ExperimentConfig`.
- `match_counts_to_library(counts, library)` returning filtered counts, missing guide report, and a merged DataFrame ready for analysis.
Add graceful error handling (raise custom `DataContractError` defined here), logging placeholders, and type hints. Ensure functions keep order, align replicates, and validate that metadata sample columns exist in counts.

## Prompt 06 – Quality Control Metrics Module

Implement `src/crispr_screen_expert/qc.py` providing:
- `compute_replicate_correlations(counts, metadata)` using log-normalized counts and returning Pearson r per condition pair plus interpretation (Excellent/Warning/Fail thresholds).
- `compute_guide_detection(counts, min_count=10)` reporting fraction of guides per sample above threshold.
- `compute_library_coverage(counts, library)` summarizing coverage per gene and identifying missing guides.
- `evaluate_controls(counts, metadata)` verifying control stability (e.g., median absolute deviation).
Each function should return `QCMetric` instances with numeric value, threshold metadata, and recommended action messages (e.g., “Consider re-running library prep”). Provide a `run_all_qc(...) -> List[QCMetric]` aggregator.

## Prompt 07 – Normalization & Replicate Handling

Add `src/crispr_screen_expert/normalization.py` with routines:
- `normalize_counts_cpm(counts)` (counts per million, pseudo-count 1).
- `aggregate_replicates(counts, metadata, method="median")`.
- `compute_log2_fold_change(normalized_counts, metadata)` returning guide-level log2FC for treatment vs control.
- `compute_gene_stats(log2fc, library)` aggregating guides per gene (mean, median, variance).
Handle dropout vs enrichment screens by sign conventions. Include clear docstrings and ensure functions are composable for pipeline orchestration.

## Prompt 08 – MAGeCK Integration Layer

Create `src/crispr_screen_expert/mageck_adapter.py` encapsulating MAGeCK CLI calls:
- Detect `mageck` binary via `shutil.which`; expose `is_available()`.
- Implement `run_mageck(counts_path, metadata, output_dir, library_path=None, kwargs)` writing temporary files as needed and invoking subprocess with robust error handling and timeout.
- Parse MAGeCK gene summary output into pandas DataFrame with columns gene, score, pval, fdr, rank.
- Surface warnings if MAGeCK missing; advise fallback.
Include detailed logging, docstrings referencing overview requirements, and ensure the adapter does not crash when MAGeCK absent (returns None, pipeline will use fallback).

## Prompt 09 – Robust Rank Aggregation Fallback

Implement `src/crispr_screen_expert/rra.py` providing a pure-Python fallback resembling MAGeCK-RRA:
- Accept guide-level log2FC and p-values; compute per-gene rankings, perform RRA (use algorithm from MAGeCK paper).
- Include multiple testing correction (Benjamini-Hochberg) and effect size summaries.
- Offer configuration for weighting guides (from library weights) and minimum guide count thresholds.
- Return DataFrame compatible with MAGeCK output structure so downstream code can be agnostic.
Document assumptions and cite the MAGeCK algorithm in comments.

## Prompt 10 – Analysis Result Assembly

Create `src/crispr_screen_expert/results.py` housing utilities to transform raw computations into domain models:
- `build_analysis_summary(...) -> AnalysisSummary` capturing counts of guides, significant hits, QC health flags, runtime statistics.
- `merge_gene_results(gene_df, qc_metrics, narrative)` returning `AnalysisResult`.
- Functions to select top hits, format volcano plot payloads, compute per-condition statistics for UI tables.
Ensure outputs align with `models.AnalysisResult` schema and include helpful docstrings.

## Prompt 11 – Pathway Enrichment Pipeline

Develop `src/crispr_screen_expert/enrichment.py`:
- Use gseapy (fallback to hypergeometric with goatools if unavailable) to run enrichment on significant genes against GO, KEGG, Reactome.
- Support configurable background (all screened genes) and adjustable FDR threshold.
- Provide caching of enrichment results per run (optional local JSON).
- Return list of `PathwayResult` models with effect direction, overlapping genes, q-values, citations (link to source database).
Include guardrails for small gene sets and note in docstring that pathway enrichment is optional per user toggle.

## Prompt 12 – Gene Annotation Service

Create `src/crispr_screen_expert/annotations.py`:
- Implement `fetch_gene_annotations(genes: Iterable[str])` using MyGene.info (requests) with retries and rate limiting.
- Provide offline fallback using a bundled minimal gene summary CSV (generate from MyGene for common genes in sample dataset).
- Normalize responses into consistent dict (symbol, name, summary, entrez, uniprot, pathways).
- Cache results locally (`.cache/gene_cache.json`).
Return `Dict[str, GeneAnnotation]` matching models. Log API usage counts for later analytics.

## Prompt 13 – Narrative Generation Engine

Add `src/crispr_screen_expert/narrative.py`:
- Provide `generate_narrative(result: AnalysisResult, settings)` that stitches together QC findings, top hits, pathway insights.
- If `settings.enable_llm` and `OPENAI_API_KEY` present, call OpenAI (or generic LLM) with prompt templates summarizing top findings, including guardrails to require citations. Handle API failures gracefully.
- Always include deterministic fallback summary built from templated strings referencing results metrics.
- Return `NarrativeSnippet` objects (title, body, source, type) for UI rendering.
Include instructions in README about configuring API keys and disclaimers about AI-generated text.

## Prompt 14 – Pipeline Orchestrator

Implement `src/crispr_screen_expert/pipeline.py` exposing `run_analysis(config: ExperimentConfig, paths: DataPaths, settings) -> AnalysisResult`:
- Stages: load data, QC, normalization, scoring (MAGeCK or RRA fallback), gene assembly, enrichment, annotations, narrative, result packaging.
- Each stage logs progress, records runtime stats, and collects warnings/errors for the UI.
- Persist intermediate artifacts in a timestamped output directory (`artifacts/<timestamp>/`) including normalized counts, gene results CSV, QC JSON, enrichment CSV.
- Return fully populated `AnalysisResult`.
Add exception handling to convert failures into structured error messages without crashing the UI.

## Prompt 15 – Command Line Interface

Create `src/crispr_screen_expert/cli.py` using Typer:
- Commands: `run-pipeline` (accept paths to counts/library/metadata, output dir, toggles), `validate-data`, `list-artifacts`.
- Optionally accept `--use-mageck/--no-use-mageck`, `--enable-llm`, `--fdr-threshold`.
- Integrate progress reporting (rich progress or textual updates) and print summary table at completion.
- Register entry point in `pyproject.toml` under `[project.scripts]` as `crispr-screen-expert=crispr_screen_expert.cli:app`.
Update README with CLI usage examples leveraging demo dataset.

## Prompt 16 – Unit Test Suite

Set up `tests/` with pytest:
- Fixtures in `tests/conftest.py` to load demo dataset and synthetic configs.
- Tests covering data loader validation, QC computations, normalization outputs, RRA fallback calculations (use small hand-crafted inputs).
- Ensure tests assert both numeric values and QC flag classifications.
- Configure pytest to run with coverage report; update Makefile `test` target to call `pytest --cov=crispr_screen_expert`.

## Prompt 17 – Integration Test & Benchmark Harness

Add `tests/test_pipeline_demo.py` running full pipeline on the synthetic demo dataset. Assert:
- Pipeline completes without exceptions.
- At least one known positive gene (e.g., BRCA2) appears in top hits with FDR < 0.1.
- QC metrics mark replicate correlations as Excellent.
Create `scripts/benchmark_pipeline.py` to measure runtime on demo dataset and log results for instrumentation (target < 30s). Document how to run these in README.

## Prompt 18 – Visualization Utilities

Implement `src/crispr_screen_expert/visualization.py` with Plotly figure factories:
- Volcano plot with significance shading and top gene labels.
- Replicate correlation scatter with trendline and QC badge overlay.
- Guide coverage bar chart, library detection heatmap, pathway enrichment bubble chart.
Functions should accept pandas data frames, return Plotly Figure objects, and include tooltip formatting for UI reuse. Provide unit tests verifying figure structure (data traces count).

## Prompt 19 – Dash Application Skeleton

Create Dash app structure under `src/crispr_screen_expert/app/`:
- `__init__.py` defining `create_app()`.
- `layout.py` building overall layout with navigation tabs: Upload, Results, QC, Pathways, Reports.
- `ids.py` centralizing component IDs.
- `state.py` for storing session-level state (dcc.Store usage).
- `app.py` at project root to run the Dash server (import create_app, expose `server` for WSGI).
Use Dash Bootstrap Components for styling and set a consistent theme aligned with "CRISPR-studio" branding.

## Prompt 20 – Upload & Configuration UI

Implement UI components and callbacks for data ingestion:
- Drag-and-drop uploaders for counts/library/metadata (accept CSV/TSV/JSON).
- Metadata form letting users map columns to roles, choose screen type, set advanced options (FDR threshold, scoring method).
- Validation feedback (alerts summarizing issues) before enabling “Run Analysis” button.
- Persist uploaded files to a temporary directory and reflect configuration in dcc.Store.
Ensure callbacks connect to backend validators and display helpful messages referencing `docs/data_contract.md`.

## Prompt 21 – Results Dashboard & QC Visualization

Build callbacks/pages to display pipeline outputs:
- Summary cards (number of significant genes, runtime, QC status).
- Volcano plot, gene table with sorting/filtering, download buttons (CSV export).
- QC tab showing replicate correlations, detection rates, and textual interpretations from `QCMetric`.
- Pathway tab embedding enrichment bubble chart and table with filter controls.
Implement caching of figures to avoid recomputation on each callback.

## Prompt 22 – Gene Detail & Exploration Interactions

Add interactive gene exploration features:
- Clicking a volcano plot point or table row opens a sidebar/modal with gene annotation (from `annotations`), guide-level metrics, pathway memberships, and LLM narrative snippet.
- Include quick links to PubMed/MyGene.
- Provide toggles to compare gene performance across replicates and show raw counts.
Ensure accessibility (keyboard focus) and responsive design.

## Prompt 23 – Report Generation & Export

Implement `src/crispr_screen_expert/reporting.py`:
- Use Jinja2 templates in `templates/report.html` to render complete analysis summary (QC, hits, pathways, narrative).
- Provide functions `render_html(result)` and `export_pdf(result, output_path)` (using WeasyPrint if available; otherwise fall back to HTML).
- Integrate with Dash: "Download Report" button triggers background generation and serves file.
Include templated sections for manual annotations and highlight disclaimers about AI-generated text.

## Prompt 24 – Background Jobs & Caching

Introduce asynchronous job handling so heavy analyses do not block the UI:
- Implement `src/crispr_screen_expert/background.py` using `ThreadPoolExecutor` (or RQ if available) managing job queue, status polling, cancellation.
- Store job metadata (start time, state, warnings) and provide Dash callbacks to poll status.
- Cache recent results keyed by dataset hash to enable instant reloads of the same files.
Ensure thread safety and clean shutdown on app exit.

## Prompt 25 – Configuration Management & Logging

Create `src/crispr_screen_expert/config.py` using `pydantic-settings` for environment-driven settings (data directories, default thresholds, API keys). Add `logging_config.py` configuring structured logs via loguru (console + rotating file in `logs/`). Update pipeline and CLI to use shared logger. Document environment variables (.env) in README.

## Prompt 26 – User Documentation

Author `docs/user_guide.md` covering:
- Installation (Makefile workflow, virtualenv).
- Running the CLI with demo data.
- Launching the Dash app, uploading data, interpreting each section.
- Explaining QC badges, significance thresholds, pathway analysis interpretation, AI narrative caveats.
- Troubleshooting (common data contract violations, MAGeCK missing).
Link screenshots placeholders (describe what to capture later).

## Prompt 27 – Developer Documentation

Produce `docs/developer_guide.md` summarizing architecture, module responsibilities, data flow diagrams (ASCII), coding conventions (type hints, docstrings, logging). Include instructions for adding new scoring methods, extending pathway catalogs, writing tests, and using the benchmark script. Reference risk mitigations and non-goals.

## Prompt 28 – Roadmap & Success Metrics

Create `docs/roadmap.md` mapping out backlog items across 4-week timeline:
- Week 1: scaffolding, data ingestion, QC.
- Week 2: scoring, enrichment, CLI, tests.
- Week 3: Dash UI, reports.
- Week 4: polish, demo rehearsal, beta outreach.
Include success metrics from overview (accuracy vs published data, run time, UI clarity, beta interest) and note stretch goals (LLM summaries, on-prem deployment options).

## Prompt 29 – Security & Privacy Guidelines

Add `docs/security_privacy.md` summarizing data handling policies:
- No long-term storage of uploads unless user exports.
- HTTPS and authentication expectations for deployment.
- API usage (MyGene, OpenAI) with minimal data sharing.
- Guidance for on-prem installations.
Reference privacy concerns highlighted in overview and include checklist for reviewers.

## Prompt 30 – Continuous Integration Pipeline

Introduce GitHub Actions workflow `.github/workflows/ci.yml`:
- Run on push/pull_request.
- Jobs: `lint` (ruff + mypy), `tests` (pytest with coverage), `build-docs` (mkdocs build).
- Cache pip dependencies, set Python 3.11, fail fast on lint/test errors.
Update README with CI badge placeholder and instructions for local lint/test commands.

## Prompt 31 – Containerization & Deployment Aids

Create `Dockerfile` (multi-stage: builder installs dependencies, final image runs Dash app) and `docker-compose.yml` to launch app plus optional worker (background jobs). Include environment variable examples and volumes for `artifacts/`. Update README with docker usage instructions (build, run, bind port 8050).

## Prompt 32 – Marketing & Landing Page Content

Develop `docs/marketing_assets.md` containing:
- Landing page copy (hero statement echoing “CRISPR screen results at your fingertips”).
- Feature list targeting biologists (analysis to insights, QC guardrails, AI narratives).
- Value props for core facilities and biotech teams, referencing monetization notes.
- Screenshots/storyboard descriptions for future design.
Include call-to-action ideas (Request demo, Upload pilot screen).

## Prompt 33 – Demo Runbook & Slide Outline

Create `docs/demo_runbook.md` translating the 3-minute script into actionable steps:
- Pre-demo setup checklist (pre-run pipeline, load dataset, ensure caches).
- Live narration cues per UI section with timing.
- Backup plan (switch to precomputed results).
- Slide outline summarizing problem, solution, impact metrics.
Link to assets generated by reporting module for insertion into slides.

## Prompt 34 – Go-To-Market Outreach Plan

Author `docs/go_to_market.md` expanding on channels listed in overview:
- Personal network outreach templates (email script, lab demo agenda).
- Online forum posts drafts (Biostars, r/labrats) showcasing before/after pain relief.
- Conference abstract bullet points and social media snippet.
- Pricing thought starters (freemium tiers, on-prem licensing).
Tie each channel to metrics (e.g., target 3 pilot labs) and include timeline.

## Prompt 35 – Usage Analytics & Feedback Loop

Implement lightweight analytics respecting privacy:
- Add `src/crispr_screen_expert/analytics.py` to log anonymized events (analysis_started, analysis_completed, qc_warning) to CSV/JSON for future review.
- Integrate with pipeline and Dash callbacks (opt-in toggle in config, default off).
- Provide CLI command to summarize analytics (counts, average runtime).
- Document opt-in process in user guide and note compliance with privacy guidelines.

## Prompt 36 – Beta Feedback & Iteration Tracker

Create `docs/beta_feedback_plan.md` outlining:
- How to recruit early adopters (from go-to-market plan).
- Structured feedback form (usability, accuracy, desired features).
- Process for triaging feedback into roadmap (using labels like `bug`, `enhancement`, `education`).
- Success criteria before public launch (e.g., 3 labs complete analysis, 90% positive QC trust rating).
Update roadmap to reference this feedback loop where appropriate.
