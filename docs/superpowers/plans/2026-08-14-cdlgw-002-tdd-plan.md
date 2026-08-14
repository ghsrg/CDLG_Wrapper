# CDLGW-002 External CDLG Execution and Raw Artifact Capture TDD Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` only after the user approves execution. Track every task by its `CDLGW-002-TNN` ID.

**Plan ID:** `CDLGW-002`  
**Slice status:** `in-progress`; implementation not started  
**Goal:** Verify a pinned external CDLG checkout, prepare an ignored disposable runtime, execute stock CDLG as a child process, and preserve one raw XES plus its `drift_info.csv` and diagnostics.

**Architecture:** All interaction with CDLG is through `git` commands, copied runtime files, subprocess arguments, standard streams, exit status, and generated files. The runner never imports `CDLG/src`, writes into `CDLG/`, or changes upstream source. It does not annotate, enrich, parse, or publish the log; those responsibilities begin in later slices.

**Tech Stack:** Python 3.10+, standard library (`subprocess`, `shutil`, `pathlib`, `time`, `dataclasses`), pytest, existing wrapper configuration/errors.

---

## Sources Read and Authority

1. [AGENTS.md](../../../AGENTS.md) — legal boundary, pinned commit, and environment separation.
2. [Wrapper Design](../../wrapper-design.md) — External CDLG Execution Contract and error handling.
3. [Roadmap](../../ROADMAP.md) — `CDLGW-002` scenarios and evidence IDs.
4. [MVP implementation plan](2026-08-14-cdlg-wrapper-mvp.md) — Task 3.
5. [CDLGW-001 TDD plan](2026-08-14-cdlgw-001-tdd-plan.md) — resolved configuration contract.
6. External pinned CDLG checkout (read-only verification): `generate_collection_of_logs.py`, `src/configurations.py`, `src/input_parameters/default`, `src/utilities.py`, and `src/data_classes/class_collection.py`.

## Confirmed Upstream Contract

- Entry point: `generate_collection_of_logs.py`.
- Parameter file: `src/input_parameters/default` in the child runtime.
- Output root: `output/`; each run creates `<parameter_name>_<unix_timestamp>/`.
- Required raw files for one log: exactly one `*.xes` and `drift_info.csv`.
- The collection engine has no CLI parameter-file argument; a disposable runtime copy is therefore required to preserve the pinned checkout.

## Assumptions and Open Questions

- `cdlg.python_executable` is required by the runner. A missing value is a configuration-stage failure; executable availability is verified before child execution.
- Runtime copies are created only under ignored `work/<run-id>/cdlg-runtime`; staging output is caller-provided and must be outside `CDLG/`.
- The runner preserves the upstream default parameter template and changes only approved wrapper-mapped fields; no new CDLG parameter key is introduced.
- Real CDLG end-to-end execution remains `CDLGW-006`. This slice tests process behavior with a fake executable/fixture runtime and tests the real checkout only through read-only Git and file-contract checks.
- No unresolved acceptance or source-priority question blocks the plan.

## Files

| Path | Action | Responsibility |
| --- | --- | --- |
| `wrapper/cdlg_runner.py` | Create | Checkout verification, runtime-copy preparation, parameter rendering, child execution, raw collection. |
| `scripts/run_cdlg.ps1` | Create | Thin Windows launcher accepting Python executable and runtime directory. |
| `scripts/run_cdlg.sh` | Create | Thin POSIX launcher accepting Python executable and runtime directory. |
| `tests/test_cdlg_runner.py` | Create | BDD-style unit/integration-boundary tests with fake checkouts and fake child executables. |
| `tests/conftest.py` | Create | Reusable fake-CDLG checkout and `git` fixture helpers. |
| `README.md` | Modify | Add external-CDLG runner prerequisites only after tests pass. |
| `docs/ROADMAP.md` | Modify | Attach evidence after passing tests; do not mark slice complete. |

## BDD Agent Scenario Cards

### `CDLGW-002-AC01` — Reject invalid external CDLG checkouts before generation

