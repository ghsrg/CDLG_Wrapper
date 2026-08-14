# CDLGW-001 Bootstrap and Configuration Contract TDD Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` or `superpowers:subagent-driven-development` only after the user approves execution. Track every task by its `CDLGW-001-TNN` ID.

**Plan ID:** `CDLGW-001`  
**Slice status:** `in-progress`; implementation not started  
**Goal:** Establish the wrapper package, typed expected failures, and a validated YAML configuration that resolves the approved first-experiment defaults and exact trace allocation.

**Architecture:** This slice is pure benchmark-owned configuration code. It must not invoke CDLG, inspect its checkout, write generated datasets, import `bpm_prediction`, or schedule activities. The resolved configuration supplies the contract required by `CDLGW-002` and later slices.

**Tech Stack:** Python 3.10+, standard library dataclasses/math/pathlib, PyYAML, pytest.

---

## Sources Read and Authority

1. [AGENTS.md](../../../AGENTS.md) — external-boundary and workflow rules.
2. [Project Principles](../../PRINCIPLES.md) — complete-pipeline and reproducibility principles.
3. [Wrapper Design](../../wrapper-design.md) — configuration, trace-allocation, error, and evidence contracts.
4. [Roadmap](../../ROADMAP.md) — `CDLGW-001` scenarios and status.
5. [MVP implementation plan](2026-08-14-cdlg-wrapper-mvp.md) — Tasks 1–2 decomposition.

## Assumptions and Open Questions

- The committed example config supplies `dataset.total_traces`; this slice does not impose a methodology-level default count.
- Scheduler distribution parameters have no approved numeric defaults and therefore remain outside this slice; `CDLGW-004` will add them before any timing simulation exists.
- `cdlg.python_executable` is accepted as an opaque non-empty path string here and is verified only by `CDLGW-002`.
- No unresolved acceptance, source-priority, or verification question blocks this slice.

## Files

| Path | Action | Responsibility |
| --- | --- | --- |
| `requirements.txt` | Create | Wrapper dependencies only: PM4Py, PyYAML, pytest. |
| `wrapper/__init__.py` | Create | Marks benchmark-owned package. |
| `wrapper/errors.py` | Create | Expected exception classes and CLI exit-code mapping. |
| `wrapper/config.py` | Create | Frozen configuration types, YAML loading, defaults, validation, allocation. |
| `configs/cdlg_experiment.yaml` | Create | Publishable first-experiment example; no workstation-specific absolute paths. |
| `tests/test_errors.py` | Create | BDD-style unit tests for `CDLGW-001-AC03`. |
| `tests/test_config.py` | Create | BDD-style unit tests for `CDLGW-001-AC01`. |
| `tests/test_trace_allocation.py` | Create | BDD-style unit tests for `CDLGW-001-AC02`. |
| `README.md` | Modify | Add only the wrapper-environment setup command after dependencies exist. |
| `docs/ROADMAP.md` | Modify | Add evidence references after passing tests; do not mark slice complete. |

## BDD Agent Scenario Cards

### `CDLGW-001-AC01` — Resolve a valid first-experiment configuration

