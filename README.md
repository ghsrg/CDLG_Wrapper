# CDLG Adapter for bpm_prediction

This repository is an adapter layer for
[bpm_prediction](https://github.com/ghsrg/bpm_prediction). It runs an external
installation of CDLG and converts CDLG-generated event logs into the
version-aware XES, BPMN/PTML, and provenance artifacts required for structural
drift experiments in `bpm_prediction`.

It is **not** another process simulator, a CDLG fork, or a prediction system.
CDLG remains the upstream generator; `bpm_prediction` remains the system that
builds structure, trains models, and evaluates prediction experiments.

## Responsibilities

```text
CDLG
  -> raw simulated XES and drift information
  -> this adapter
  -> versioned XES, BPMN/PTML per version, topology and provenance evidence
  -> bpm_prediction
  -> structural analysis, training, and evaluation
```

| Component | Responsibility |
| --- | --- |
| CDLG | Generates process trees, simulated traces, and its native drift behavior. |
| This repository | Runs CDLG externally, reconstructs version artifacts, enriches and combines logs, and records reproducibility evidence. |
| bpm_prediction | Consumes the resulting dataset for topology construction, statistics, prediction, and evaluation. |

The adapter preserves CDLG as the source of simulated control-flow. Its
post-processing adds the experiment contract needed by `bpm_prediction`; it
does not reimplement or modify CDLG's generator.

## Planned dataset contract

For one experiment, the adapter will produce:

- one unified, version-annotated XES log;
- one BPMN and one PTML representation for each process version;
- version allocation, drift/topology metrics, and validation reports;
- the resolved configuration, external CDLG revision, command trace, and a
  machine-readable provenance manifest stored with the generated dataset.

The intended default experiment uses five configurable versions with roughly
equal trace shares, a shared timeline, `start` and `complete` lifecycle events,
optional `assign` events, and stable activity-specific resource pools.

## Repository boundary

The upstream CDLG clone is an external runtime dependency located locally in
`CDLG/`. It is ignored by Git and is never copied, vendored, imported as a
Python dependency, or modified by this repository. The adapter invokes CDLG
only through a documented command boundary.

The currently pinned upstream revision is:

```text
Repository: https://gitlab.uni-mannheim.de/processanalytics/cdlg_tool
Commit:     cbe1534de94f06a3f1cca460b079d436f604445e
```

Before reproducing an experiment, clone CDLG separately, check out this commit,
and create its Python 3.10 environment according to CDLG's own requirements.

## Status

The first-experiment architecture and specification are approved. Wrapper
implementation has not started yet; the next step is the implementation plan.

## License

The adapter code and documentation in this repository are released under the
[MIT License](LICENSE). CDLG remains a separate upstream project with its own
license and terms.
