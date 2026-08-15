# CDLGW-006 End-to-End and bpm_prediction Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Execute the pinned CDLG checkout through the complete wrapper pipeline, atomically publish one validated small bundle, and prove that the separate `bpm_prediction` environment can ingest its XES and BPMN artifacts.

**Architecture:** `wrapper.orchestrator` will coordinate existing, benchmark-owned modules into a caller-provided staging directory; it must not reimplement their logic or import either external project. `wrapper.generate_benchmark` will invoke this orchestrator, while `tests/test_end_to_end.py` uses the real external CDLG process and `tests/test_bpm_prediction_compatibility.py` invokes the downstream interpreter solely through subprocesses. A successful bundle is promoted from `work/<run-id>/bundle` to `outputs/datasets/<run-id>`; a failed bundle is retained at `outputs/failed/<run-id>`.

**Tech Stack:** Python 3.10, PM4Py, PyYAML, pytest, `subprocess`, external pinned CDLG Python 3.10 environment, separate `bpm_prediction` `.venv-modern` environment.

---

**Plan ID:** `CDLGW-006` · **Status:** executed; closed without commit per user instruction.

## Sources and Authority

1. `AGENTS.md` — external CDLG/legal boundary, separate environments, no imports.
2. `docs/PRINCIPLES.md` — complete pipeline acceptance and reproducible evidence.
3. `docs/wrapper-design.md` — approved end-to-end flow, artifact layout, validation contract, and downstream smoke test.
4. `docs/ROADMAP.md` — `CDLGW-006-AC01` and `CDLGW-006-AC02`.
5. `docs/superpowers/plans/2026-08-14-cdlg-wrapper-mvp.md` Task 10 — real execution and downstream acceptance.
6. `C:\Users\korsr\PycharmProjects\bpm_prediction\AGENTS.md`, `docs/ADAPTER_XES.MD`, `docs/GNN_RUNTIME_MVP2_5.MD`, and `tools/ingest_topology.py` — separate downstream ingestion contract.

## Assumptions and Preconditions

- The ignored `CDLG/` checkout exists, is clean, has origin `https://gitlab.uni-mannheim.de/processanalytics/cdlg_tool`, and is pinned to `cbe1534de94f06a3f1cca460b079d436f604445e`.
- The real CDLG interpreter is supplied in the wrapper YAML as `cdlg.python_executable`; it is never activated or imported by wrapper Python.
- The real downstream smoke receives `BPM_PREDICTION_ROOT` and `BPM_PREDICTION_PYTHON` explicitly from the test environment. The latter must point to `.venv-modern\\Scripts\\python.exe` on Windows. Missing prerequisites fail the explicit integration command with diagnostics; they are not silently skipped.
- Published paths are intentionally implementation-owned: `work/<run-id>/bundle` for mutable staging, `outputs/datasets/<run-id>` for a successful bundle, and `outputs/failed/<run-id>` for a failed bundle. `run-id` is generated once per invocation and recorded in `manifest.json`.
- The generated `models/process_definitions.csv` will be extended compatibly with the file-based BPMN adapter columns `proc_def_id`, `proc_def_key`, `version`, `deployment_id`, and `bpmn_path`; existing wrapper validation continues to use `version` and `bpmn_path`.

## BDD Agent Scenario Cards