- **Intent:** make all first-experiment defaults explicit, immutable, and auditable.
- **Priority:** P0.
- **Sources:** [Configuration and CLI Contract](../../wrapper-design.md#configuration-and-cli-contract), [Confirmed Direction](../../../AGENTS.md#confirmed-direction).
- **Given:** a YAML file with `dataset.total_traces: 1000` and no optional first-experiment overrides.
- **When:** `load_config(path)` is called.
- **Then:** it returns a frozen configuration with `version_count=5`, IDs `v1..v5`, `middle`, `0.2`, sudden drift, disabled noise and `assign`, three resources per activity, and a relative `CDLG/` checkout path.
- **Independent verification:** `python -m pytest tests/test_config.py -v`.
- **TDD obligation:** `CDLGW-001-T03` RED, `CDLGW-001-T04` GREEN, `CDLGW-001-T09` REFACTOR.
- **Evidence:** `CDLGW-001-EV01` records the focused passing command/result.

### `CDLGW-001-AC02` — Preserve exact trace allocation despite CDLG's shared count

- **Intent:** ensure final dataset proportions are deterministic and sum exactly to the requested total.
- **Priority:** P0.
- **Sources:** [Trace Allocation Contract](../../wrapper-design.md#trace-allocation-contract).
- **Given:** `total_traces=17` and `version_count=5`.
- **When:** allocation resolves.
- **Then:** retained counts equal `(4, 4, 3, 3, 3)`, their sum is `17`, version IDs remain ordered, and the future CDLG shared count is `4`.
- **Independent verification:** `python -m pytest tests/test_trace_allocation.py -v`.
- **TDD obligation:** `CDLGW-001-T05` RED, `CDLGW-001-T06` GREEN, `CDLGW-001-T09` REFACTOR.
- **Evidence:** `CDLGW-001-EV02` records the focused passing command/result.

### `CDLGW-001-AC03` — Map expected failures to stable CLI codes

- **Intent:** make later CLI diagnostics machine-actionable without conflating expected and unexpected failures.
- **Priority:** P1.
- **Sources:** [Approved Error Handling and Diagnostics](../../wrapper-design.md#approved-error-handling-and-diagnostics).
- **Given:** each expected wrapper error and an unexpected `RuntimeError`.
- **When:** `exit_code_for(error)` is called.
- **Then:** configuration/CDLG/artifact/validation/publication errors map to `2/3/4/5/6`; unexpected errors map to `1`.
- **Independent verification:** `python -m pytest tests/test_errors.py -v`.
- **TDD obligation:** `CDLGW-001-T01` RED, `CDLGW-001-T02` GREEN, `CDLGW-001-T09` REFACTOR.
- **Evidence:** `CDLGW-001-EV03` records the focused passing command/result.

## Numbered TDD Tasks

### `CDLGW-001-T01` — RED for `CDLGW-001-AC03`

- Create `tests/test_errors.py` with the behavior matrix below.

```python
import pytest

from wrapper.errors import (
    ArtifactError,
    CdlgExecutionError,
    ConfigurationError,
    PublicationError,
    ValidationError,
    exit_code_for,
)


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ConfigurationError("invalid YAML"), 2),
        (CdlgExecutionError("child failed"), 3),
        (ArtifactError("export failed"), 4),
        (ValidationError("invalid bundle"), 5),
        (PublicationError("cannot publish"), 6),
        (RuntimeError("unexpected"), 1),
    ],
)
def test_given_error_when_mapped_then_documented_exit_code_is_returned(error, expected):
    assert exit_code_for(error) == expected
```

- Run: `python -m pytest tests/test_errors.py -v`
- Expected: FAIL because `wrapper.errors` does not exist.
- Capture failing output as `CDLGW-001-EV03-RED` in the execution report or commit evidence.

### `CDLGW-001-T02` — GREEN for `CDLGW-001-AC03`

- Create `wrapper/__init__.py` and implement this exact error boundary in `wrapper/errors.py`.

```python
class WrapperError(Exception):
    """Base class for expected wrapper failures."""


class ConfigurationError(WrapperError):
    pass


class CdlgExecutionError(WrapperError):
    pass


class ArtifactError(WrapperError):
    pass


class ValidationError(WrapperError):
    pass


class PublicationError(WrapperError):
    pass


def exit_code_for(error: BaseException) -> int:
    if isinstance(error, ConfigurationError):
        return 2
    if isinstance(error, CdlgExecutionError):
        return 3
    if isinstance(error, ArtifactError):
        return 4
    if isinstance(error, ValidationError):
        return 5
    if isinstance(error, PublicationError):
        return 6
    return 1
```

- Run: `python -m pytest tests/test_errors.py -v`
- Expected: PASS.
- Capture result as `CDLGW-001-EV03`.

### `CDLGW-001-T03` — RED for `CDLGW-001-AC01`

- Create `tests/test_config.py` with an isolated YAML fixture and immutable-default assertions.

```python
from pathlib import Path

from wrapper.config import load_config


def test_given_minimal_config_when_loaded_then_first_experiment_defaults_resolve(tmp_path: Path):
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text("dataset:\n  total_traces: 1000\n", encoding="utf-8")

    resolved = load_config(config_path)

    assert resolved.dataset.version_count == 5
    assert resolved.dataset.version_ids == ("v1", "v2", "v3", "v4", "v5")
    assert resolved.cdlg.process_tree_complexity == "middle"
    assert resolved.cdlg.evolution_proportion == 0.2
    assert resolved.cdlg.drift_type == "sudden"
    assert resolved.cdlg.noise_enabled is False
    assert resolved.lifecycle.assign_enabled is False
    assert resolved.resources.pool_size == 3
    assert resolved.cdlg.checkout_path == Path("CDLG")
```

- Add negative tests for an unsupported preset, non-positive total, zero versions, and a whitespace-only Python executable.
- Run: `python -m pytest tests/test_config.py -v`
- Expected: FAIL because `wrapper.config` does not exist.
- Capture failing output as `CDLGW-001-EV01-RED`.

### `CDLGW-001-T04` — GREEN for `CDLGW-001-AC01`

- Create `wrapper/config.py` with frozen `dataclass` types `CdlgConfig`, `DatasetConfig`, `LifecycleConfig`, `ResourceConfig`, and `ResolvedConfig`.
- Implement `load_config(path: Path) -> ResolvedConfig` with `yaml.safe_load`, mapping validation, defaults from the approved Canon, and `ConfigurationError` for invalid inputs.
- Use this validation shape; do not perform filesystem or CDLG checks in this slice.

```python
def _require_positive_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ConfigurationError(f"{field} must be a positive integer")
    return value


def _require_choice(value: object, field: str, allowed: set[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ConfigurationError(f"{field} must be one of: {choices}")
    return value
```

- Run: `python -m pytest tests/test_config.py -v`
- Expected: PASS.
- Capture result as `CDLGW-001-EV01`.

### `CDLGW-001-T05` — RED for `CDLGW-001-AC02`

- Create `tests/test_trace_allocation.py`.

```python
import pytest

from wrapper.config import ConfigurationError, allocate_traces


def test_given_remainder_when_allocated_then_earliest_versions_receive_one_extra_trace():
    assert allocate_traces(total_traces=17, version_count=5) == (4, 4, 3, 3, 3)


def test_given_exact_division_when_allocated_then_each_version_receives_same_count():
    assert allocate_traces(total_traces=20, version_count=5) == (4, 4, 4, 4, 4)


@pytest.mark.parametrize("total, versions", [(0, 5), (4, 5), (10, 0)])
def test_given_impossible_allocation_when_allocated_then_configuration_error(total, versions):
    with pytest.raises(ConfigurationError):
        allocate_traces(total_traces=total, version_count=versions)
```

- Add a test that `ResolvedConfig.cdlg_traces_per_version == 4` for total `17` and five versions.
- Run: `python -m pytest tests/test_trace_allocation.py -v`
- Expected: FAIL because `allocate_traces` and the derived value do not exist.
- Capture failing output as `CDLGW-001-EV02-RED`.

### `CDLGW-001-T06` — GREEN for `CDLGW-001-AC02`

- Implement exact quotient/remainder allocation and a ceiling-derived CDLG count.

```python
from math import ceil


def allocate_traces(*, total_traces: int, version_count: int) -> tuple[int, ...]:
    total = _require_positive_int(total_traces, "dataset.total_traces")
    versions = _require_positive_int(version_count, "dataset.version_count")
    if total < versions:
        raise ConfigurationError("dataset.total_traces must be at least dataset.version_count")
    base, remainder = divmod(total, versions)
    return tuple(base + (1 if index < remainder else 0) for index in range(versions))


def cdlg_traces_per_version(allocation: tuple[int, ...]) -> int:
    return max(allocation)
```

- Make `ResolvedConfig` expose both `trace_allocation` and `cdlg_traces_per_version`; never replace the exact allocation with the ceiling count.
- Run: `python -m pytest tests/test_trace_allocation.py -v`
- Expected: PASS.
- Capture result as `CDLGW-001-EV02`.

### `CDLGW-001-T07` — RED for cross-field configuration integrity

- Extend `tests/test_config.py` with behavior tests for configuration overrides.

```python
import pytest

from wrapper.config import ConfigurationError, load_config


@pytest.mark.parametrize(
    "yaml_text",
    [
        "dataset:\n  total_traces: 100\n  version_count: 0\n",
        "cdlg:\n  process_tree_complexity: unsupported\ndataset:\n  total_traces: 100\n",
        "cdlg:\n  python_executable: '   '\ndataset:\n  total_traces: 100\n",
    ],
)
def test_given_invalid_override_when_loaded_then_configuration_error(tmp_path, yaml_text):
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_config(path)
```

- Run: `python -m pytest tests/test_config.py -v`
- Expected: FAIL for at least one new invalid override.
- Capture failing output as `CDLGW-001-EV01-CROSSFIELD-RED`.

### `CDLGW-001-T08` — GREEN for cross-field configuration integrity and example config

- Implement override normalization with these committed example values in `configs/cdlg_experiment.yaml`.

```yaml
dataset:
  total_traces: 1000
  version_count: 5
cdlg:
  process_tree_complexity: middle
  evolution_proportion: 0.2
  drift_type: sudden
  noise_enabled: false
  checkout_path: CDLG
  python_executable: ""
lifecycle:
  assign_enabled: false
resources:
  pool_size: 3
```

- Treat an omitted `python_executable` as `None`; reject a supplied blank/whitespace value. Do not resolve environment variables or test executable availability yet.
- Create `requirements.txt` with wrapper-only direct dependencies and add minimal README setup text using an isolated wrapper environment.
- Run: `python -m pytest tests/test_errors.py tests/test_config.py tests/test_trace_allocation.py -v`
- Expected: PASS.
- Capture combined result as `CDLGW-001-EV04`.

### `CDLGW-001-T09` — REFACTOR, documentation, and traceability

- Refactor only duplication between YAML parsing and validation while all focused tests remain green.
- Verify `@dataclass(frozen=True)` configuration objects reject mutation in one focused test.
- Add a concise evidence entry to `docs/ROADMAP.md` linking `CDLGW-001-EV01` through `EV04` to the execution report or test output location created during implementation.
- Do not mark `CDLGW-001` complete; route completion to `closure-verification` after all scenarios and evidence exist.
- Run: `python -m pytest tests/test_errors.py tests/test_config.py tests/test_trace_allocation.py -v`
- Expected: PASS with all scenario tests.
- Commit: `git add requirements.txt configs wrapper tests README.md docs/ROADMAP.md && git commit -m "feat: establish wrapper configuration contract"`.

## Verification Matrix

| Evidence ID | Scenario | Command | Expected result |
| --- | --- | --- | --- |
| `CDLGW-001-EV01` | `AC01` | `python -m pytest tests/test_config.py -v` | Configuration defaults and invalid-input tests pass. |
| `CDLGW-001-EV02` | `AC02` | `python -m pytest tests/test_trace_allocation.py -v` | Allocation and ceiling-count tests pass. |
| `CDLGW-001-EV03` | `AC03` | `python -m pytest tests/test_errors.py -v` | Expected error codes and fallback code pass. |
| `CDLGW-001-EV04` | all | `python -m pytest tests/test_errors.py tests/test_config.py tests/test_trace_allocation.py -v` | Complete slice-focused suite passes. |

## Forbidden Scope

- No subprocess invocation, runtime copy, or parameter-file rendering for CDLG.
- No `CDLG/` source changes, imports, vendor copies, or Python-environment mixing.
- No XES, BPMN, PTML, scheduling, resources, lifecycle events, or dataset publication.
- No `bpm_prediction` imports or modifications.
- No change to the approved methodology or default experiment semantics.

## Approval Gate

Reply `OK EXECUTE CDLGW-001` to authorize execution of this TDD plan.

Reply `CHANGE CDLGW-001` followed by corrections to revise this plan.

Generic `OK` approves the plan content only; it does not authorize implementation.
