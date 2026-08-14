# Roadmap

## Delivery Status

- `active_plan_id`: `CDLGW-001`
- `active_slice`: Bootstrap and Configuration Contract
- `implementation_status`: not started
- `canonical_design`: [wrapper-design.md](wrapper-design.md)
- `implementation_source_plan`: [2026-08-14-cdlg-wrapper-mvp.md](superpowers/plans/2026-08-14-cdlg-wrapper-mvp.md)

Only one slice may be `in-progress`. A slice becomes `complete` only after its
acceptance scenarios have independent evidence and closure verification.

## Traceability Convention

| Item | Format | Meaning |
| --- | --- | --- |
| Plan ID | `CDLGW-NNN` | One independently deliverable roadmap slice. |
| Acceptance ID | `CDLGW-NNN-ACNN` | Observable behavior required by that slice. |
| Evidence ID | `CDLGW-NNN-EVNN` | Test, command, or review result proving an acceptance scenario. |
| Task ID | `CDLGW-NNN-TNN` | RED/GREEN/REFACTOR task created in the slice-specific execution plan. |

## Delivery Slices

| Plan ID | Slice | Status | Source plan coverage | Depends on | Completion boundary |
| --- | --- | --- | --- | --- | --- |
| `CDLGW-001` | Bootstrap and Configuration Contract | in-progress | Tasks 1-2 | Approved Canon | Valid YAML resolves into a reproducible, exact-allocation configuration with typed failures. |
| `CDLGW-002` | External CDLG Execution and Raw Artifact Capture | planned | Task 3 | `CDLGW-001` | Verified external checkout produces one captured raw XES and drift CSV without modifying `CDLG/`. |
| `CDLGW-003` | Version Reconstruction and Structure Artifacts | planned | Tasks 4-5 | `CDLGW-002` | Exact version mapping plus one parseable BPMN/PTML pair and catalog row per version. |
| `CDLGW-004` | Execution Enrichment and Unified XES | planned | Tasks 6-7 | `CDLGW-003` | Versioned lifecycle/resource/timestamp XES and evidence bundle satisfy the XES contract. |
| `CDLGW-005` | Validation, Publication, and CLI | planned | Tasks 8-9 | `CDLGW-004` | CLI publishes only strictly validated dataset bundles and preserves failed-run diagnostics. |
| `CDLGW-006` | End-to-End and bpm_prediction Compatibility | planned | Task 10 | `CDLGW-005` | Real CDLG run and separate downstream compatibility smoke test pass. |

## Agent Scenario Cards

### `CDLGW-001` — Bootstrap and Configuration Contract