| ID | Priority | Given / When / Then | Independent verification | TDD obligation and evidence |
| --- | --- | --- | --- | --- |
| `CDLGW-006-AC01` | P0 | Given the clean pinned checkout and a 3-version, 9-trace YAML with the external CDLG Python executable, when `python -m wrapper.generate_benchmark --config <path>` runs, then exactly one complete validated bundle is published under `outputs/datasets/<run-id>`, contains the required raw/XES/BPMN/PTML/config/report/log evidence, and its checksum inventory verifies. | `pytest tests/test_end_to_end.py -v -m integration` plus direct CLI command. | RED/GREEN orchestration tests; real subprocess result is `CDLGW-006-EV01`. |
| `CDLGW-006-AC02` | P0 | Given the published AC01 bundle and the separate downstream interpreter, when the XES and file-based BPMN ingestion commands run, then lifecycle pairing by `concept:instance`, versions `v1..v3`, BPMN ingestion with `collapse_for_prediction`, and 100% version-scoped XES/BPMN activity alignment succeed. | `pytest tests/test_bpm_prediction_compatibility.py -v -m integration` with explicit downstream environment variables. | RED/GREEN generated-config and subprocess tests; downstream summaries are `CDLGW-006-EV02`. |
| `CDLGW-006-AC03` | P1 | Given any failure before publication, when the orchestration aborts, then no directory exists in `outputs/datasets/`, while one `outputs/failed/<run-id>` bundle retains `failure.json`, the chained traceback, raw evidence already available, and the failed stage/component. | `pytest tests/test_orchestrator.py -v`. | Inject one failure after raw capture and one after export; evidence `CDLGW-006-EV03`. |

## File Structure

| File | Responsibility |
| --- | --- |
| Create `wrapper/orchestrator.py` | Unique run ID/staging ownership and ordered composition of existing runner, metadata, annotation, export, enrichment, XES, evidence, validation, and publication components. |
| Modify `wrapper/generate_benchmark.py` | Replace the CDLGW-006 placeholder with the orchestrator boundary; retain CLI parsing and typed exit mapping. |
| Modify `wrapper/structure.py` | Emit a BPMN file-adapter-compatible catalog without changing deterministic BPMN/PTML output. |
| Modify `wrapper/evidence.py` | Finalize evidence only after all required artifacts exist: run trace, validation/alignment reports, downstream configs, manifest inventory, and checksums. |
| Modify `wrapper/validation.py` | Verify the finalized report/config content that CDLGW-006 produces, in addition to the existing path and integrity checks. |
| Modify `wrapper/config.py`, `configs/cdlg_experiment.yaml` | Add only the output/run identity values required to locate the run safely, preserve existing defaults, and require the real CDLG Python for an actual run. |
| Create `tests/test_orchestrator.py` | Fast, monkeypatched stage-order, staging, success, and failure-retention contract tests. |
| Create `tests/test_end_to_end.py` | Real, slow pinned-CDLG three-version fixture test; no fake CDLG process. |
| Create `tests/test_bpm_prediction_compatibility.py` | Separate-interpreter XES and file-BPMN ingestion smoke test through subprocess only. |
| Create `configs/cdlg_smoke.yaml` | Committed 3-version × 3-trace integration fixture, with the CDLG executable supplied only at invocation/test setup. |
| Modify `README.md`, `docs/wrapper-design.md`, `docs/ROADMAP.md` | Document actual command, output roots, required external environments, and status/evidence only after closure. |

## TDD Tasks

### `CDLGW-006-T01` — RED/GREEN orchestration and artifact finalization for `CDLGW-006-AC01`

**Files:** create `wrapper/orchestrator.py`, `tests/test_orchestrator.py`; modify `wrapper/generate_benchmark.py`, `wrapper/evidence.py`, `wrapper/config.py`, `configs/cdlg_experiment.yaml`.

