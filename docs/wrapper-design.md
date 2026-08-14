# CDLG Versioned XES Wrapper Design

## Document Status

- Status: Approved Canon
- Date: 2026-08-14
- Repository: `CDLG_Wrapper` independent adapter repository
- Implementation location: `wrapper/`
- Integration mode: external pinned CDLG subprocess plus file exchange
- Approval status: approved by user on 2026-08-14
- Design review status: architecture, data flow, error handling, diagnostics, and
  test strategy approved; self-review complete

This is the approved living design specification for the first experiment.
Confirmed decisions may be clarified here, but implementation must not silently
change the methodology, artifact contract, or repository boundary.

## Decision Recording Policy

- Record every user agreement and every adopted design decision in this living
  specification.
- Adopt without a separate confirmation only decisions that are deterministic,
  fit the approved architecture, preserve experimental semantics, and do not
  materially expand implementation scope.
- Record the rationale for automatically adopted decisions.
- Request explicit user approval when a choice changes experimental methodology,
  public artifact contracts, repository boundaries, or implementation complexity
  materially.

## Objective

Build a configuration-driven benchmark wrapper that invokes an external,
unmodified CDLG checkout to generate a structurally evolving raw event log, then
post-processes the raw artifacts into a research-ready versioned XES, one BPMN
and one PTML per version, drift metrics, and a complete experimental evidence
bundle for experiments in `bpm_prediction`.

The wrapper must produce one final XES dataset whose traces are explicitly
associated with process versions. `bpm_prediction` consumes the generated
artifacts later, but it does not import or execute CDLG.

## Repository Boundary

The wrapper belongs to an independent benchmark repository. CDLG is obtained
separately from
`https://gitlab.uni-mannheim.de/processanalytics/cdlg_tool`, remains under its
GPL-3.0 license, and is stored only in the ignored local `CDLG/` checkout.

The benchmark must invoke CDLG as a separate process. Communication is limited
to generated parameter files, process arguments, exit status, stdout, stderr,
raw XES, and drift metadata. Benchmark Python code must not import CDLG modules,
copy CDLG source, modify the checkout, or install CDLG into the benchmark
environment.

The pinned upstream revision for the first experiment is
`cbe1534de94f06a3f1cca460b079d436f604445e`. The runner must verify this revision
and a clean tracked worktree before every run and record both facts as evidence.

`bpm_prediction` remains a third independent repository and consumes only the
published benchmark artifacts.

## Licensing and Attribution Boundary

- License benchmark-owned wrapper code and repository materials under the root
  MIT License.
- Keep `/CDLG/` ignored and absent from every benchmark commit and release.
- Do not use a Git submodule or vendor archive for CDLG in the first
  implementation.
- Attribute CDLG, its upstream URL, GPL-3.0 license, and exact commit in the root
  README, run manifest, environment report, and methodology report.
- Preserve raw CDLG output as provenance but do not represent generated data as
  CDLG source code. If a generated artifact unexpectedly embeds covered source
  text, stop publication and review it separately.
- Apply the MIT license only to benchmark-owned materials and never represent it
  as relicensing CDLG or third-party artifacts. This engineering boundary is not
  legal advice and does not replace a formal legal review.

## Confirmed Design Decisions

### Process Version Semantics

- Use one evolutionary chain: `v1 -> v2 -> ... -> vN`.
- Generate `v1` once.
- Derive each following version by applying CDLG structural evolution to the immediately preceding process tree.
- Do not generate independent random process trees for individual versions.
- Every trace must carry an explicit process version.
- Configure the number of versions as a positive integer.
- Use `5` as the default version count for the first experiment.
- Generate ordered version IDs automatically as `v1` through `vN`.
- Do not require a user-provided version ID list in the first implementation.

### Base Process Tree Contract

- Configure the initial CDLG preset through
  `cdlg.process_tree_complexity`.
- Accept only `simple`, `middle`, or `complex` in the first implementation.
- Use `middle` as the default preset. In the current CDLG implementation this
  targets a process tree with approximately 14-20 visible activities and a mixed
  sequence, choice, parallel, and loop structure.
- Generate `v1` through CDLG's preset-based process-tree generation path; do not
  reimplement random process-tree generation in the wrapper.
- Do not expose raw PM4Py tree-generator parameter overrides in the first
  implementation.
- Record the selected preset, the current CDLG preset parameter snapshot, and the
  CDLG repository revision in `configs/resolved.yaml`, `manifest.json`, and
  `environment.json`.
- Treat the recorded parameter snapshot as experimental evidence. If a future
  CDLG revision changes a preset, the changed resolved values and revision must
  remain visible instead of being silently presented as the previous preset.

### Evolution Strength Contract