- **Intent:** prevent a benchmark run from silently using the wrong, dirty, incomplete, or unlicensed upstream source.
- **Priority:** P0.
- **Sources:** [External CDLG Execution Contract](../../wrapper-design.md#external-cdlg-execution-contract), [Legal and Repository Boundary](../../../AGENTS.md#legal-and-repository-boundary).
- **Given:** a checkout with a wrong origin URL, non-pinned commit, tracked modification, absent GPL license, or missing `generate_collection_of_logs.py`.
- **When:** `verify_checkout()` is called.
- **Then:** it raises `CdlgExecutionError` before a runtime copy or child process is created, identifying the failed invariant.
- **Independent verification:** `python -m pytest tests/test_cdlg_runner.py -k checkout -v`.
- **TDD obligation:** `CDLGW-002-T01` RED, `CDLGW-002-T02` GREEN, `CDLGW-002-T07` REFACTOR.
- **Evidence:** `CDLGW-002-EV01`.

### `CDLGW-002-AC02` — Run a disposable CDLG runtime and preserve unambiguous raw evidence

- **Intent:** execute CDLG as an external program without mutating the pinned checkout and retain enough evidence to diagnose the child process.
- **Priority:** P0.
- **Sources:** [External CDLG Execution Contract](../../wrapper-design.md#external-cdlg-execution-contract), [Approved Error Handling and Diagnostics](../../wrapper-design.md#approved-error-handling-and-diagnostics).
- **Given:** a verified checkout, resolved config with an interpreter, and a fake child that produces one XES plus `drift_info.csv`.
- **When:** `run_cdlg()` executes.
- **Then:** it creates an ignored runtime copy, writes the mapped upstream parameter file only there, captures command/stdout/stderr/exit code/elapsed time, and copies the two raw files unchanged into staging.
- **And given:** a non-zero child exit, zero XES files, or multiple XES files.
- **Then:** it raises `CdlgExecutionError`, retains diagnostics, and does not claim a raw artifact result.
- **Independent verification:** `python -m pytest tests/test_cdlg_runner.py -k "runtime or process or artifacts" -v`.
- **TDD obligation:** `CDLGW-002-T03` RED, `CDLGW-002-T04` GREEN, `CDLGW-002-T05` RED, `CDLGW-002-T06` GREEN, `CDLGW-002-T07` REFACTOR.
- **Evidence:** `CDLGW-002-EV02`, `CDLGW-002-EV03`, `CDLGW-002-EV04`.

## Numbered TDD Tasks

### `CDLGW-002-T01` — RED for `CDLGW-002-AC01`

- Create `tests/conftest.py` with a helper that initializes a temporary Git repository, commits a minimal CDLG-shaped tree, and assigns the required origin URL.
- Create checkout behavior tests in `tests/test_cdlg_runner.py`.

```python
import pytest

from wrapper.cdlg_runner import verify_checkout
from wrapper.errors import CdlgExecutionError


@pytest.mark.parametrize("defect", ["wrong_origin", "wrong_commit", "dirty", "missing_license", "missing_entrypoint"])
def test_given_invalid_checkout_when_verified_then_generation_is_rejected(fake_cdlg_checkout, defect):
    checkout = fake_cdlg_checkout(defect=defect)

    with pytest.raises(CdlgExecutionError, match="checkout"):
        verify_checkout(checkout, required_commit="a" * 40)
```

- Run: `python -m pytest tests/test_cdlg_runner.py -k checkout -v`
- Expected: FAIL because `wrapper.cdlg_runner` does not exist.
- Capture failure as `CDLGW-002-EV01-RED`.

### `CDLGW-002-T02` — GREEN for `CDLGW-002-AC01`

- Implement `CheckoutInfo` and `verify_checkout(checkout: Path, required_commit: str) -> CheckoutInfo` in `wrapper/cdlg_runner.py`.
- Invoke only external Git commands with argument lists, never shell strings:

```python
def _git(checkout: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(checkout), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise CdlgExecutionError(f"CDLG checkout git command failed: {' '.join(args)}")
    return result.stdout.strip()
```

- Verify origin URL, exact HEAD, empty `git status --porcelain`, `LICENSE`, `generate_collection_of_logs.py`, and `src/input_parameters/default` before returning success.
- Run: `python -m pytest tests/test_cdlg_runner.py -k checkout -v`
- Expected: PASS.
- Capture result as `CDLGW-002-EV01`.

### `CDLGW-002-T03` — RED for runtime isolation and parameter rendering in `CDLGW-002-AC02`

- Add tests proving that the source checkout remains byte-identical while a runtime is built under `work/<run-id>/cdlg-runtime`.

```python
def test_given_verified_checkout_when_runtime_prepared_then_only_ignored_copy_changes(fake_cdlg_checkout, tmp_path):
    checkout = fake_cdlg_checkout()
    source_parameter = (checkout / "src/input_parameters/default").read_text(encoding="utf-8")

    runtime = prepare_runtime_copy(checkout, work_root=tmp_path / "work", run_id="run-001")
    render_parameters(runtime, resolved_config_with_total_17())

    assert runtime == tmp_path / "work/run-001/cdlg-runtime"
    assert (checkout / "src/input_parameters/default").read_text(encoding="utf-8") == source_parameter
    assert ".git" not in {path.name for path in runtime.iterdir()}
```

- Add a renderer test that checks these exact mapped lines:
  `Process_tree_complexity`, `Process_tree_evolution_proportion`,
  `Number_event_logs: 1`, `Number_traces_per_process_model_version`,
  `Change_type: sudden`, `Drift_types: sudden`, `Number_drifts_per_log`, and
  `Noise: False`.
- Assert all unmapped lines remain unchanged from the copied upstream template.
- Run: `python -m pytest tests/test_cdlg_runner.py -k runtime -v`
- Expected: FAIL because runtime and renderer functions do not exist.
- Capture failure as `CDLGW-002-EV02-RED`.

### `CDLGW-002-T04` — GREEN for runtime isolation and parameter rendering

- Implement `prepare_runtime_copy()` with `shutil.copytree()` and an ignore set for `.git`, `.venv`, `venv`, `env`, `.idea`, `.vscode`, `__pycache__`, and `documentation`.
- Reject a destination that resolves inside the checkout or an existing runtime directory.
- Implement `render_parameters()` by parsing the copied `default` template into ordered `key: value` lines, replacing only mapped keys, rejecting a missing/duplicate required key, and writing UTF-8 with a trailing newline.
- The value mapping must use the `ResolvedConfig` values already supplied by `CDLGW-001`; do not add wrapper-only keys to the CDLG file.
- Run: `python -m pytest tests/test_cdlg_runner.py -k runtime -v`
- Expected: PASS.
- Capture result as `CDLGW-002-EV02`.

### `CDLGW-002-T05` — RED for process execution and raw-artifact collection in `CDLGW-002-AC02`

- Add a fake Python executable fixture that writes either: one `log_1.xes` plus `drift_info.csv`; no XES; two XES files; or exits with code `17` after writing stderr.
- Add behavior tests.

```python
def test_given_one_raw_xes_and_drift_csv_when_child_succeeds_then_artifacts_are_copied(tmp_path):
    result = run_cdlg(
        runtime_dir=prepared_runtime(tmp_path),
        python_executable=fake_python(tmp_path, mode="success"),
        staging_raw_dir=tmp_path / "staging/raw",
    )

    assert result.exit_code == 0
    assert result.raw_xes_path.name == "cdlg_output.xes"
    assert result.raw_drift_csv_path.name == "drift_info.csv"
    assert result.stdout_path.read_text(encoding="utf-8")


@pytest.mark.parametrize("mode", ["nonzero", "no_xes", "multiple_xes", "missing_csv"])
def test_given_invalid_child_output_when_collected_then_cdlg_execution_error(tmp_path, mode):
    with pytest.raises(CdlgExecutionError):
        run_cdlg(
            runtime_dir=prepared_runtime(tmp_path),
            python_executable=fake_python(tmp_path, mode=mode),
            staging_raw_dir=tmp_path / "staging/raw",
        )
```

- Run: `python -m pytest tests/test_cdlg_runner.py -k "process or artifacts" -v`
- Expected: FAIL because `run_cdlg` does not exist.
- Capture failure as `CDLGW-002-EV03-RED`.

### `CDLGW-002-T06` — GREEN for process execution and raw-artifact collection

- Implement `run_cdlg()` with `subprocess.run()` through the platform launcher (`scripts/run_cdlg.ps1` on Windows or `scripts/run_cdlg.sh` on POSIX), passing the configured Python executable and runtime directory as separate arguments, with `capture_output=True`, `text=True`, and no shell.
- Persist `cdlg_stdout.log` and `cdlg_stderr.log` in the caller-provided diagnostics directory before handling success/failure. Return an immutable result containing command, exit code, elapsed seconds, output paths, and copied raw paths.
- On non-zero exit, missing output root, zero/multiple XES candidates, or missing `drift_info.csv`, raise `CdlgExecutionError` containing the invariant and keep logs available.
- Copy selected source files with `shutil.copy2()` to `raw/cdlg_output.xes`, `raw/drift_info.csv`, and `raw/cdlg_parameters.txt`; never post-process source files.
- Run: `python -m pytest tests/test_cdlg_runner.py -k "process or artifacts" -v`
- Expected: PASS.
- Capture result as `CDLGW-002-EV03`.

### `CDLGW-002-T07` — REFACTOR, launcher scripts, documentation, and traceability

- Create thin launchers with no generation logic:

```powershell
param(
    [Parameter(Mandatory = $true)][string]$PythonExecutable,
    [Parameter(Mandatory = $true)][string]$RuntimeDirectory
)
Set-Location -LiteralPath $RuntimeDirectory
& $PythonExecutable "generate_collection_of_logs.py"
exit $LASTEXITCODE
```

```sh
#!/usr/bin/env sh
set -eu
cd "$2"
"$1" generate_collection_of_logs.py
```

- Make `run_cdlg()` select the platform launcher deterministically from the current operating system; direct invocation of CDLG's entry point is not an alternative execution path.
- Update README with runner prerequisites: separate CDLG checkout/interpreter, pinned revision, and no import/install boundary. Do not claim the full CLI exists yet.
- Add `CDLGW-002-EV01` through `EV04` references to Roadmap implementation evidence; do not mark the slice complete.
- Run the full slice suite:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_errors.py tests/test_config.py tests/test_trace_allocation.py tests/test_cdlg_runner.py -v
```

- Expected: PASS; capture as `CDLGW-002-EV04`.
- Commit: `git add wrapper/cdlg_runner.py scripts tests README.md docs/ROADMAP.md && git commit -m "feat: add external CDLG runner"`.

## Verification Matrix

| Evidence ID | Scenario | Command | Expected result |
| --- | --- | --- | --- |
| `CDLGW-002-EV01` | `AC01` | `python -m pytest tests/test_cdlg_runner.py -k checkout -v` | All invalid-checkout guards pass. |
| `CDLGW-002-EV02` | `AC02` | `python -m pytest tests/test_cdlg_runner.py -k runtime -v` | Runtime isolation and template rendering pass. |
| `CDLGW-002-EV03` | `AC02` | `python -m pytest tests/test_cdlg_runner.py -k "process or artifacts" -v` | Success and child/output failure behavior pass. |
| `CDLGW-002-EV04` | all | `.venv\\Scripts\\python.exe -m pytest tests/test_errors.py tests/test_config.py tests/test_trace_allocation.py tests/test_cdlg_runner.py -v` | Full prior-plus-slice suite passes. |

## Forbidden Scope

- No modifications, staging, vendoring, or imports of `CDLG/` source.
- No raw XES parsing, version annotation, BPMN/PTML export, lifecycle enrichment, or dataset publication.
- No `bpm_prediction` import, environment activation, or code change.
- No gradual/incremental/recurring drift support, retries, or regeneration policy.
- No real experimental dataset acceptance; the pinned real-CDLG end-to-end test belongs to `CDLGW-006`.

## Approval Gate

Reply `OK EXECUTE CDLGW-002` to authorize execution of this TDD plan.

Reply `CHANGE CDLGW-002` followed by corrections to revise this plan.

Generic `OK` approves the plan content only; it does not authorize implementation.