- [ ] **RED:** Write `test_given_stage_results_when_orchestrated_then_staging_pipeline_order_and_published_path_are_exact`. Replace every external effect with injected fakes that append: `verify`, `runtime`, `run`, `metadata`, `annotate`, `structures`, `enrich`, `xes`, `metrics`, `evidence`, `validate`, `publish`. Assert the list exactly matches that order; assert `dataset.xes`, raw files, logs, reports, configs, structures, manifest, and checksums are passed to publication from one `work/<run-id>/bundle` directory.
- [ ] Run `\.venv\\Scripts\\python.exe -m pytest tests/test_orchestrator.py -k published -v`. Expected: FAIL because `wrapper.orchestrator` does not exist.
- [ ] **GREEN:** Add `run_generation_pipeline(config_path, resolved_config)` in `wrapper/orchestrator.py`. Generate a collision-resistant `run_id`; create only `work/<run-id>/bundle`; call `verify_checkout`, `prepare_runtime_copy`, `render_parameters`, `run_cdlg`, `parse_raw_metadata`, `annotate_versions`, `export_structures`, `enrich_traces`, `assemble_xes`/`write_xes`, drift metrics, evidence finalization, `validate_bundle`, and `publish_validated_bundle` in the approved data-flow order. Pass CDLG only its configured executable and disposable runtime path. Make `wrapper.generate_benchmark.run_generation_pipeline` delegate to this function.
- [ ] Run the focused test. Expected: PASS.
- [ ] **REFACTOR:** Keep orchestration dependency injection private to the module/test seam; do not add a wrapper import of CDLG or `bpm_prediction`. Add a dedicated `run.log` with stage start/end/status lines and close it before final checksums.
- [ ] Commit: `git add wrapper/orchestrator.py wrapper/generate_benchmark.py wrapper/config.py wrapper/evidence.py configs/cdlg_experiment.yaml tests/test_orchestrator.py && git commit -m "feat: orchestrate benchmark generation"`.

### `CDLGW-006-T02` — RED/GREEN downstream-ready catalog/config/report artifacts for `CDLGW-006-AC01` and `CDLGW-006-AC02`

**Files:** modify `wrapper/structure.py`, `wrapper/evidence.py`, `wrapper/validation.py`; extend `tests/test_structure.py`, `tests/test_evidence.py`, and `tests/test_validation.py`.

- [ ] **RED:** Add tests asserting that each process-definition row contains `proc_def_id=vK`, a stable `proc_def_key`, `version=vK`, a stable `deployment_id`, and bundle-relative `bpmn_path=bpmn/vK.bpmn`; assert emitted `configs/bpm_prediction_xes.yaml` maps `concept:name`, `time:timestamp`, `org:resource`, `lifecycle:transition`, `concept:version`, `concept:instance`, `start`, and `complete`; assert emitted `configs/bpm_prediction_bpmn.yaml` selects file BPMN ingestion with `structure_from_logs: false` and `gateway_mode: collapse_for_prediction`. Add tests that validation rejects non-JSON validation/alignment reports or a config whose required values are missing.
- [ ] Run `\.venv\\Scripts\\python.exe -m pytest tests/test_structure.py tests/test_evidence.py tests/test_validation.py -v`. Expected: FAIL on missing catalog columns/config/report semantic checks.
- [ ] **GREEN:** Extend catalog serialization compatibly, create both downstream configs and `reports/validation.json`/`reports/topology_alignment.json` from real stage outputs, include every final file in manifest inventory, then generate checksums after `run.log` closes. Add validator checks for report JSON objects/status and the fixed downstream mapping settings. Keep all paths relative to the bundle root.
- [ ] Run the focused suite. Expected: PASS.
- [ ] **REFACTOR:** Keep downstream YAML construction in evidence/config serialization, not in the CLI or the downstream repository. Re-check that no exported metadata contains an absolute workstation path.
- [ ] Commit: `git add wrapper/structure.py wrapper/evidence.py wrapper/validation.py tests/test_structure.py tests/test_evidence.py tests/test_validation.py && git commit -m "feat: emit downstream compatibility artifacts"`.

### `CDLGW-006-T03` — RED/GREEN failed-run preservation for `CDLGW-006-AC03`

**Files:** modify `wrapper/orchestrator.py`, `wrapper/publication.py`; extend `tests/test_orchestrator.py`, `tests/test_publication.py`.