- Configure one evolution proportion and apply it to every adjacent transition `vK -> vK+1`.
- Use `0.2` as the default evolution proportion.
- Encode the configured value in the generated CDLG parameter file as
  `Process_tree_evolution_proportion`; benchmark code must not call the internal
  evolution function directly.
- Interpret `0.2` as approximately 20% of the current process tree's activity leaves being targeted by CDLG evolution operations.
- Do not interpret four transitions at `0.2` as a guaranteed 80% difference between `v1` and `v5`.
- Changes may overlap across transitions, and additions or deletions change the activity count used by later transitions.
- Record adjacent-version and cumulative `v1`-to-`vN` structural-change diagnostics in the output manifest.
- Do not regenerate versions to force a predefined final structural distance unless a later design revision explicitly adds such a policy.
- The first experiment accepts the naturally generated cumulative distance; no minimum or maximum `v1`-to-`vN` threshold is enforced.

### Drift Scope for the First Experiment

- Support sudden drift only in the first implementation.
- Represent versions as contiguous trace blocks in version order.
- Preserve exact configured trace counts per version.
- Treat gradual drift as a later, separately configured extension.
- Exclude incremental and recurring drift from the first implementation.

### Lifecycle Contract

- Emit `start` and `complete` events for every simulated activity instance.
- Support `assign` as an optional output event; disable it by default.
- Emit the standard `concept:instance` attribute for exact lifecycle pairing in
  the current `bpm_prediction` XES adapter.
- Also emit `sim:activity_instance_id` with the same value for provenance and
  compatibility with downstream graph-building diagnostics.
- Configure downstream `start_transitions` as `["start"]` even when optional
  `assign` events are present. Treating both `assign` and `start` as starts would
  count one activity instance twice and leave a false active-task state after
  its completion.
- Preserve stable event ordering when timestamps are equal.
- Keep `complete` as the prediction event consumed by the downstream XES adapter.

### Resource Contract

- Emit `org:resource` for every lifecycle event.
- Use stable activity-specific resource pools.
- Use three resources per activity by default and allow the pool cardinality to
  be configured globally.
- Keep activity pools disjoint in the first experiment; a resource belongs to
  exactly one activity pool.
- Keep an activity's resource pool stable across all process versions where that activity exists.
- Reuse the same pool if an unchanged activity persists, is moved, or reappears
  in a later version; create a new deterministic pool only for a newly introduced
  activity.
- Select an executor from the activity pool for each activity instance.
- Never allow one resource to execute two activity instances simultaneously.
- If all resources in the required pool are busy, wait until at least one becomes
  available.
- Among available resources, select the one with the lowest accumulated workload
  and use a wrapper-controlled random tie-break when workloads are equal.
- Reuse the selected executor for all lifecycle events of the same activity instance.
- Generate deterministic resource IDs from the stable activity identity and pool
  position, and record the complete activity-to-resource mapping in the manifest.
- Do not introduce resource-distribution changes at version boundaries in the first experiment.

### Configuration and CLI Contract

- Use YAML as the wrapper configuration format.
- Provide one non-interactive CLI entry point.
- Use `configs/` for committed example and experiment configurations.
- Use the planned invocation form
  `python wrapper/generate_benchmark.py --config <config-path>`.
- Provide `scripts/run_cdlg.ps1` and `scripts/run_cdlg.sh` as thin
  platform-specific subprocess launchers.
- Do not extend CDLG's legacy line-based parameter format for wrapper-specific settings.
- Keep the configuration publishable with the generated dataset so the experimental setup is auditable.
- Support optional per-version XES debug export through
  `output.export_per_version_xes`; disable it by default because the unified XES
  is the experiment contract.

### External CDLG Execution Contract

- Configure an ignored CDLG checkout path and a CDLG Python executable path;
  default the checkout path to `CDLG/` but do not publish workstation-specific
  absolute paths.
- Before execution, verify the checkout's exact commit, clean tracked state,
  expected GPL-3.0 license file, and required upstream entry points.
- Create a run-specific disposable CDLG runtime copy under ignored `work/` rather
  than writing generated parameters or outputs into the pinned source checkout.
- Exclude `.git`, virtual environments, IDE files, and upstream documentation
  from the disposable runtime copy.
- Translate the resolved benchmark YAML into CDLG's existing line-based
  `src/input_parameters/default` format inside the disposable runtime copy.
- Execute the unmodified upstream `generate_collection_of_logs.py` entry point
  with the configured CDLG interpreter and runtime copy as its working directory.
- Pass no Python objects across the boundary. Capture only process arguments,
  environment allowlist, exit code, stdout, stderr, elapsed time, and generated
  files.
