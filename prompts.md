
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