**Sources:** [wrapper-design.md](wrapper-design.md#configuration-and-cli-contract), [wrapper-design.md](wrapper-design.md#trace-allocation-contract), [MVP plan](superpowers/plans/2026-08-14-cdlg-wrapper-mvp.md).

| Scenario | Priority | Given / When / Then | Independent verification | TDD and evidence |
| --- | --- | --- | --- | --- |
| `CDLGW-001-AC01` | P0 | Given a valid first-experiment YAML, when it is loaded, then defaults resolve to five sudden versions, `middle`, `0.2`, no noise, and lifecycle/resource defaults. | `pytest tests/test_config.py -v` | RED/GREEN tasks; save result as `CDLGW-001-EV01`. |
| `CDLGW-001-AC02` | P0 | Given `total_traces=17` and five versions, when allocation resolves, then it is `[4,4,3,3,3]` and CDLG receives ceiling count `4`. | `pytest tests/test_trace_allocation.py -v` | RED/GREEN tasks; save result as `CDLGW-001-EV02`. |
| `CDLGW-001-AC03` | P1 | Given invalid configuration or an expected wrapper error, when the CLI maps it, then it returns the documented typed exit code. | `pytest tests/test_errors.py -v` | RED/GREEN tasks; save result as `CDLGW-001-EV03`. |

**Implementation evidence:** `CDLGW-001-EV01`, `CDLGW-001-EV02`,
`CDLGW-001-EV03`, and `CDLGW-001-EV04` are produced by the focused pytest
commands listed above. Latest local execution used the benchmark `.venv`
interpreter because `python` is not on PATH in this workstation session. Status
remains `in-progress` until closure verification reviews coverage.

**Forbidden scope:** invoking CDLG, writing dataset output, importing `bpm_prediction`, or implementing lifecycle/resource scheduling.

### `CDLGW-002` — External CDLG Execution and Raw Artifact Capture

**Sources:** [wrapper-design.md](wrapper-design.md#external-cdlg-execution-contract), [AGENTS.md](../AGENTS.md#legal-and-repository-boundary).

| Scenario | Priority | Given / When / Then | Independent verification | TDD and evidence |
| --- | --- | --- | --- | --- |
| `CDLGW-002-AC01` | P0 | Given an incorrect, dirty, or incomplete checkout, when a run starts, then it fails before generation with component-specific diagnostics. | `pytest tests/test_cdlg_runner.py -v` using fake checkouts | RED/GREEN tasks; `CDLGW-002-EV01`. |
| `CDLGW-002-AC02` | P0 | Given the pinned clean checkout and resolved configuration, when the runner executes, then it captures exactly one raw XES, drift CSV, command, stdout, stderr, and exit code without writing into `CDLG/`. | Focused runner test plus manual clean-worktree check | RED/GREEN tasks; `CDLGW-002-EV02`. |

**Forbidden scope:** CDLG source changes, Python imports from `CDLG/src`, or post-processing raw XES.

### `CDLGW-003` — Version Reconstruction and Structure Artifacts

**Sources:** [wrapper-design.md](wrapper-design.md#structure-artifact-contract), [wrapper-design.md](wrapper-design.md#deterministic-bpmn-identity-contract).

| Scenario | Priority | Given / When / Then | Independent verification | TDD and evidence |
| --- | --- | --- | --- | --- |
| `CDLGW-003-AC01` | P0 | Given raw CDLG XES and drift metadata, when parsed, then every retained trace belongs to one ordered version and surplus traces are recorded without altering raw provenance. | `pytest tests/test_cdlg_metadata.py tests/test_annotate_versions.py -v` | RED/GREEN tasks; `CDLGW-003-EV01`. |
| `CDLGW-003-AC02` | P0 | Given recovered process trees, when structures export, then each version has one parseable PTML, BPMN, and deterministic catalog row with valid IDs/references. | `pytest tests/test_structure.py -v` | RED/GREEN tasks; `CDLGW-003-EV02`. |

**Forbidden scope:** artificial event scheduling, resources, or downstream runtime integration.

### `CDLGW-004` — Execution Enrichment and Unified XES

**Sources:** [wrapper-design.md](wrapper-design.md#lifecycle-contract), [wrapper-design.md](wrapper-design.md#resource-contract), [wrapper-design.md](wrapper-design.md#timestamp-and-concurrency-contract), [wrapper-design.md](wrapper-design.md#required-xes-compatibility-contract).

| Scenario | Priority | Given / When / Then | Independent verification | TDD and evidence |
| --- | --- | --- | --- | --- |
| `CDLGW-004-AC01` | P0 | Given CDLG activity traces and source trees, when enriched, then every activity has paired `start`/`complete`, exact instance IDs, stable resources, and no resource double-booking. | `pytest tests/test_enrichment.py tests/test_process_tree_replay.py -v` | RED/GREEN tasks; `CDLGW-004-EV01`. |
| `CDLGW-004-AC02` | P0 | Given enriched traces, when assembled, then one XES has required attributes, globally unique case IDs, stable event order, version-contiguous traces, and shared absolute time. | `pytest tests/test_xes.py tests/test_evidence.py -v` | RED/GREEN tasks; `CDLGW-004-EV02`. |

**Forbidden scope:** gradual drift, resource drift, or `sim:bpmn_element_id`/`sim:bpmn_tag` enrichment.

### `CDLGW-005` — Validation, Publication, and CLI

**Sources:** [wrapper-design.md](wrapper-design.md#validation-contract), [wrapper-design.md](wrapper-design.md#approved-error-handling-and-diagnostics).

| Scenario | Priority | Given / When / Then | Independent verification | TDD and evidence |
| --- | --- | --- | --- | --- |
| `CDLGW-005-AC01` | P0 | Given an invalid bundle, when validation runs, then publication fails and a failed-run bundle preserves diagnostics without appearing valid. | `pytest tests/test_validation.py -v` | RED/GREEN tasks; `CDLGW-005-EV01`. |
| `CDLGW-005-AC02` | P0 | Given a valid configuration, when the CLI runs, then it reports the dataset path on success and maps expected failures to documented non-zero exit codes. | `pytest tests/test_cli.py -v` | RED/GREEN tasks; `CDLGW-005-EV02`. |

**Forbidden scope:** changing the dataset methodology to make validation pass.

### `CDLGW-006` — End-to-End and bpm_prediction Compatibility

**Sources:** [wrapper-design.md](wrapper-design.md#downstream-compatibility-smoke-test), [wrapper-design.md](wrapper-design.md#bpm_prediction-structure-integration-analysis).

| Scenario | Priority | Given / When / Then | Independent verification | TDD and evidence |
| --- | --- | --- | --- | --- |
| `CDLGW-006-AC01` | P0 | Given the pinned external CDLG checkout, when a small three-version run completes, then the complete validated artifact bundle exists and all checksums match. | `pytest tests/test_end_to_end.py -v` | Slow integration evidence `CDLGW-006-EV01`. |
| `CDLGW-006-AC02` | P0 | Given the generated bundle and separate `bpm_prediction` environment, when its XES/BPMN ingestion smoke test runs, then pairing, BPMN ingestion, `collapse_for_prediction`, and activity alignment succeed. | `pytest tests/test_bpm_prediction_compatibility.py -v` with the downstream interpreter | Compatibility evidence `CDLGW-006-EV02`. |

**Forbidden scope:** importing `bpm_prediction` into the wrapper or making its code a wrapper dependency.

## Deferred Themes

- Controlled gradual, incremental, and recurring drift scenarios.
- Resource-configuration, workload, and performance drift.
- Activity-specific timing distributions and calendar constraints.
- Optional `sim:bpmn_element_id` and `sim:bpmn_tag` experiments.

## Status Discipline

- A `planned` slice has approved sources and scenario cards but no execution evidence.
- An `in-progress` slice is the only active slice and must retain its Plan ID.
- A `complete` slice requires closure verification against every listed acceptance ID.
- A blocked slice must name the missing source, decision, command, or external condition.
