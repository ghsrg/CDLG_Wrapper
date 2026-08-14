# CDLG Adapter MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a configuration-driven external-process adapter that turns one CDLG collection log into a validated versioned XES dataset bundle, plus BPMN/PTML and reproducibility evidence consumable by `bpm_prediction`.

**Architecture:** The wrapper never imports CDLG. It creates an ignored disposable runtime copy, renders CDLG's existing `src/input_parameters/default`, invokes `generate_collection_of_logs.py`, and parses only generated files. Benchmark-owned modules then assign versions, reconstruct/export structures, enrich lifecycle/time/resource data, build one XES, and publish a staged bundle only after validation.

**Tech Stack:** Python 3.10+, PM4Py, PyYAML, standard library (`dataclasses`, `subprocess`, `pathlib`, `logging`, `hashlib`), pytest.

**Canonical references:** `docs/wrapper-design.md`, `AGENTS.md`, `docs/PRINCIPLES.md`.

---

## File map

| Path | Responsibility |
| --- | --- |
| `requirements.txt` | Wrapper-owned, pinned direct dependencies. |
| `configs/cdlg_experiment.yaml` | Publishable default first-experiment input. |
| `wrapper/config.py` | Immutable configuration schema, defaults, YAML loading, and validation. |
| `wrapper/errors.py` | Typed expected failures and CLI exit-code mapping. |
| `wrapper/cdlg_runner.py` | Checkout verification, runtime-copy preparation, parameter rendering, subprocess execution, raw artifact capture. |
| `wrapper/cdlg_metadata.py` | Parse CDLG log/CSV metadata into version snapshots and trace boundaries. |
| `wrapper/structure.py` | PTML/BPMN export, deterministic BPMN identity normalization, process catalog. |
| `wrapper/enrichment.py` | Process-tree replay, lifecycle expansion, timing, resources, carryover. |
| `wrapper/xes.py` | Version attributes, global IDs, ordering, unified XES output. |
| `wrapper/evidence.py` | Manifests, reports, environment data, checksums, staged publication. |
| `wrapper/validation.py` | Strict bundle and semantic validation. |
| `wrapper/generate_benchmark.py` | Thin CLI and orchestrator. |
| `scripts/run_cdlg.ps1`, `scripts/run_cdlg.sh` | Thin platform launchers used by the runner. |
| `tests/` | Unit, semantic, artifact, failure-path, and slow end-to-end tests. |

### Task 1: Bootstrap the wrapper contract

**Files:**
- Create: `requirements.txt`
- Create: `wrapper/__init__.py`
- Create: `wrapper/errors.py`
- Create: `tests/test_errors.py`

- [ ] Write failing exit-code tests for configuration, CDLG, export/evidence, validation, and publication errors.

```python
from wrapper.errors import ConfigurationError, exit_code_for

def test_configuration_error_has_exit_code_two():
    assert exit_code_for(ConfigurationError("bad config")) == 2
```

- [ ] Run `python -m pytest tests/test_errors.py -v`; expect import failure.
- [ ] Implement `WrapperError`, the five typed subclasses, and `exit_code_for()`; keep unexpected exceptions mapped to `1`.
- [ ] Add direct dependencies `pm4py`, `PyYAML`, and test dependency `pytest` to `requirements.txt`; do not add CDLG as a dependency.
- [ ] Re-run the focused test; expect PASS.
- [ ] Commit: `git add requirements.txt wrapper tests/test_errors.py && git commit -m "chore: bootstrap wrapper package"`.

### Task 2: Implement configuration loading and exact allocation

**Files:**
- Create: `configs/cdlg_experiment.yaml`
- Create: `wrapper/config.py`
- Create: `tests/test_config.py`
- Create: `tests/test_trace_allocation.py`

- [ ] Write failing tests for defaults (`5` versions, `middle`, `0.2`, sudden/no-noise), invalid presets, non-positive totals, and quotient/remainder allocation.

```python
from wrapper.config import allocate_traces

def test_equal_allocation_is_exact_and_stable():
    assert allocate_traces(total_traces=17, version_count=5) == [4, 4, 3, 3, 3]
```

- [ ] Implement frozen dataclasses for `cdlg`, `dataset`, `lifecycle`, `resources`, `time`, `output`, and resolved version IDs. Reject any allocation containing zero traces.
- [ ] Render the default YAML with `Number_event_logs: 1`, `Number_drifts_per_log: version_count - 1`, `Drift_types: sudden`, `Noise: False`, and `Number_traces_per_process_model_version: ceil(total_traces / version_count)`. Store the exact quotient/remainder allocation as wrapper metadata.
- [ ] Preserve requested input separately from resolved derived values.
- [ ] Run `python -m pytest tests/test_config.py tests/test_trace_allocation.py -v`; expect PASS.
- [ ] Commit: `git add configs wrapper/config.py tests && git commit -m "feat: add validated benchmark configuration"`.