- Copy raw XES and relevant raw metadata into the benchmark staging bundle before
  post-processing; never post-process the only copy in place.
- Fail if CDLG produces no XES, multiple ambiguous candidate XES files, malformed
  drift metadata, or a number of process-tree snapshots inconsistent with the
  configured version count.
- Keep failed disposable runtime state only when debug retention is enabled;
  otherwise retain command/stdout/stderr/failure evidence and remove the runtime
  copy after diagnostics are finalized.

### Trace Allocation Contract

- Configure one positive integer `dataset.total_traces` for the final XES.
- Allocate traces equally across all configured process versions by default.
- For five versions, target approximately 20% of the complete dataset per version.
- Use integer quotient/remainder allocation so the final sum is exactly `dataset.total_traces`.
- Ensure that version trace counts differ by at most one when equal allocation is used.
- Assign any remainder deterministically in ascending version order.
- Because stock CDLG accepts one shared `Number_traces_per_process_model_version`
  value, render `ceil(dataset.total_traces / version_count)` for CDLG, then
  retain the resolved exact allocation from each contiguous version block during
  post-processing. Preserve the complete untrimmed CDLG XES as raw provenance and
  record retained and discarded trace counts per version in the manifest.
- Record requested totals, actual per-version counts, and actual per-version percentages in the output manifest.
- Reject zero versions, non-positive totals, duplicate version IDs, and allocations that would leave a configured version with zero traces.

### Timestamp and Concurrency Contract

- Use one shared absolute timeline for all cases and process versions.
- Assign each case an absolute arrival timestamp on that timeline.
- Emit activity `start` and `complete` timestamps from simulated execution
  intervals rather than from a fixed increment over the linear XES order.
- Permit temporal overlap between parallel process-tree branches so that their
  activity intervals represent concurrent execution.
- Permit temporal overlap between independent cases.
- Sort events inside each trace by timestamp before XES export and use a stable
  `assign -> start -> complete` lifecycle tie-break order when timestamps are
  equal.
- Preserve process-tree control-flow semantics when scheduling activities;
  timestamp generation must not turn a parallel operator into a sequential
  dependency.
- Keep version blocks contiguous by trace membership in the final XES, while
  timestamps remain globally comparable across the complete dataset.
- Activate the next process version for newly arriving cases after the configured
  trace allocation for the current version has been started; do not wait for all
  current-version cases to complete.
- Bind each case to the process version active at its arrival. An in-flight case
  retains that version and structure until completion even if later versions have
  already started accepting new cases.
- Allow natural version-boundary carryover when an in-flight case completes after
  the next version has begun.
- Do not force a target carryover percentage and do not add artificial terminal
  waits in the first experiment. The observed overlap is an outcome of arrival
  rates, activity durations, resource waiting, and process complexity.
- Report case counts and percentages by completion-version delta (`same_version`,
  `plus_1`, `plus_2`, and so on) in validation and provenance artifacts.
- Record the actual activation timestamp of every process version in the
  manifest.
- Configure case arrivals and activity durations according to the Temporal
  Distribution Contract below.

The reference `bpm_prediction` simulation uses the same natural-overlap behavior:
its explicit `version_carryover` forcing is disabled, while long-running cases
can still cross activation boundaries. Its recorded overall completion deltas are
approximately 14.55% for `plus_1`, 4.37% for `plus_2`, 0.67% for `plus_3`, and
0.22% for `plus_4`. These values are reference observations, not wrapper targets
or acceptance thresholds.

### Temporal Distribution Contract

- Use a Poisson arrival process with one configurable rate shared by all process
  versions.
- Use one global lognormal activity-duration distribution in the first
  experiment.
- Apply the same duration parameters to all activities and versions so duration
  does not encode activity identity or process version.
- Do not enable activity-specific duration overrides in the first experiment.
- Keep both arrival and duration parameters configurable for later controlled
  experiments.
- Treat activity-specific timing and version-specific timing changes as separate
  performance-drift scenarios, not part of the first structural-drift dataset.

### Reproducibility and Article Evidence Contract

Store the complete generation evidence bundle beside the XES, BPMN, and PTML
artifacts. The bundle must distinguish requested inputs, resolved effective
parameters, processing decisions, observed outcomes, and validation evidence.

Required evidence artifacts:

- `configs/input.yaml`: an unchanged copy of the user-provided wrapper
  configuration;
- `configs/resolved.yaml`: the effective configuration after defaults,
  normalization, and derived trace allocations have been applied;
- `manifest.json`: machine-readable run identity, artifact inventory, relative
  paths, process-version mapping, trace counts, timestamps, random-state
  information, and references to the checksum inventory;
- `reports/processing.json`: machine-readable record of every generation stage,
  selected CDLG operations, per-version structural lineage, enrichment rules,
  and actual distributions;