- [ ] **RED:** Write parameterized tests injecting `ArtifactError` after `run_cdlg` and `ValidationError` after evidence finalization. Assert no `outputs/datasets/<run-id>` target, exactly one `outputs/failed/<run-id>`, `failure.json.status == "failed"`, component/stage identify the failing stage, `logs/traceback.txt` exists, and raw CDLG files remain if they were captured before the failure.
- [ ] Run `\.venv\\Scripts\\python.exe -m pytest tests/test_orchestrator.py tests/test_publication.py -k "failed or failure" -v`. Expected: FAIL because orchestration does not retain failures for all stages.
- [ ] **GREEN:** Wrap the orchestration state machine so every expected and unexpected failure before publication calls `retain_failure` once with the last completed stage/component, then re-raises the original typed error. Preserve only relative references in diagnostics and never overwrite an existing failed directory.
- [ ] Run the focused failure suite. Expected: PASS.
- [ ] **REFACTOR:** Do not catch `BaseException`; retain ordinary exceptions while preserving `KeyboardInterrupt` and `SystemExit` behavior.
- [ ] Commit: `git add wrapper/orchestrator.py wrapper/publication.py tests/test_orchestrator.py tests/test_publication.py && git commit -m "fix: retain failed generation bundles"`.

### `CDLGW-006-T04` — Real external CDLG execution for `CDLGW-006-AC01`

**Files:** create `configs/cdlg_smoke.yaml`, `tests/test_end_to_end.py`; modify `README.md` and `docs/wrapper-design.md` only after the command succeeds.

- [ ] **RED:** Add an `@pytest.mark.integration` test that resolves the configured CDLG executable, runs the wrapper CLI with a temporary copy of `configs/cdlg_smoke.yaml`, and asserts a returned directory under temporary `outputs/datasets/` contains exactly 3 BPMN, 3 PTML, 9 unified XES traces, raw XES/drift CSV/parameters, CDLG stdout/stderr, processing/methodology/validation/alignment reports, both downstream configs, and a valid checksum inventory.
- [ ] Run `\.venv\\Scripts\\python.exe -m pytest tests/test_end_to_end.py -v -m integration`. Expected before GREEN: FAIL at the unimplemented orchestration boundary.
- [ ] **GREEN:** Complete only the integration wiring required for the test. Execute the real pinned CDLG child process using its separate Python 3.10 executable; do not patch or write inside `CDLG/`. Capture the exact subprocess command, exit code, elapsed time, stdout/stderr paths, observed commit, and trace allocation in the evidence bundle.
- [ ] Run `\.venv\\Scripts\\python.exe -m pytest tests/test_end_to_end.py -v -m integration`. Expected: PASS with one published bundle and no modifications under `CDLG/`.
- [ ] Run the direct reproducibility command using a temporary smoke config: `\.venv\\Scripts\\python.exe -m wrapper.generate_benchmark --config <temporary-smoke-config>`. Expected: exit `0`, stdout is only the published bundle path.
- [ ] Commit: `git add configs/cdlg_smoke.yaml tests/test_end_to_end.py README.md docs/wrapper-design.md && git commit -m "test: verify real CDLG end-to-end run"`.

### `CDLGW-006-T05` — Separate `bpm_prediction` compatibility smoke for `CDLGW-006-AC02`

**Files:** create `tests/test_bpm_prediction_compatibility.py`; modify `README.md`, `docs/wrapper-design.md` after success.