### Task 3: Verify and execute CDLG exclusively as an external process

**Files:**
- Create: `wrapper/cdlg_runner.py`
- Create: `scripts/run_cdlg.ps1`
- Create: `scripts/run_cdlg.sh`
- Create: `tests/test_cdlg_runner.py`

- [ ] Write failing tests using a temporary fake checkout for: wrong commit, dirty tracked worktree, missing GPL file, missing entry point, and non-zero child exit.
- [ ] Implement checkout verification with these commands: `git -C <checkout> remote get-url origin`, `git -C <checkout> rev-parse HEAD`, and `git -C <checkout> status --porcelain`.
- [ ] Implement a runtime-copy function that copies the checkout only into ignored `work/<run-id>/cdlg-runtime`, excluding `.git`, virtual environments, IDE data, and documentation. Never write into `CDLG/`.
- [ ] Render only the upstream line-based parameter file in the runtime copy. Invoke `<cdlg_python> generate_collection_of_logs.py` through the platform launcher, capture command, allowlisted environment, stdout, stderr, exit code, and elapsed time.
- [ ] Require exactly one raw XES and one drift CSV for `Number_event_logs: 1`; copy them unchanged into staging `raw/`.
- [ ] Run `python -m pytest tests/test_cdlg_runner.py -v`; expect PASS.
- [ ] Commit: `git add wrapper/cdlg_runner.py scripts tests && git commit -m "feat: add external CDLG runner"`.

### Task 4: Parse CDLG metadata and annotate process versions

**Files:**
- Create: `wrapper/cdlg_metadata.py`
- Create: `wrapper/annotate_versions.py`
- Create: `tests/test_cdlg_metadata.py`
- Create: `tests/test_annotate_versions.py`

- [ ] Build XES/CSV fixtures containing `process_trees`, drift boundaries, and five contiguous trace blocks.
- [ ] Write failing tests asserting ordered `v1..vN` tree snapshots, exact boundaries, and rejection of missing/ambiguous metadata.
- [ ] Parse CDLG log-level attributes and the raw drift CSV without importing CDLG. Map every raw trace to exactly one version, retain the configured exact count from each contiguous version block, and record discarded surplus traces without modifying the raw XES.
- [ ] Add `concept:version` to trace and event attributes. Preserve raw trace/event values in `raw/cdlg_output.xes`; do not overwrite it.
- [ ] Run focused metadata/annotation tests; expect PASS.
- [ ] Commit: `git add wrapper/cdlg_metadata.py wrapper/annotate_versions.py tests && git commit -m "feat: annotate CDLG traces by version"`.

### Task 5: Export structures and create the BPMN catalog

**Files:**
- Create: `wrapper/structure.py`
- Create: `tests/test_structure.py`

- [ ] Write failing tests for PTML and BPMN round-trips, one artifact per version, task-name equality with XES labels, and broken sequence-flow references after normalization.
- [ ] Parse every recovered process-tree string with PM4Py; export PTML and BPMN to `models/ptml/vK.ptml` and `models/bpmn/vK.bpmn`.
- [ ] Normalize BPMN IDs deterministically: task IDs from normalized label + stable hash; start/end fixed; gateway IDs from type, role, and canonical child signature; sequence-flow IDs from normalized endpoints. Rewrite every reference.
- [ ] Emit `models/process_definitions.csv` with deterministic process key, `proc_def_id`, version, and relative BPMN path.
- [ ] Run `python -m pytest tests/test_structure.py -v`; expect PASS.
- [ ] Commit: `git add wrapper/structure.py tests && git commit -m "feat: export version BPMN and PTML"`.

### Task 6: Add lifecycle, timing, resources, and natural carryover

**Files:**
- Create: `wrapper/enrichment.py`
- Create: `tests/test_enrichment.py`
- Create: `tests/test_process_tree_replay.py`

- [ ] Write failing semantic tests for sequence, XOR, parallel overlap, loop repetition, three lifecycle events when enabled, and no resource double-booking.
- [ ] Implement replay against the version's parsed process tree. Preserve the CDLG-selected activity occurrence sequence and fail when it cannot align to the tree.
- [ ] For each activity instance, create globally unique `concept:instance` and matching `sim:activity_instance_id`; emit `start` and `complete`, plus `assign` only when configured.
- [ ] Implement Poisson case arrivals, global lognormal durations, stable disjoint activity pools, least-workload tie-breaking, queueing, and one resource per instance. Give lifecycle events the same `org:resource`.
- [ ] Bind a case to its arrival version, allow in-flight completion after a later version activates, and report observed completion-version deltas. Use stable `assign -> start -> complete` timestamp ordering.
- [ ] Run focused enrichment tests; expect PASS.
- [ ] Commit: `git add wrapper/enrichment.py tests && git commit -m "feat: enrich execution lifecycle and resources"`.