- `reports/methodology.md`: concise human-readable description suitable as a
  source for the dataset and experimental-method sections of an article;
- `reports/validation.json`: all validation checks, measured values, thresholds,
  warnings, and pass/fail status;
- `reports/topology_alignment.json`: BPMN/XES activity coverage and optional
  BPMN-versus-XES topology comparison;
- `environment.json`: Python, CDLG, PM4Py, dependency, operating-system, and
  repository revision information available at generation time;
- `checksums.sha256`: integrity hashes for every finalized published artifact in
  the dataset bundle except the checksum file itself.

The evidence must include at least:

- every CDLG input parameter passed by the wrapper;
- the CDLG upstream URL, pinned and observed commits, clean-state check, Python
  executable version, exact command, exit code, stdout/stderr paths, and raw XES
  checksum;
- wrapper-only parameters and all default values actually used;
- version count, trace allocation, evolution proportion, and version IDs;
- the exact ordered evolution operations and CDLG-reported added, deleted, and
  moved activities for every `vK -> vK+1` transition;
- adjacent and cumulative structural-difference diagnostics;
- lifecycle, resource, timestamp, arrival, duration, and natural-carryover
  policies;
- requested and observed trace counts and percentages per version;
- observed lifecycle, resource, duration, concurrency, and completion-version
  distributions;
- BPMN/PTML/XES export details and downstream compatibility settings;
- all wrapper-controlled seeds or random states and an explicit limitation note
  for any randomness that cannot be controlled or reconstructed exactly;
- generation start/end times, warnings, validation status, and relative output
  paths.

Do not rely on console output as experimental evidence. The run is publishable
only when the structured evidence files are written successfully and their
checksums match the final artifacts. Close mutable outputs such as `run.log`
before calculating hashes. Use relative paths in published metadata; do not
expose workstation-specific absolute paths.

### Noise Contract

- Disable explicit control-flow, timestamp, lifecycle, attribute, and resource
  noise in the first experiment.
- Do not classify variability produced by the approved Poisson arrivals,
  lognormal durations, resource waiting, parallel scheduling, or natural
  carryover as injected noise.
- Introduce configurable noise only in a later controlled robustness scenario and
  report it as a separate experimental factor.

### Validation Contract

Mandatory local validation must fail the run before publication when any of the
following conditions is detected:

- external CDLG checkout commit, tracked state, license, or required entry points
  do not match the pinned execution contract;
- CDLG exits non-zero or its raw XES/stdout/stderr evidence is missing;
- raw drift metadata cannot provide exactly one ordered process tree per
  configured version and unambiguous trace boundaries;
- final or per-version trace counts differ from the resolved allocation;
- the number of BPMN or PTML artifacts differs from the configured version count;
- a trace or event has a missing or inconsistent process version;
- required XES attributes are missing;
- a lifecycle instance lacks exactly one `start` and one `complete`, has duplicate
  terminal events, or completes before it starts;
- events are not stably ordered by timestamp within a trace;
- one resource executes overlapping activity instances;
- an XES activity has no uniquely aligned BPMN task in its version;
- BPMN IDs are duplicated, sequence-flow references are broken, or the BPMN
  cannot be parsed back by PM4Py;
- a PTML artifact cannot be parsed back or does not correspond to its generated
  version;
- a finalized artifact hash does not match `checksums.sha256` during the final
  integrity-verification phase.

Use exact equality for counts and 100% coverage for required lifecycle and
BPMN-to-XES alignment checks. Report distributional observations such as natural
carryover and structural distances without imposing target thresholds unless a
future experiment config explicitly defines them.

The CDLG repository remains standalone. Mandatory local validation must not
import `bpm_prediction`. Generate downstream XES/BPMN configurations and a
machine-readable compatibility report so `bpm_prediction` can run its own parser,
topology-ingestion, and activity-alignment smoke tests in its separate virtual
environment before the dataset is used for training.

### XES BPMN-Specific Attributes

- `sim:bpmn_element_id` and `sim:bpmn_tag` are not required for the first experiment.
- The BPMN artifact, rather than duplicated event attributes, should carry the
  exact process structure used by `bpm_prediction`.
- Stable lifecycle instance identity is required even though BPMN element metadata is optional.

### Structure Artifact Contract

- Produce one unified XES dataset containing traces from all process versions.
- Preserve the unmodified raw CDLG XES as a provenance artifact.
- Extract ordered process-tree snapshots and change metadata from the raw CDLG
  XES log-level drift attributes.
- Parse CDLG process-tree strings with the benchmark environment's PM4Py
  `parse_process_tree()` support; do not use CDLG imports for reconstruction.
