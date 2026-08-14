# CDLG Structural Drift Benchmark

This repository contains an independent benchmark wrapper for generating and
post-processing structural-drift datasets with CDLG.

CDLG is not vendored, copied, modified, or tracked by this repository. It is an
external GPL-3.0 program that must be obtained separately and is invoked as a
separate process. Integration uses configuration files, process exit status,
standard output/error, raw XES files, and exported drift metadata.

## Repository Boundary

```text
benchmark repository
  -> external-process runner
  -> ignored local CDLG checkout
  -> raw XES and drift metadata
  -> benchmark post-processing
  -> versioned XES, BPMN/PTML, topology, and drift metrics
```

The benchmark wrapper must not import CDLG Python modules. CDLG source code,
virtual environments, and runtime copies remain outside the benchmark's Git
history.

## Pinned CDLG Revision

- Upstream: <https://gitlab.uni-mannheim.de/processanalytics/cdlg_tool>
- License: GNU General Public License v3.0
- Pinned upstream commit: `cbe1534`

Prepare the ignored local checkout:

```powershell
git clone https://gitlab.uni-mannheim.de/processanalytics/cdlg_tool CDLG
git -C CDLG checkout cbe1534
```

The runner must verify the actual CDLG commit before every benchmark run and
record it in the generated manifest and methodology report.

## Planned Layout

```text
wrapper/
  generate_benchmark.py
  annotate_versions.py
  calculate_drift_metrics.py
configs/
  cdlg_experiment.yaml
scripts/
  run_cdlg.ps1
  run_cdlg.sh
docs/
  superpowers/specs/
CDLG/                       # ignored external upstream checkout
README.md
AGENTS.md
```

## Planned Pipeline

1. Resolve and preserve the benchmark configuration.
2. Execute the pinned, unmodified CDLG checkout as a separate process.
3. Preserve raw CDLG XES, drift metadata, stdout, stderr, exit code, and runtime
   provenance.
4. Annotate every trace and event with its process version.
5. Parse CDLG process-tree snapshots from raw output and export one PTML and one
   deterministic BPMN per version.
6. Add the approved lifecycle, resource, timestamp, and natural-carryover model.
7. Calculate structural drift metrics and topology-alignment evidence.
8. Validate and publish one unified research-ready dataset bundle.

Implementation has not started. The revised subprocess-based design
specification must be approved before an implementation plan is written.

## Licensing Note

The benchmark wrapper and its repository-owned materials are licensed under the
MIT License in `LICENSE`.

This repository does not redistribute CDLG. Users obtain CDLG from its upstream
repository and are responsible for complying with its GPL-3.0 license. Generated
artifacts preserve the exact CDLG URL, commit, configuration, and execution
provenance. This repository documentation is not legal advice.