### Task 7: Assemble one XES and produce reproducibility evidence

**Files:**
- Create: `wrapper/xes.py`
- Create: `wrapper/evidence.py`
- Create: `tests/test_xes.py`
- Create: `tests/test_evidence.py`

- [ ] Write failing tests for globally unique case IDs, event ordering, required attributes, artifact inventory, relative paths, and checksum mismatch detection.
- [ ] Implement unified XES assembly. Keep the trace order version-contiguous while retaining absolute timestamps; support disabled-by-default per-version debug XES exports.
- [ ] Write `configs/input.yaml`, `configs/resolved.yaml`, raw parameter copy, `manifest.json`, `environment.json`, `reports/processing.json`, `reports/methodology.md`, and SHA-256 checksums only after mutable files are closed.
- [ ] Ensure all publishable paths are relative and diagnostics contain no inherited environment secrets.
- [ ] Run focused XES/evidence tests; expect PASS.
- [ ] Commit: `git add wrapper/xes.py wrapper/evidence.py tests && git commit -m "feat: assemble dataset evidence bundle"`.

### Task 8: Validate and publish atomically

**Files:**
- Create: `wrapper/validation.py`
- Create: `tests/test_validation.py`

- [ ] Write failing tests that inject missing BPMN, wrong trace count, duplicate instance IDs, overlapping resource intervals, invalid BPMN references, and checksum tampering.
- [ ] Implement strict validator checks from `docs/wrapper-design.md`: version counts, XES attributes/lifecycle pairs, BPMN/PTML parseability, alignment uniqueness, resource capacity, artifact inventory, and checksums.
- [ ] Implement unique staging and final publication: failed runs remain in a marked failed directory with `failure.json` and traceback; successful runs publish once and never overwrite an existing dataset directory.
- [ ] Run `python -m pytest tests/test_validation.py -v`; expect PASS.
- [ ] Commit: `git add wrapper/validation.py tests && git commit -m "feat: validate and publish datasets"`.

### Task 9: Wire the CLI, diagnostics, and orchestration

**Files:**
- Create: `wrapper/generate_benchmark.py`
- Create: `tests/test_cli.py`
- Modify: `README.md`
- Modify: `docs/ROADMAP.md`

- [ ] Write failing CLI tests for `--config`, `--log-level`, success output, each expected exit code, and a failure report with component/stage context.
- [ ] Implement a thin `argparse` CLI and `GenerationOrchestrator` that calls Tasks 2–8 in design order. Configure `logs/run.log`, `logs/cdlg_stdout.log`, `logs/cdlg_stderr.log`, and chained traceback writing.
- [ ] Update README with exact setup/run commands and output layout; mark roadmap implementation status only after the corresponding tests pass.
- [ ] Run `python -m pytest tests/test_cli.py -v`; expect PASS.
- [ ] Commit: `git add wrapper/generate_benchmark.py tests README.md docs/ROADMAP.md && git commit -m "feat: add benchmark generation CLI"`.

### Task 10: Execute end-to-end and downstream compatibility acceptance

**Files:**
- Create: `tests/test_end_to_end.py`
- Create: `tests/test_bpm_prediction_compatibility.py`
- Modify: `docs/wrapper-design.md`
- Modify: `docs/ROADMAP.md`

- [ ] Add a slow real-CDLG test using the pinned checkout and `3 versions x 3 traces`; skip only when the external checkout/interpreter is intentionally unavailable.
- [ ] Assert the complete accepted bundle: unified XES, three BPMN/PTML files, raw artifacts, reports, evidence, and valid checksums.
- [ ] In the separate `bpm_prediction` environment, run the documented compatibility command against the bundle; assert XES pairing, file-based BPMN ingestion, `collapse_for_prediction`, and 100% unambiguous activity alignment.
- [ ] Run the complete wrapper suite: `python -m pytest tests -v`. Run the downstream smoke test separately with the `bpm_prediction` interpreter.
- [ ] Record observed constraints or CDLG behavior in the canonical design; do not silently change methodology. Mark the roadmap slice complete only after both acceptance commands pass.
- [ ] Commit: `git add tests docs && git commit -m "test: verify end-to-end adapter compatibility"`.

## Plan self-review

- **Spec coverage:** Tasks 2–10 cover the approved configuration, external boundary, sudden five-version chain, XES lifecycle/resource/timing, BPMN/PTML, evidence, diagnostics, validation, and `bpm_prediction` compatibility contracts.
- **Stock CDLG constraint:** CDLG takes one per-version trace count. Task 2 renders its ceiling value, while Task 4 deterministically retains the approved quotient/remainder allocation and records every discarded surplus trace in provenance.
- **No placeholders:** every task names files, acceptance behavior, focused command, and commit boundary.
- **Type consistency:** all downstream steps consume the resolved configuration, raw artifact record, version mapping, enriched trace records, and staged bundle defined by the preceding components.