- Produce exactly one BPMN XML artifact for each generated process version;
  therefore `N` configured versions produce `N` BPMN files.
- Generate each BPMN artifact from the exact process tree used to simulate that
  version's traces.
- Use BPMN as the primary topology source for `bpm_prediction`.
- Retain one PTML artifact per version as the canonical process-tree audit
  representation.
- Use XES-derived topology only as an optional fallback and QA comparison.
- Map all BPMN artifacts to their process versions through one
  `process_definitions.csv` catalog.

### Deterministic BPMN Identity Contract

- Replace PM4Py-generated random BPMN IDs before export.
- Derive task IDs from the normalized visible activity label plus a short stable
  hash, so an unchanged activity retains its ID when moved within the process
  tree or carried into a later version.
- Use fixed deterministic IDs for the process start and end events.
- Derive gateway IDs from the operator type, split/join role, and canonical
  signature of the represented child structure.
- Treat a gateway whose represented structure changes as a changed structural
  node and assign it a new deterministic ID.
- Resolve rare ID collisions with a deterministic suffix derived from canonical
  traversal order; never use runtime-random UUIDs.
- Rewrite all sequence-flow source and target references after ID normalization.
- Record original exporter IDs, normalized IDs, canonical signatures, and
  cross-version identity changes in `reports/processing.json`.
- Validate ID uniqueness and referential integrity before accepting a BPMN
  artifact.

## Required XES Compatibility Contract

### Trace Attributes

| Attribute | Requirement | Purpose |
|---|---:|---|
| `concept:name` | Required | Globally unique case identifier |
| `concept:version` | Required | Process version used to generate the trace |
| `sim:generated_by` | Recommended | Dataset provenance |

### Event Attributes

| Attribute | Requirement | Purpose |
|---|---:|---|
| `concept:name` | Required | Activity identity consumed by the XES adapter |
| `time:timestamp` | Required | Event ordering and temporal features |
| `lifecycle:transition` | Required | `start`, `complete`, and optional `assign` |
| `org:resource` | Required | Stable resource feature and lifecycle pairing fallback |
| `concept:version` | Required | Event-level version with precedence over trace fallback |
| `concept:instance` | Required | Exact `start`/`complete` pairing in the XES adapter |
| `sim:activity_instance_id` | Recommended | Duplicate instance identity for provenance and downstream diagnostics |

## Current CDLG Findings

- `generate_specific_trees()` and `generate_log_from_tree()` provide the basic random model and trace generation APIs.
- `evolve_tree_randomly()` derives a changed process tree and reports added, deleted, and moved activities.
- The installed PM4Py version provides a process-tree exporter whose supported format is PTML.
- The stock collection engine can place several drifts in one XES, but it stores drift information mainly at log level and does not provide the explicit per-trace `concept:version` contract needed by the experiment.
- `add_duration_to_log()` currently adds only `complete` lifecycle events.
- CDLG does not model organizational resources, so the wrapper must add resource assignment as a separate enrichment stage.
- The downstream `bpm_prediction` XES adapter retains completion events for prediction while using start events and activity instance IDs for duration pairing and parallel active-task reconstruction.
- The current `bpm_prediction` log-based topology extractor creates a version-scoped directly-follows graph. It does not reconstruct exact process-tree operators or explicit AND/XOR gateways from XES.
- A linearized trace provides an observed previous event, but that event is not necessarily the causal predecessor when the process tree contains parallel branches.
- The installed PM4Py version can convert a process tree directly to BPMN and
  export BPMN XML; PTML is therefore not the only available structure artifact.
- PM4Py's conversion preserves process-tree operator semantics: sequence, XOR,
  parallel, inclusive-OR, and loop operators are converted to the corresponding
  BPMN control-flow pattern.
- PM4Py-generated BPMN node IDs are not stable by default. The wrapper must
  normalize at least task IDs deterministically and preserve activity labels
  across versions before BPMN artifacts can be treated as a stable experiment
  contract.

## `bpm_prediction` Structure Integration Analysis

### BPMN-First Path

`bpm_prediction` already supports file-based BPMN ingestion; a running Camunda
instance is not required. The effective flow is:

```text
process_definitions.csv + per-version BPMN XML
  -> CamundaBpmnAdapter(bpmn_source=files)
  -> BpmnStructureParserService
  -> ProcessStructureDTO
  -> knowledge-graph repository
  -> topology projection for GNN runtime
```

The BPMN parser retains explicit task, event, gateway, subprocess, call-activity,
boundary-event, sequence-flow, condition, loop, and multi-instance metadata. It
therefore preserves the structural information that cannot be reconstructed
reliably from a linearized XES trace.