- [ ] **RED:** Write a subprocess-only test that takes the published AC01 bundle plus `BPM_PREDICTION_ROOT` and `BPM_PREDICTION_PYTHON`. Run `tools/ingest_topology.py` twice from the downstream project: once with the bundle XES config and once with the file-BPMN config. Assert both return code `0`; the XES summary has `adapter == "xes"` and versions `v1`, `v2`, `v3`; the BPMN summary has `adapter == "camunda"`, `structure_source == "bpmn"`, `quarantined_procdefs == 0`, and the same versions. Assert the generated topology-alignment report records 100% activity coverage.
- [ ] Run `\.venv\\Scripts\\python.exe -m pytest tests/test_bpm_prediction_compatibility.py -v -m integration`. Expected before GREEN: FAIL because downstream configs/catalog are not yet executable against the real bundle.
- [ ] **GREEN:** Correct only wrapper-generated file paths, catalog columns, and mapping/config serialization needed for the two downstream subprocesses. Keep `bpm_prediction` unmodified; never add it to wrapper dependencies or `sys.path`.
- [ ] Run the compatibility test with the explicit separate interpreter environment. Expected: PASS.
- [ ] Run the downstream architecture guard separately: `C:\Users\korsr\PycharmProjects\bpm_prediction\.venv-modern\Scripts\python.exe C:\Users\korsr\PycharmProjects\bpm_prediction\tools\architecture_guard.py`. Expected: exit `0`.
- [ ] Commit: `git add tests/test_bpm_prediction_compatibility.py README.md docs/wrapper-design.md && git commit -m "test: verify bpm prediction compatibility"`.

### `CDLGW-006-T06` — Closure and evidence

**Files:** modify `docs/ROADMAP.md`, `README.md`, `docs/wrapper-design.md`; create ignored `outputs/worklogs/YYYY-MM-DD-HHMM-REPORT-CDLGW-006-end-to-end-compatibility.md`.

- [ ] Run wrapper unit and integration tests: `\.venv\\Scripts\\python.exe -m pytest tests -v` and `\.venv\\Scripts\\python.exe -m pytest tests/test_end_to_end.py tests/test_bpm_prediction_compatibility.py -v -m integration`.
- [ ] Run `\.venv\\Scripts\\python.exe -m compileall -q wrapper`, the wrapper import-boundary scan, `git diff --check`, and `git -C CDLG status --porcelain`; the last command must return no tracked modifications.
- [ ] Use `closure-verification` to record `CDLGW-006-EV01` through `CDLGW-006-EV04` with a coverage matrix for AC01–AC03. Mark CDLGW-006 complete in Roadmap only after all P0 scenarios have independent real-run evidence.
- [ ] Commit: `git add docs/ROADMAP.md README.md docs/wrapper-design.md && git commit -m "docs: close CDLGW-006 compatibility evidence"`.

## Evidence Map

| Evidence ID | Proof |
| --- | --- |
| `CDLGW-006-EV01` | Real pinned-CDLG 3-version × 3-trace CLI run and complete validated published bundle. |
| `CDLGW-006-EV02` | Two downstream subprocess summaries proving XES pairing and file-based BPMN ingestion/alignment. |
| `CDLGW-006-EV03` | Injected failure tests prove failed-run retention and absence of a published target. |
| `CDLGW-006-EV04` | Full wrapper suite, compile, boundary, diff, clean-CDLG, and closure-verification evidence. |

## Forbidden Scope

- CDLG source changes, copies into Git, imports, dependency installation, or modification of the pinned checkout.
- Any wrapper import, dependency, `sys.path` edit, or source change in `bpm_prediction`.
- Gradual drift, resource drift, noise, new timing methodology, or changes to approved first-experiment semantics.
- Training/evaluation in `bpm_prediction`; this slice ends at ingestion and structural compatibility.
- Publishing a partial bundle, overwriting an existing published/failed run, or skipping real integration prerequisites.

## Self-Review

- Spec coverage: AC01 maps to T01/T02/T04; AC02 maps to T02/T05; failure semantics map to T03; legal boundary and closure map to T04–T06.
- Placeholder scan: no deferred implementation placeholders; all external prerequisites are explicit test gates.
- Type consistency: the plan composes existing `ResolvedConfig`, `CdlgRunResult`, `RawMetadata`, `AnnotatedLog`, `EnrichedLog`, `ValidationReport`, and `Path` contracts. The orchestrator, rather than individual modules, owns run IDs and stage diagnostics.

Execution was authorized by the user request `EXECUTE CDLGW-006`; commit steps
were intentionally skipped because the user requested development in `main`
without a commit.
