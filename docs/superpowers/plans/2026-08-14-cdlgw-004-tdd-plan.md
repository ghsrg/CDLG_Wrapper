# CDLGW-004 Execution Enrichment and Unified XES Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn annotated CDLG activity traces into one versioned XES with lifecycle pairs, shared-timeline execution intervals, stable resources, and draft reproducibility evidence.

**Architecture:** `wrapper/enrichment.py` owns replay-compatible instance expansion, arrivals, durations, resource scheduling, and carryover observations. `wrapper/xes.py` owns only XES assembly/export. `wrapper/evidence.py` serializes the non-publishing evidence produced by these modules. Preserve raw XES and CDLG-selected activity occurrence order; do not import CDLG or `bpm_prediction`.

**Tech Stack:** Python 3.10, PM4Py XES APIs, standard-library `random`, `datetime`, `hashlib`, `json`, `csv`, PyYAML, pytest.

---

**Plan ID:** `CDLGW-004`  
**Status:** proposed; execution requires `OK EXECUTE CDLGW-004`.  
**Sources:** [Roadmap](../../ROADMAP.md#cdlgw-004-вЂ”-execution-enrichment-and-unified-xes), [Lifecycle/Resource/Time contracts](../../wrapper-design.md#lifecycle-contract), [XES contract](../../wrapper-design.md#required-xes-compatibility-contract), [MVP tasks 6-7](2026-08-14-cdlg-wrapper-mvp.md#task-6-add-lifecycle-timing-resources-and-natural-carryover).

## BDD Agent Scenario Cards

| ID | Priority | Given / When / Then | Evidence |
| --- | --- | --- | --- |
| `CDLGW-004-AC01` | P0 | Given annotated CDLG traces and their source process trees, when enriched, then every activity occurrence has exactly one `start` and `complete`, a global `concept:instance` equal to `sim:activity_instance_id`, one stable `org:resource`, and no overlapping work for that resource. | `CDLGW-004-EV01`: `pytest tests/test_enrichment.py tests/test_process_tree_replay.py -v` |
| `CDLGW-004-AC02` | P0 | Given enriched traces, when assembled, then one XES has globally unique case IDs, required version/lifecycle/resource/timestamp attributes, stable `assign -> start -> complete` ordering, version-contiguous traces, and globally comparable absolute timestamps. | `CDLGW-004-EV02`: `pytest tests/test_xes.py tests/test_evidence.py -v` |

Additional BDD checks: parallel branches overlap when their source tree permits it; XOR preserves the CDLG-selected branch; a loop occurrence is retained; optional `assign` is omitted by default; a later version may activate while an earlier case remains in flight; all published metadata paths are relative.

## File Structure

- Create `wrapper/enrichment.py`: immutable enriched records, replay validation, interval/resource scheduler, carryover summary.
- Create `wrapper/xes.py`: conversion of enriched records into a single PM4Py XES log and optional per-version debug logs.
- Create `wrapper/evidence.py`: draft configs, processing/environment/manifest records, methodology text, and checksums for closed files.
- Create `tests/test_process_tree_replay.py`, `tests/test_enrichment.py`, `tests/test_xes.py`, `tests/test_evidence.py`.
- Modify `wrapper/config.py`: add validated `temporal` and `output` config records only; maintain existing defaults.
- Modify `docs/ROADMAP.md` only after closure; update `README.md`/`docs/wrapper-design.md` only if the implemented config/CLI contract differs from Canon.

## TDD Tasks

### Task 1: `CDLGW-004-T01` — RED/GREEN replay-compatible enrichment

**Files:** create `tests/test_process_tree_replay.py`, create `wrapper/enrichment.py`.

- [ ] Write failing tests with sequence, XOR, parallel, and loop trees. The input is an `AnnotatedTrace`; assertions preserve its activity-name occurrence sequence and reject an activity absent from its version tree.

```python
def test_parallel_trace_gets_overlapping_intervals():
    enriched = enrich_traces(traces=parallel_trace(), snapshots=parallel_snapshots(), config=config())
    assert interval(enriched[0], "A").overlaps(interval(enriched[0], "B"))
```

- [ ] Run `\.venv\Scripts\python.exe -m pytest tests/test_process_tree_replay.py -v`; expect failure because `enrich_traces` does not exist.
- [ ] Implement minimal tree parser/replay validation in `wrapper/enrichment.py`; use the recovered tree only as a structural oracle. Do not generate another control-flow path.
- [ ] Re-run the command; expect PASS.
- [ ] Commit this task: `git add wrapper/enrichment.py tests/test_process_tree_replay.py && git commit -m "feat: replay CDLG traces for enrichment"`.

### Task 2: `CDLGW-004-T02` — RED/GREEN lifecycle, resources, and shared time

**Files:** modify `wrapper/config.py`; modify `wrapper/enrichment.py`; create `tests/test_enrichment.py`.

- [ ] Add failing tests for start/complete pairing, disabled/enabled `assign`, identical resource on each lifecycle event, disjoint activity pools, no overlapping intervals per resource, Poisson arrival ordering, global lognormal durations, and natural carryover.

```python
assert [(event.transition, event.resource) for event in instance.events] == [("start", "res_a_1"), ("complete", "res_a_1")]
assert all(not left.overlaps(right) for left, right in resource_intervals(enriched, "res_a_1"))
```

- [ ] Run `\.venv\Scripts\python.exe -m pytest tests/test_enrichment.py -v`; expect failure.
- [ ] Add `TemporalConfig(arrival_rate, duration_mu, duration_sigma, epoch)` and `OutputConfig(export_per_version_xes=False)` with defaults documented in the config catalog/example. Add an injected wrapper-owned `random.Random` to make tests deterministic; record that CDLG randomness remains external.
- [ ] Implement activity-specific deterministic pools (`resource_<stable-activity-id>_<position>`), lowest-workload selection, deterministic RNG tie-break, waiting, and lifecycle records. Emit global case/instance IDs; use `assign` before `start` only when enabled. Maintain trace membership order by version while scheduling all cases on one absolute timeline.
- [ ] Re-run focused replay/enrichment tests; expect PASS and save as `CDLGW-004-EV01`.
- [ ] Commit: `git add wrapper/config.py wrapper/enrichment.py tests/test_enrichment.py tests/test_process_tree_replay.py && git commit -m "feat: enrich lifecycle resources and time"`.

### Task 3: `CDLGW-004-T03` — RED/GREEN unified XES assembly

**Files:** create `wrapper/xes.py`, create `tests/test_xes.py`.

- [ ] Write failing tests that build two enriched versions and assert one XES, version-contiguous trace order, unique `concept:name` case IDs, trace/event `concept:version`, UTC timestamps, required resource/instance fields, and stable lifecycle tie order.

```python
assert trace_versions(exported_log) == ["v1", "v1", "v2"]
assert event_transitions(exported_log[0]) == ["assign", "start", "complete"]
```

- [ ] Run `\.venv\Scripts\python.exe -m pytest tests/test_xes.py -v`; expect failure.
- [ ] Implement `assemble_xes(enriched_log)` and `write_xes(log, path)`. Serialize exactly the enriched values; do not add `sim:bpmn_element_id` or `sim:bpmn_tag`. Support debug per-version exports only behind `output.export_per_version_xes`.
- [ ] Re-run; expect PASS and save as `CDLGW-004-EV02`.
- [ ] Commit: `git add wrapper/xes.py tests/test_xes.py && git commit -m "feat: assemble unified versioned XES"`.

### Task 4: `CDLGW-004-T04` — RED/GREEN draft evidence

**Files:** create `wrapper/evidence.py`, create `tests/test_evidence.py`.

- [ ] Write failing tests for relative artifact paths, input/resolved config copies, processing records (allocation, pools, carryover, distributions), environment record, methodology text, and checksum mismatch detection. Do not test publication or final validation; those belong to `CDLGW-005`.
- [ ] Run `\.venv\Scripts\python.exe -m pytest tests/test_evidence.py -v`; expect failure.
- [ ] Implement `write_draft_evidence(...)` into a caller-provided staging directory. Close files before SHA-256 calculation; include only wrapper-controlled randomness and the explicit external-CDLG seed limitation. Never serialize absolute workstation paths or inherited environment secrets.
- [ ] Re-run XES/evidence tests; expect PASS.
- [ ] Commit: `git add wrapper/evidence.py tests/test_evidence.py && git commit -m "feat: record enrichment evidence"`.

### Task 5: `CDLGW-004-T05` — REFACTOR and closure

- [ ] Run `\.venv\Scripts\python.exe -m pytest tests/test_process_tree_replay.py tests/test_enrichment.py tests/test_xes.py tests/test_evidence.py -v` (`EV01`/`EV02`).
- [ ] Run `\.venv\Scripts\python.exe -m pytest tests -v`, `\.venv\Scripts\python.exe -m compileall -q wrapper`, import-boundary scan, and `git diff --check` (`CDLGW-004-EV03`).
- [ ] Create ignored closure evidence under `outputs/worklogs/` and update Roadmap only after independent closure verification (`CDLGW-004-EV04`).

## Forbidden Scope

- Gradual/incremental/recurring drift, resource drift, calendars, activity-specific duration distributions.
- `sim:bpmn_element_id` or `sim:bpmn_tag` event enrichment.
- Final validation/publication/CLI/downstream execution (`CDLGW-005`/`CDLGW-006`).
- CDLG source changes, CDLG imports, or `bpm_prediction` imports.

## Self-Review

`AC01` maps to Tasks 1-2 and `EV01`; `AC02` maps to Tasks 3-4 and `EV02`. Task 5 supplies the outer regression and closure evidence. The plan deliberately separates scheduling, XES serialization, and evidence to prevent accidental publication behavior in this slice.

Reply `OK EXECUTE CDLGW-004` to authorize execution of this TDD plan. Reply `CHANGE CDLGW-004` with corrections to revise it.