For task-label prediction, `collapse_for_prediction` is the appropriate runtime
projection: the repository keeps the complete BPMN graph, while gateways and
events are traversed as transparent control-flow nodes to derive task-to-task
candidate edges. This matches CDLG XES events, which contain activity labels but
do not emit gateway events. A future gateway-importance experiment can still use
the retained full BPMN structure.

The wrapper must ensure that:

- each process version has one BPMN XML artifact and one catalog row;
- `proc_def_id`, process key, and version metadata are deterministic;
- unchanged activities keep stable deterministic BPMN task IDs across versions;
- BPMN task names match XES `concept:name` values exactly;
- visible activity labels are unique within a process version, or generation
  fails with an explicit alignment error;
- the exported BPMN passes the downstream parser and topology-projection smoke
  tests before the dataset is used for training in `bpm_prediction`.

### XES-Derived Path

The XES route is suitable as a fallback and a QA comparison, but not as the
primary structural source for this experiment. Its effective flow is:

```text
versioned XES
  -> XesAdapter
  -> completed EventRecord sequence with paired start timestamps
  -> TopologyExtractorService
  -> version-scoped task-level directly-follows graph
```

The extractor uses timestamps to avoid some false causal edges when activities
overlap. It does not infer gateway nodes or exact process-tree operators. If
parallel activities are assigned sequential timestamps, they are necessarily
observed as an order; different interleavings may then create both directions
between activities across traces. The true structural predecessor and the exact
AND/XOR semantics cannot generally be recovered from XES alone.

There is also an experiment-validity constraint:

- deriving topology only from the training split can omit future-version
  structure;
- deriving topology from the complete XES exposes future-version behavior while
  reconstructing that structure;
- exporting BPMN for every version independently avoids this ambiguity: future
  topology is known as an external process-model artifact, while future event
  behavior remains excluded from training.

### Approved Structure Artifact Contract

Use BPMN as the primary topology source and PTML as the canonical CDLG/process-tree
audit artifact. Keep XES-derived topology only as an optional diagnostic baseline.

The wrapper output bundle should contain:

```text
<dataset>/
  dataset.xes
  manifest.json
  raw/
    cdlg_output.xes
    cdlg_parameters.txt
  models/
    ptml/v1.ptml ... vN.ptml
    bpmn/v1.bpmn ... vN.bpmn
    process_definitions.csv
  configs/
    input.yaml
    resolved.yaml
    bpm_prediction_xes.yaml
    bpm_prediction_bpmn.yaml
  reports/
    processing.json
    methodology.md
    validation.json
    topology_alignment.json
  logs/
    run.log
    cdlg_stdout.log
    cdlg_stderr.log
    traceback.txt  # failed runs only
  failure.json     # failed runs only
  environment.json
  checksums.sha256
```

The generated downstream configuration should use file-based BPMN ingestion,
`structure_from_logs: false`, and the canonical
`gateway_mode: collapse_for_prediction`. The XES mapping should disable classifier
composition for activity identity, consume only `complete` prediction events,
and use only `start` as a pairing transition.

Source evidence in `bpm_prediction`:

- `tools/ingest_topology.py` and `tools/sync_topology.py` route BPMN and XES
  topology ingestion;
- `src/adapters/ingestion/camunda_bpmn_adapter.py` implements file-based BPMN
  catalog and XML loading;
- `src/application/services/bpmn_structure_parser_service.py` builds the rich
  BPMN structure DTO;
- `src/domain/services/topology_projection_alignment.py` implements gateway
  preservation and collapse-for-prediction projection;
- `src/adapters/ingestion/xes_adapter.py` implements lifecycle pairing and
  completion-event projection;
- `src/application/services/topology_extractor_service.py` derives the
  version-scoped XES directly-follows topology.

## Approved Architecture

```text
CLI
  -> ConfigurationLoader
  -> GenerationOrchestrator
       -> CDLGCheckoutVerifier
       -> CDLGParameterRenderer
       -> CDLGProcessRunner
       -> RawArtifactCollector
       -> CDLGMetadataParser
       -> VersionAnnotator
       -> ExecutionEnricher <-> ResourceManager
       -> StructureExporter -> BpmnIdentityNormalizer
       -> DriftMetricsCalculator
       -> UnifiedXesAssembler
       -> EvidenceBuilder
       -> DatasetValidator
```

Component responsibilities:

1. `CLI`: resolves the config path, invokes one use case, prints the final result,
   and maps expected failures to non-zero exit codes. It contains no generation
   rules.
2. `ConfigurationLoader`: parses YAML, applies defaults, validates types and
   cross-field constraints, and produces an immutable resolved configuration.
3. `GenerationOrchestrator`: coordinates the run and artifact staging but does
   not implement subprocess, post-processing, export, or validation rules.
