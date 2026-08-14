# CDLGW-003 TDD Plan: Version Reconstruction and Structure Artifacts

> **Status:** proposed. Do not implement this slice until the user approves it
> with `OK EXECUTE CDLGW-003`.

**Plan ID:** `CDLGW-003`

**Goal:** Convert the captured raw CDLG XES and drift metadata into an in-memory
version mapping, retain exactly the resolved number of traces per contiguous
version block, and export one deterministic BPMN/PTML pair plus one catalog row
for every recovered process version.

**Architecture boundary:** This slice consumes only files staged by
`wrapper.cdlg_runner`. It must not import CDLG, mutate the preserved raw XES,
schedule lifecycle events, assign resources, create the final unified XES, or
call `bpm_prediction`.

**Sources:**

- [Roadmap acceptance cards](../../ROADMAP.md#cdlgw-003-вЂ”-version-reconstruction-and-structure-artifacts)
- [Structure artifact contract](../../wrapper-design.md#structure-artifact-contract)
- [Deterministic BPMN identity contract](../../wrapper-design.md#deterministic-bpmn-identity-contract)
- [Trace-allocation contract](../../wrapper-design.md#trace-allocation-contract)
- [MVP plan tasks 4-5](2026-08-14-cdlg-wrapper-mvp.md#task-4-recover-version-metadata-and-annotate-traces)

## Acceptance and BDD Scenarios

### `CDLGW-003-AC01` — recover and annotate ordered versions

**BDD-01: exact allocation and provenance preservation**

```gherkin
Given a raw CDLG XES with five contiguous version blocks of four traces
And resolved allocation [4, 4, 3, 3, 3]
When metadata is parsed and retained traces are annotated
Then retained traces map in order to v1 through v5 with counts [4, 4, 3, 3, 3]
And each retained trace and each copied event has concept:version
And five surplus raw traces are recorded by version without changing raw XES bytes
```

**BDD-02: reject metadata that cannot establish the structural oracle**

```gherkin
Given raw drift metadata with a missing tree, duplicate version, malformed tree,
or ambiguous trace boundary
When version reconstruction is requested
Then it raises a typed artifact error before any annotated output is published
And the diagnostic identifies the failing metadata component
```

**BDD-03: preserve raw labels and order**

```gherkin
Given a valid raw trace block
When its retained copy is version-annotated
Then original trace IDs, event names, and event order are unchanged
And annotation is applied to a new in-memory representation rather than raw/cdlg_output.xes
```

### `CDLGW-003-AC02` — export one deterministic structure pair per version

**BDD-04: one parseable artifact pair and catalog row per snapshot**

```gherkin
Given ordered, parseable process-tree snapshots for v1 through v5
When structures are exported
Then models/ptml/vK.ptml and models/bpmn/vK.bpmn exist for every K
And each file parses back through the installed PM4Py API
And process_definitions.csv has exactly one deterministic row per version
```

**BDD-05: stable task identity and valid BPMN references**

```gherkin
Given an unchanged visible activity carried from v1 into v2
When both BPMN artifacts are normalized
Then that task has the same deterministic BPMN ID in both versions
And BPMN task names exactly equal the corresponding visible activity labels
And all IDs are unique and every sequence-flow endpoint resolves to an exported node
```

**BDD-06: fail ambiguous activity alignment**

```gherkin
Given a process tree with duplicate visible activity labels in one version
When its BPMN structure is prepared
Then export fails with an explicit alignment error
And no catalog row is emitted for that invalid version
```

## TDD Execution Tasks

### `CDLGW-003-T01` — RED: characterize raw metadata and boundaries

**Files:**

- Create `tests/fixtures/cdlg_metadata/valid_five_versions.xes`
- Create `tests/fixtures/cdlg_metadata/valid_drift_info.csv`
- Create malformed metadata fixtures beside them
- Create `tests/test_cdlg_metadata.py`

**Tests first:** Build small, readable raw XES/CSV fixtures that represent CDLG
log-level `process_trees` metadata and five contiguous four-trace blocks. Add
failing tests for ordered snapshots, exact snapshot count, malformed/missing
trees, duplicate version IDs, and ambiguous boundaries. Tests must assert
`ArtifactError` diagnostics, not internal parser implementation details.

**Expected RED command:**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cdlg_metadata.py -v
```

**Evidence:** contributes to `CDLGW-003-EV01`.

### `CDLGW-003-T02` — GREEN: parse CDLG metadata without CDLG imports

**Files:**

- Create `wrapper/cdlg_metadata.py`
- Modify `wrapper/errors.py` only if a more specific existing typed error is
  necessary; preserve CLI exit-code compatibility

**Implementation:** Define immutable records for an ordered process-tree
snapshot and raw version boundaries. Parse the staged XES log attributes and
`drift_info.csv`, cross-check both sources, and require exactly
`resolved_config.dataset.version_count` ordered snapshots. Return boundaries
that map each raw trace index to exactly one source version before trimming.
Reject disagreements, malformed tree strings, missing fields, duplicates, or
unresolvable boundaries as `ArtifactError`. Keep all parsing file-based and do
not import `CDLG`.

**GREEN command:**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cdlg_metadata.py -v
```

### `CDLGW-003-T03` — RED: specify non-destructive annotation and surplus accounting

**Files:**

- Create `tests/test_annotate_versions.py`

**Tests first:** Starting with `17` requested traces, five versions, and four
raw traces per version, assert retained counts `[4, 4, 3, 3, 3]`, deterministic
first-to-last contiguous assignment, trace/event `concept:version`, and a
per-version discarded-count report `[0, 0, 1, 1, 1]`. Add tests proving that
the raw source file checksum and original event values/order remain unchanged.

**Expected RED command:**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_annotate_versions.py -v
```

**Evidence:** contributes to `CDLGW-003-EV01`.

### `CDLGW-003-T04` — GREEN: annotate retained copies and report surplus

**Files:**

- Create `wrapper/annotate_versions.py`

**Implementation:** Accept parsed boundaries and `ResolvedConfig`. Copy only
the resolved allocation from each contiguous raw block; never rewrite the raw
XES. Apply `concept:version` to every retained trace and event in the copied
representation. Return an immutable mapping/report that includes source index,
version ID, retained count, and discarded count for each version. This module
does not yet serialize the unified XES; that belongs to `CDLGW-004`.

**GREEN command:**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cdlg_metadata.py tests/test_annotate_versions.py -v
```

### `CDLGW-003-T05` — RED: specify PTML/BPMN export and deterministic identity

**Files:**

- Create `tests/test_structure.py`

**Tests first:** Use two small, ordered process-tree strings where one visible
activity is unchanged and another structural fragment changes. Assert exactly
one PTML and BPMN file per version, PM4Py round-trip parsing, fixed start/end
IDs, stable unchanged task IDs, deterministic changed-gateway IDs, unique IDs,
valid sequence-flow references, task-name equality, deterministic catalog rows,
and rejection of duplicate visible labels.

The test must run the export twice to two temporary destinations and compare
the normalized BPMN IDs and catalog content, so it detects random exporter IDs.

**Expected RED command:**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_structure.py -v
```

**Evidence:** contributes to `CDLGW-003-EV02`.

### `CDLGW-003-T06` — GREEN: export normalized structures and catalog

**Files:**

- Create `wrapper/structure.py`

**Implementation:** Parse each recovered process-tree string with the installed
PM4Py generic parser, export PTML, convert the same tree to BPMN, and export
the BPMN XML. Normalize exporter-generated IDs deterministically before final
write:

- task IDs use normalized visible label plus a stable short hash;
- start/end use fixed IDs;
- gateways use operator type, split/join role, and canonical child signature;
- flows use normalized endpoint IDs;
- deterministic traversal-derived suffixes resolve collisions.

Rewrite every flow reference after normalization and validate uniqueness and
referential integrity in memory. Reject duplicate visible labels in a version.
Emit `models/process_definitions.csv` in version order with deterministic
`process_key`, `proc_def_id`, `version`, and relative BPMN path. Return original
to normalized ID mappings and canonical signatures for the later processing
report; do not create `reports/processing.json` in this slice.

**GREEN command:**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_structure.py -v
```

### `CDLGW-003-T07` — REFACTOR and slice verification

**Files:**

- Modify `docs/ROADMAP.md` only after implementation and independent closure
  evidence exist
- Create ignored `outputs/worklogs/...-REPORT-CDLGW-003-...md` only at closure

**Refactor constraints:** Keep PM4Py-specific logic contained in
`wrapper/structure.py`; keep XES/CSV parsing in `wrapper/cdlg_metadata.py`; do
not add new runtime dependencies. Re-run all prior tests to protect the
configuration and external-runner contracts.

**Required verification:**

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_cdlg_metadata.py tests/test_annotate_versions.py tests/test_structure.py -v
.\.venv\Scripts\python.exe -m pytest tests -v
.\.venv\Scripts\python.exe -m compileall -q wrapper
git diff --check
```

**Evidence mapping:** focused metadata/annotation run is `CDLGW-003-EV01`;
focused structure run is `CDLGW-003-EV02`; full suite and closure review are
`CDLGW-003-EV03` and `CDLGW-003-EV04`.

## Completion Criteria

- Both `CDLGW-003-AC01` and `CDLGW-003-AC02` have fresh, independent evidence.
- Every configured version has one recovered process tree, one parseable PTML,
  one parseable normalized BPMN file, and one deterministic catalog row.
- Retained trace counts exactly equal `ResolvedConfig.trace_allocation`; all
  excess raw traces are recorded, never silently deleted or rewritten.
- `CDLG/` remains untracked and unmodified; no wrapper module imports CDLG or
  `bpm_prediction`.
- The Roadmap is updated only after closure verification passes.

## Explicitly Deferred

- Lifecycle expansion, timestamps, concurrency, resources, and carryover
  (`CDLGW-004`).
- Unified XES serialization, manifests, checksums, CLI, publication, and
  downstream compatibility (`CDLGW-004` through `CDLGW-006`).
- Gradual drift and optional BPMN event attributes.
