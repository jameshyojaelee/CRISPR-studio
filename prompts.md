
### Prompt 2: Graceful Native Enrichment Fallback with Telemetry
You own `src/crispr_screen_expert/pipeline.py` and `src/crispr_screen_expert/native/enrichment.py`. Make native enrichment truly optional:
1. Catch `DataContractError` from `native_enrichment.run_enrichment_native`, log it with library names, and fall back to `run_enrichr` automatically. Reserve hard failures for genuine input issues (e.g., empty significant gene lists already handled earlier).
2. Emit structured warnings in the pipeline result so downstream UIs can surface “native library missing” vs “native backend crashed.” Include these warnings in the log_event payload for `analysis_failed`/`analysis_completed`.
3. Extend tests (`tests/test_native_enrichment.py` and `tests/test_pipeline_reliability.py`) to cover scenarios where unsupported library names are supplied or the native backend raises runtime errors.
4. Document the workflow in `docs/reference/mageck/README.md` (or add a new section) explaining how bundled native libraries differ from Enrichr sets and how the fallback works.
Acceptance: turning on `--use-native-enrichment` never aborts an analysis solely because the native set is unavailable; warnings clearly cite the root cause and appear in tests.

### Prompt 3: Dash App Pipeline Settings Parity
Bring the Dash UI (`src/crispr_screen_expert/app/callbacks.py` + layout components) to parity with the CLI/API:
1. Add UI controls for MAGeCK toggle, native RRA/enrichment toggles, Enrichr library selection, and “skip annotations.” Persist selections in `dcc.Store` state.
2. Thread those settings into `_run_pipeline_job` by constructing `PipelineSettings` that mirror the CLI defaults. Ensure environment overrides (`CRISPR_STUDIO_FORCE_PYTHON`, etc.) still apply.
3. Display the active settings in the job status overlay and store completed run metadata so history cards show which backend produced each artifact.
4. Write Cypress-style Dash tests (`tests/test_dash_integration.py`) that flip these toggles and confirm the pipeline receives them (mock `run_analysis`).
5. Update CSS/UX as needed so the new controls fit the upload tab without breaking responsiveness.
Acceptance: users can choose the same execution paths in the UI as via CLI, and tests assert the settings are honored.

### Prompt 4: JobManager Lifecycle & Observability Upgrade
Improve `src/crispr_screen_expert/background.py`-based job handling for both Dash and FastAPI surfaces:
1. Track job metadata (submitted, started, finished timestamps, exception info) in a dedicated dataclass. Remove finished/failed futures from `_jobs` to prevent unbounded growth; keep a capped history (e.g., last 50 jobs) for status queries.
2. Add optional callbacks for completion so API layer can plug in analytics/logging without duplicating logic in callbacks.py and api.py.
3. Guard `result()`/`exception()` calls with error handling so unknown job IDs raise a clear custom exception.
4. Introduce tests in `tests/test_api.py` (or a new test file) to simulate many jobs and assert futures are cleaned up while metadata remains accessible for completed jobs.
Acceptance: running 500 sequential jobs does not grow memory linearly, and coverage proves cleanup works.

### Prompt 5: Simplify Pipeline DataPaths Usage
The `DataPaths` NamedTuple currently carries a metadata path that isn’t consumed. Align config loading logic:
1. Decide on one of two approaches and implement it consistently:
   - Remove `metadata` from `DataPaths` and adjust all call sites/tests/scripts accordingly, OR
   - Teach `run_analysis` to lazily load `ExperimentConfig` from `paths.metadata` when `config` isn’t provided (and ensure callers don’t double-parse).
2. Whichever path you take, update typing hints, docs, and tests (CLI, API, Dash, scripts) so there’s a single authoritative flow for metadata.
3. Add regression tests ensuring mismatched config/path combinations raise a clear error.
Acceptance: no caller needs to fabricate dummy metadata paths; there’s exactly one place where metadata JSON is parsed.

### Prompt 6: Trim Core Dependencies & Package Extras
`psutil` is only used by benchmarking scripts but is pulled into the core install. Clean that up:
1. Move psutil into a new optional extra (e.g., `[benchmark]`) or reuse `[dev]`, and guard imports in `scripts/benchmark_pipeline.py` with a helpful error message if the extra isn’t installed.
2. Document the extra in README + docs, and add a Makefile target (`make benchmark`) that installs `.[benchmark]` before running scripts.
3. While touching packaging, audit other optional tooling (e.g., weasyprint, kaleido) to ensure they’re either extras or clearly marked as optional runtime deps.
4. Add packaging tests (could be simple `pip install .` in CI) to ensure extras resolve.
Acceptance: a fresh `pip install crispr_screen_expert` only brings in what core pipeline needs; benchmarking instructions explain how to pull extras.

### Prompt 7: Regression Test Suite for Fallback & Warnings
Create a battery of tests to cover the new behaviors:
1. Add tests ensuring analytics `log_event` is invoked for each failure/success path, including new warning payloads from native fallback and annotation batching.
2. Build synthetic datasets in `tests/test_pipeline_demo.py` that exercise multiple warning combinations (native fallback + annotation chunk skip) and assert the final `AnalysisResult.warnings` contains de-duplicated, ordered entries.
3. Add snapshot-based checks for CLI output when MAGeCK is toggled off vs on, using `pytest` capsys.
Acceptance: coverage increases over pipeline + analytics modules, and CI proves warnings/logging behave as expected.

### Prompt 8: Documentation & Playbooks
Round up all behavioral changes into documentation deliverables:
1. Update README quickstart, `docs/demo_runbook.md`, and `docs/developer_guide.md` to include the new Dash controls, fallback logic, and dependency extras.
2. Create a troubleshooting appendix (`docs/troubleshooting.md`) mapping common warnings (native library missing, annotation batch failures, cache corruption) to remediation steps.
3. Add a short playbook in `docs/runbooks/operations.md` describing how to monitor JobManager health, rotate analytics logs, and export OpenAPI schemas after pipeline upgrades.
Acceptance: docs clearly walk through the enhanced controls, fallbacks, and operational steps so demo users and engineers stay aligned.