4. `CDLGCheckoutVerifier`: verifies the ignored checkout URL, pinned commit,
   clean tracked state, license, and required entry points.
5. `CDLGParameterRenderer`: translates resolved benchmark settings into CDLG's
   existing line-based parameter file and records every mapped value.
6. `CDLGProcessRunner`: prepares the disposable runtime copy and invokes the
   upstream entry point through the platform launcher. It performs no imports
   from CDLG.
7. `RawArtifactCollector`: captures raw XES, generated metadata, command,
   stdout/stderr, exit code, and timings without mutating the raw source files.
8. `CDLGMetadataParser`: extracts ordered process-tree snapshots, drift points,
   and change metadata from raw CDLG output using benchmark-owned parsing code
   and PM4Py.
9. `VersionAnnotator`: maps raw traces to `v1...vN` from CDLG drift boundaries
   and adds trace/event version attributes.
10. `ExecutionEnricher`: replays raw CDLG activity traces against the extracted
    source tree and adds lifecycle intervals, shared-timeline timestamps,
    parallel overlap, resource waits, and natural carryover without changing the
    CDLG-selected control-flow trace.
11. `ResourceManager`: owns stable activity pools, capacity, queueing, workload,
   assignment, and release rules.
12. `StructureExporter`: exports PTML and BPMN per version and builds the BPMN
   process catalog.
13. `BpmnIdentityNormalizer`: replaces exporter-random identifiers and rewrites
    sequence-flow references without changing process semantics.
14. `DriftMetricsCalculator`: calculates adjacent and cumulative node, edge, and
    candidate-space structural differences from exported version structures.
15. `UnifiedXesAssembler`: assigns global case and instance IDs, attaches version
    metadata, stably orders events, and writes the unified XES.
16. `EvidenceBuilder`: writes input/resolved configs, manifest, processing and
    methodology reports, environment metadata, and checksums.
17. `DatasetValidator`: verifies the completed staged bundle against the strict
    local validation contract.

All modules live under `wrapper/`. No benchmark module imports CDLG or
`bpm_prediction`. CDLG runs only in a child process; `bpm_prediction` consumes
only the finalized files.

## Approved End-to-End Data Flow

1. Load the user YAML, apply defaults and derived values, validate the complete
   contract, and preserve both `input.yaml` and `resolved.yaml`.
2. Calculate exact per-version trace allocations whose sum equals the requested
   dataset total.
3. Verify the external CDLG checkout and render one exact CDLG parameter file
   with one event log, `N-1` sudden drifts, the selected preset, evolution
   proportion, exact traces per process-model version, and disabled explicit
   noise.
4. Create the ignored disposable runtime copy and invoke the unmodified CDLG
   generator through the external-process launcher.
5. Capture command metadata, stdout, stderr, exit code, raw CDLG XES, and raw
   drift metadata before any transformation.
6. Parse CDLG's process-tree snapshots and change boundaries. Verify that the raw
   log represents one evolutionary chain with exactly `N` ordered structures.
7. Annotate raw traces and events as `v1...vN` from CDLG change boundaries and
   verify exact configured counts.
8. Parse each process-tree string with PM4Py, then export one PTML and one
   deterministic BPMN artifact per version and record structural lineage.
9. Replay each raw CDLG activity trace against its source tree. Add lifecycle,
   resources, durations, parallel execution intervals, resource waits, and
   absolute timestamps without inventing a different control-flow trace.
10. Assemble all enriched traces into one XES, retain the start-time version for
    every case, assign global identifiers, and stably order lifecycle events.
11. Calculate adjacent/cumulative drift metrics and generate the complete
    evidence and downstream-configuration bundle.
12. Execute strict
    content validation, close mutable outputs, calculate and verify final
    checksums, and only then publish the completed dataset directory. A failed or
    interrupted run must not appear as a valid published dataset.

The benchmark enriches CDLG traces but does not replace CDLG as the control-flow
trace generator. Raw CDLG activity sequences remain immutable evidence; the
corresponding extracted process tree is the structural oracle used to distinguish
sequence from parallelism during replay.

## Approved Error Handling and Diagnostics

- Reject malformed YAML, invalid types, and inconsistent cross-field values
  before invoking CDLG or creating publishable artifacts.
- Stop the complete run if any process version cannot be generated, evolved,
  replayed, exported, or validated. Never publish a partial XES as a completed
  dataset.
- Treat PTML/BPMN export failures, BPMN identity-normalization failures, and all
  mandatory validation failures as fatal.
- Do not silently retry or regenerate a version to obtain a more desirable
  structural distance, overlap, or event distribution.
