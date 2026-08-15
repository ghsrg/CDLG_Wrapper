# CDLGW-005 Validation, Publication, and CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Steps use checkbox syntax.

**Goal:** Strictly validate a staged dataset bundle, publish only valid immutable bundles, and expose the wrapper through one non-interactive CLI.

**Architecture:** `validation.py` verifies existing raw/XES/BPMN/PTML/evidence artifacts without importing CDLG or `bpm_prediction`. `publication.py` atomically promotes a valid staging directory or retains a failed diagnostic bundle. `wrapper.generate_benchmark` provides the module-invoked CLI and maps typed errors to documented exit codes.

**Tech Stack:** Python 3.10, PM4Py, stdlib `hashlib/json/pathlib`, PyYAML, pytest.

---

**Plan ID:** `CDLGW-005` · **Status:** executed in main without commit per user instruction.

## BDD Agent Scenario Cards

| ID | Given / When / Then | Evidence |
| --- | --- | --- |
| `CDLGW-005-AC01` | Given a staged bundle with a missing model, wrong trace count, invalid lifecycle pair, duplicate instance ID, resource overlap, broken BPMN reference, or tampered checksum, when validation runs, then it raises `ValidationError`; publication is refused and diagnostics remain under a failed-run directory. | `CDLGW-005-EV01`: `pytest tests/test_validation.py tests/test_publication.py -v` |
| `CDLGW-005-AC02` | Given a valid config and a stubbed valid pipeline, when `python wrapper/generate_benchmark.py --config <path>` runs, then it prints the published dataset path and exits `0`; expected wrapper errors use the documented non-zero mapping. | `CDLGW-005-EV02`: `pytest tests/test_cli.py -v` |

## TDD Tasks

### `CDLGW-005-T01` — RED/GREEN strict bundle validation

**Files:** create `wrapper/validation.py`, create `tests/test_validation.py`.

- [x] Write failing parameterized tests for each AC01 corruption plus a valid minimal bundle.
- [x] Run `\.venv\Scripts\python.exe -m pytest tests/test_validation.py -v`; expected failure observed as missing `wrapper.validation`.
- [x] Implement `validate_bundle(staging_dir, resolved_config) -> ValidationReport`: validate counts/all required XES fields and lifecycle pairs, resource intervals, BPMN/PTML parseability/references/activity alignment, relative evidence paths, and checksums; aggregate diagnostics then raise `ValidationError`.
- [x] Re-run; PASS observed. Commit step intentionally skipped because execution was requested without commit.

### `CDLGW-005-T02` — RED/GREEN safe publication and failed diagnostics

**Files:** create `wrapper/publication.py`, create `tests/test_publication.py`.

- [x] Write failing tests that assert valid staging moves once to a unique final directory, existing final target is never overwritten, and invalid staging writes `failure.json`/traceback under `outputs/failed/`.
- [x] Run `\.venv\Scripts\python.exe -m pytest tests/test_publication.py -v`; expected failure observed as missing `wrapper.publication`.
- [x] Implement `publish_validated_bundle` using same-filesystem rename after validation; implement `retain_failure` with relative artifact references only.
- [x] Re-run; PASS observed. Commit step intentionally skipped because execution was requested without commit.

### `CDLGW-005-T03` — RED/GREEN CLI orchestration

**Files:** create `wrapper/generate_benchmark.py`, create `tests/test_cli.py`, modify `README.md` and `docs/wrapper-design.md` for the actual command.

- [x] Write subprocess/monkeypatch-style tests for missing config, expected typed error exit codes, valid run path output, and stderr behavior.
- [x] Run `\.venv\Scripts\python.exe -m pytest tests/test_cli.py -v`; expected failure observed as missing `wrapper.generate_benchmark`.
- [x] Implement argparse `--config`, injectable orchestration boundary for existing stages, and `exit_code_for` mapping; no real CDLG run in unit tests.
- [x] Re-run; PASS observed. Commit step intentionally skipped because execution was requested without commit.

### `CDLGW-005-T04` — REFACTOR and closure

- [x] Run focused AC commands (`EV01`, `EV02`), then `\.venv\Scripts\python.exe -m pytest tests -v`, `\.venv\Scripts\python.exe -m compileall -q wrapper`, import-boundary scan, and `git diff --check` (`EV03`).
- [x] Create ignored closure report and update Roadmap only after independent closure verification (`EV04`).

**Forbidden scope:** real CDLG execution, downstream `bpm_prediction` execution, gradual drift, or changes to dataset methodology.

Reply `OK EXECUTE CDLGW-005` to authorize execution. Reply `CHANGE CDLGW-005` with corrections.
