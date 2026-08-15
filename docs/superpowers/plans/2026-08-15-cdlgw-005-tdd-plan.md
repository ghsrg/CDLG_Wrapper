# CDLGW-005 Validation, Publication, and CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans task-by-task. Steps use checkbox syntax.

**Goal:** Strictly validate a staged dataset bundle, publish only valid immutable bundles, and expose the wrapper through one non-interactive CLI.

**Architecture:** `validation.py` verifies existing raw/XES/BPMN/PTML/evidence artifacts without importing CDLG or `bpm_prediction`. `publication.py` atomically promotes a valid staging directory or retains a failed diagnostic bundle. `generate_benchmark.py` orchestrates existing modules and maps typed errors to documented exit codes.

**Tech Stack:** Python 3.10, PM4Py, stdlib `hashlib/json/pathlib`, PyYAML, pytest.

---

**Plan ID:** `CDLGW-005` · **Status:** proposed.

## BDD Agent Scenario Cards

| ID | Given / When / Then | Evidence |
| --- | --- | --- |
| `CDLGW-005-AC01` | Given a staged bundle with a missing model, wrong trace count, invalid lifecycle pair, duplicate instance ID, resource overlap, broken BPMN reference, or tampered checksum, when validation runs, then it raises `ValidationError`; publication is refused and diagnostics remain under a failed-run directory. | `CDLGW-005-EV01`: `pytest tests/test_validation.py tests/test_publication.py -v` |
| `CDLGW-005-AC02` | Given a valid config and a stubbed valid pipeline, when `python wrapper/generate_benchmark.py --config <path>` runs, then it prints the published dataset path and exits `0`; expected wrapper errors use the documented non-zero mapping. | `CDLGW-005-EV02`: `pytest tests/test_cli.py -v` |

## TDD Tasks

### `CDLGW-005-T01` — RED/GREEN strict bundle validation

**Files:** create `wrapper/validation.py`, create `tests/test_validation.py`.

- [ ] Write failing parameterized tests for each AC01 corruption plus a valid minimal bundle.
- [ ] Run `\.venv\Scripts\python.exe -m pytest tests/test_validation.py -v`; expect failure.
- [ ] Implement `validate_bundle(staging_dir, resolved_config) -> ValidationReport`: validate counts/all required XES fields and lifecycle pairs, resource intervals, BPMN/PTML parseability/references/activity alignment, relative evidence paths, and checksums; aggregate diagnostics then raise `ValidationError`.
- [ ] Re-run; expect PASS. Commit: `git add wrapper/validation.py tests/test_validation.py && git commit -m "feat: validate dataset bundles"`.

### `CDLGW-005-T02` — RED/GREEN safe publication and failed diagnostics

**Files:** create `wrapper/publication.py`, create `tests/test_publication.py`.

- [ ] Write failing tests that assert valid staging moves once to a unique final directory, existing final target is never overwritten, and invalid staging writes `failure.json`/traceback under `outputs/failed/`.
- [ ] Run `\.venv\Scripts\python.exe -m pytest tests/test_publication.py -v`; expect failure.
- [ ] Implement `publish_validated_bundle` using same-filesystem rename after validation; implement `retain_failure` with relative artifact references only.
- [ ] Re-run; expect PASS. Commit: `git add wrapper/publication.py tests/test_publication.py && git commit -m "feat: publish validated datasets"`.

### `CDLGW-005-T03` — RED/GREEN CLI orchestration

**Files:** create `wrapper/generate_benchmark.py`, create `tests/test_cli.py`, modify `README.md` and `docs/wrapper-design.md` for the actual command.

- [ ] Write failing subprocess/monkeypatch tests for missing config, expected typed error exit codes, valid run path output, and no secret/absolute-path leakage.
- [ ] Run `\.venv\Scripts\python.exe -m pytest tests/test_cli.py -v`; expect failure.
- [ ] Implement argparse `--config`, orchestration of the existing stages, validation before promotion, and `exit_code_for` mapping; no real CDLG run in unit tests.
- [ ] Re-run; expect PASS. Commit: `git add wrapper/generate_benchmark.py tests/test_cli.py README.md docs/wrapper-design.md && git commit -m "feat: add benchmark CLI"`.

### `CDLGW-005-T04` — REFACTOR and closure

- [ ] Run focused AC commands (`EV01`, `EV02`), then `\.venv\Scripts\python.exe -m pytest tests -v`, `\.venv\Scripts\python.exe -m compileall -q wrapper`, import-boundary scan, and `git diff --check` (`EV03`).
- [ ] Create ignored closure report and update Roadmap only after independent closure verification (`EV04`).

**Forbidden scope:** real CDLG execution, downstream `bpm_prediction` execution, gradual drift, or changes to dataset methodology.

Reply `OK EXECUTE CDLGW-005` to authorize execution. Reply `CHANGE CDLGW-005` with corrections.