- Write the run into a unique staging directory. Publish the final dataset
  directory only after strict validation and checksum generation succeed.
- On failure, preserve the staging evidence under a clearly marked failed-run
  directory with `status: failed`; it must not be discoverable as a valid dataset.
- Do not overwrite an existing dataset directory in the first implementation.
- Use CLI exit code `0` for success, `2` for configuration failure, `3` for CDLG
  generation or scheduling failure, `4` for export or evidence failure, `5` for
  validation failure, `6` for publication/filesystem failure, and `1` for an
  unexpected internal failure.
- Record non-critical observations as warnings without converting failed
  invariants into warnings.

Every run must produce diagnostic logging suitable for separating wrapper, CDLG,
scheduler, exporter, and validator failures:

- assign one run ID and include it in every diagnostic record;
- write `logs/run.log` with timestamps, severity, component, pipeline stage, and
  process-version context;
- support `--log-level INFO|DEBUG`, with `INFO` as the default;
- preserve full chained Python exceptions with `raise ... from error` semantics;
- on failure, write `failure.json` with the failing component, stage, version,
  case or activity context when available, exception class, message, and last
  completed stage;
- on failure, write the complete chained stack trace to `logs/traceback.txt`;
- label non-zero `CDLGProcessRunner` exits as CDLG-stage failures and retain the
  exact child-process command, exit code, stdout, and stderr; preserve Python
  tracebacks only when CDLG writes them to stderr;
- flush diagnostic files before returning the non-zero exit code;
- exclude workstation secrets and use relative artifact paths in publishable
  diagnostics.

## Approved Test Strategy

Use layered tests that verify behavior and contracts without relying on brittle
snapshots of complete generated XES files.

### Unit Tests

- YAML parsing, defaults, normalization, and cross-field validation;
- exact quotient/remainder trace allocation;
- CDLG parameter rendering, checkout verification, process exit-code mapping,
  and raw-artifact selection;
- raw CDLG drift-metadata parsing and version-boundary annotation;
- deterministic task, gateway, event, and sequence-flow BPMN identities;
- lifecycle expansion, exact instance pairing, and stable timestamp tie-breaking;
- resource capacity, queueing, least-workload selection, and no double-booking;
- version activation, natural carryover, and completion-delta statistics;
- manifest, processing report, methodology report, and checksum construction.

### Process-Tree Semantic Tests

- sequence execution;
- XOR branch selection retained from the CDLG trace;
- parallel branches with genuinely overlapping activity intervals;
- loop repetitions retained from the CDLG trace;
- a composed sequence-to-parallel-to-XOR tree;
- replay failure when a CDLG trace cannot be aligned with its source tree.

### Artifact Contract Tests

- one unified XES and exactly `N` BPMN and `N` PTML artifacts;
- PTML and BPMN round-trip parsing through PM4Py;
- complete and unambiguous XES-activity-to-BPMN-task alignment;
- required trace/event attributes and exact lifecycle pairs;
- artifact inventory, relative paths, and checksum integrity;
- no completed dataset publication after an injected generation, export, or
  validation failure;
- preserved failed-run diagnostics with component attribution and traceback.

### End-to-End Tests

- run a small `3 versions x 3 traces` fixture through the real pinned CDLG child
  process, raw artifact capture, metadata parsing, structure export, enrichment,
  XES assembly, evidence creation, and strict local validation;
- keep a larger five-version experiment smoke test optional/slow rather than part
  of the default fast test suite.

### Downstream Compatibility Smoke Test

Run this test in the separate `bpm_prediction` environment rather than importing
that project into CDLG. Verify that:

- the current `XesAdapter` reads the unified XES;
- standard `concept:instance` provides exact lifecycle pairing;
- every BPMN version is accepted by file-based BPMN ingestion;
- `collapse_for_prediction` produces the expected task-level projection;
- activity-to-BPMN alignment coverage is 100% with no ambiguity.

## Open Design Questions

No unresolved first-experiment design questions remain.

## Out of Scope for the First Implementation

- Gradual, incremental, and recurring drift scenarios.
- Runtime integration into `bpm_prediction`.
- BPMN simulation; BPMN is exported as a structure artifact, not used as a
  separate simulation engine.
- `sim:bpmn_element_id` and `sim:bpmn_tag` enrichment.
- Resource-configuration drift, resource calendars, and explicit workload-drift
  scenarios. Resource capacity, queueing, and observed workload remain part of
  the approved base simulation.
- Multiple independent process families in one dataset.

## Approval Gate

The implementation plan can be written only after:

1. all open design questions required for the first experiment are resolved;
2. the architecture, data flow, validation, and testing sections are complete;
3. the specification passes a contradiction and ambiguity review;
4. the user explicitly approves this design specification.
