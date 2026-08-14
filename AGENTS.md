# AGENTS.md

Operating guide for agents working in the independent CDLG structural-drift
benchmark repository.

## Current Objective

Design and implement a configuration-driven benchmark wrapper that executes an
external, pinned CDLG checkout as a separate process and post-processes its raw
XES output into a research-ready versioned dataset bundle.

The benchmark repository must not vendor, track, modify, or import CDLG source
code. `bpm_prediction` consumes generated artifacts later and remains a separate
project and Python environment.

## Mandatory First Read

Read these files before benchmark-related analysis, planning, or implementation:

1. `AGENTS.md`
2. `docs/PRINCIPLES.md`
3. `docs/INDEX.md`
4. `README.md`
5. `docs/wrapper-design.md`

Read upstream CDLG files only from the ignored local `CDLG/` checkout and only
when its execution or output contract must be verified.

## Legal and Repository Boundary

- CDLG upstream: `https://gitlab.uni-mannheim.de/processanalytics/cdlg_tool`
- CDLG license: GPL-3.0
- Benchmark repository license: MIT
- Pinned upstream commit: `cbe1534`
- Ignored local checkout: `CDLG/`
- Integration mechanism: subprocess plus file/stdout/stderr exchange

Hard rules:

- Never add files from `CDLG/` to the benchmark Git index.
- Never copy CDLG source into `wrapper/`, `scripts/`, tests, or documentation.
- Never import `CDLG/src` modules from benchmark Python code.
- Never modify the pinned CDLG source checkout as part of benchmark execution.
- Execute CDLG through a runner script and preserve its exact command, exit code,
  stdout, stderr, URL, commit, configuration, and raw outputs.
- Fail before generation if the configured checkout does not match the required
  commit or contains tracked modifications.
- Treat CDLG as an external GPL-3.0 program; do not claim that this repository
  redistributes or relicenses it.
- Apply the root MIT license only to benchmark-owned code and materials, never to
  CDLG or other third-party artifacts.

## SDD Workflow

The design specification is the source of truth for the benchmark.

1. Record every user-approved requirement and architecture decision in the spec.
2. Automatically adopt only deterministic choices that preserve the approved
   methodology, artifact contract, legal boundary, and implementation scope.
3. Request explicit approval for material methodology, licensing-boundary,
   repository, or complexity changes.
4. Do not implement wrapper behavior until the revised complete design is
   explicitly approved.
5. After approval, create the implementation plan in
   `docs/superpowers/plans/`.
6. Implement from the approved plan with tests and small reviewable changes.
7. If implementation reveals an ambiguity or a required CDLG modification, stop
   and revise the design rather than patching the ignored checkout. Any proposed
   CDLG change requires separate discussion, explicit approval, and documented
   risk acceptance before it can be considered.

Do not rely on chat history as the only record of a decision.

## Confirmed Direction

- One evolutionary chain: `v1 -> v2 -> ... -> vN`.
- Default version count: `5`.
- Default CDLG process-tree preset: `middle`.
- Default adjacent evolution proportion: `0.2`.
- First drift mode: sudden; gradual remains a later controlled scenario.
- Equal trace allocation by version, approximately 20% each for five versions.
- Output: one unified versioned XES and one BPMN plus one PTML per version.
- Topology source: BPMN primary; XES-derived topology fallback/QA only.
- Lifecycle: required `start` and `complete`; optional `assign`, disabled by
  default.
- Pairing: required `concept:instance`; duplicate
  `sim:activity_instance_id` retained for provenance and diagnostics.
- Resources: stable disjoint activity-specific pools, three resources per
  activity by default, with no concurrent double-booking.
- Time: shared absolute timeline, Poisson arrivals, global lognormal activity
  duration, and unforced natural cross-version carryover.
- Noise: disabled for the first experiment.
- Evidence: input/resolved configs, raw CDLG output, command/stdout/stderr,
  manifests, processing/methodology/validation/alignment reports, environment
  metadata, drift metrics, and checksums.

The design specification contains the complete contract and takes precedence
over this summary.

## Planned Locations

- Main orchestration: `wrapper/generate_benchmark.py`
- Version annotation: `wrapper/annotate_versions.py`
- Drift metrics: `wrapper/calculate_drift_metrics.py`
- Supporting wrapper modules: `wrapper/`
- Experiment configs: `configs/`
- External-process launchers: `scripts/run_cdlg.ps1` and `scripts/run_cdlg.sh`
- Canonical wrapper design: `docs/wrapper-design.md`
- Implementation plans: `docs/superpowers/plans/`
- Tests: `tests/`
- Generated artifacts: `outputs/` (ignored)
- External CDLG checkout: `CDLG/` (ignored)

## Python Environments

The benchmark and CDLG must use separately configured Python executables. The
benchmark config or environment may point to the CDLG interpreter, but benchmark
Python code must not activate or import from the CDLG environment.

Do not install CDLG into the benchmark or `bpm_prediction` environment.

## Repository Artifact Language

Write code, identifiers, paths, comments, configuration keys, tests, commit
messages, agent instructions, and stable technical labels in English. Human-
facing documentation may be Ukrainian. Use standard Markdown links.

## Documentation Update Rule

Before finishing any benchmark-related task, check documentation impact:

- requirement or architecture change: update the design specification;
- legal or repository-boundary change: update `AGENTS.md`, `README.md`, and the
  design specification;
- CLI or configuration change: update `README.md` and the design specification;
- implementation-plan change: update the active file in
  `docs/superpowers/plans/`;
- discovered CDLG behavior conflicting with the spec: stop and reconcile the
  specification first.

Every final task summary must state which documentation files were updated or why
no documentation update was required.

## How Agents Work Here

1. Read the mandatory files and the relevant source specification before making
   changes.
2. Preserve the external `CDLG/` boundary and do not modify application code
   during documentation-only tasks.
3. Keep changes small, evidence-based, and linked from `docs/INDEX.md`.
4. For meaningful implementation work, define acceptance criteria before coding,
   run focused validation, then run the repository's available outer checks.
5. Update `docs/ROADMAP.md` when scope, status, or open questions change.
