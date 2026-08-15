from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from wrapper.errors import ConfigurationError


ALLOWED_PROCESS_TREE_COMPLEXITIES = {"simple", "middle", "complex"}
ALLOWED_DRIFT_TYPES = {"sudden"}


@dataclass(frozen=True)
class DatasetConfig:
    name: str
    total_traces: int
    version_count: int
    version_ids: tuple[str, ...]


@dataclass(frozen=True)
class CdlgConfig:
    process_tree_complexity: str
    evolution_proportion: float
    drift_type: str
    noise_enabled: bool
    checkout_path: Path
    python_executable: str | None


@dataclass(frozen=True)
class LifecycleConfig:
    assign_enabled: bool


@dataclass(frozen=True)
class ResourceConfig:
    pool_size: int


@dataclass(frozen=True)
class TemporalConfig:
    arrival_rate: float
    duration_mu: float
    duration_sigma: float
    epoch: datetime


@dataclass(frozen=True)
class OutputConfig:
    export_per_version_xes: bool


@dataclass(frozen=True)
class ResolvedConfig:
    dataset: DatasetConfig
    cdlg: CdlgConfig
    lifecycle: LifecycleConfig
    resources: ResourceConfig
    temporal: TemporalConfig
    output: OutputConfig
    trace_allocation: tuple[int, ...]
    cdlg_traces_per_version: int


def load_config(path: Path) -> ResolvedConfig:
    raw = _load_yaml_mapping(path)
    dataset_raw = _optional_mapping(raw, "dataset")
    cdlg_raw = _optional_mapping(raw, "cdlg")
    lifecycle_raw = _optional_mapping(raw, "lifecycle")
    resources_raw = _optional_mapping(raw, "resources")
    temporal_raw = _optional_mapping(raw, "temporal")
    output_raw = _optional_mapping(raw, "output")

    dataset_name = _require_non_empty_string(
        dataset_raw.get("name", dataset_raw.get("dataset_name", "cdlg_dataset")),
        "dataset.name",
    )
    total_traces = _require_positive_int(
        dataset_raw.get("total_traces"),
        "dataset.total_traces",
    )
    version_count = _require_positive_int(
        dataset_raw.get("version_count", 5),
        "dataset.version_count",
    )
    trace_allocation = allocate_traces(
        total_traces=total_traces,
        version_count=version_count,
    )
    version_ids = tuple(f"v{index}" for index in range(1, version_count + 1))

    return ResolvedConfig(
        dataset=DatasetConfig(
            name=dataset_name,
            total_traces=total_traces,
            version_count=version_count,
            version_ids=version_ids,
        ),
        cdlg=CdlgConfig(
            process_tree_complexity=_require_choice(
                cdlg_raw.get("process_tree_complexity", "middle"),
                "cdlg.process_tree_complexity",
                ALLOWED_PROCESS_TREE_COMPLEXITIES,
            ),
            evolution_proportion=_require_positive_float(
                cdlg_raw.get("evolution_proportion", 0.2),
                "cdlg.evolution_proportion",
            ),
            drift_type=_require_choice(
                cdlg_raw.get("drift_type", "sudden"),
                "cdlg.drift_type",
                ALLOWED_DRIFT_TYPES,
            ),
            noise_enabled=_require_bool(
                cdlg_raw.get("noise_enabled", False),
                "cdlg.noise_enabled",
            ),
            checkout_path=Path(_require_non_empty_string(
                cdlg_raw.get("checkout_path", "CDLG"),
                "cdlg.checkout_path",
            )),
            python_executable=_optional_non_empty_string(
                cdlg_raw.get("python_executable"),
                "cdlg.python_executable",
            ),
        ),
        lifecycle=LifecycleConfig(
            assign_enabled=_require_bool(
                lifecycle_raw.get("assign_enabled", False),
                "lifecycle.assign_enabled",
            ),
        ),
        resources=ResourceConfig(
            pool_size=_require_positive_int(
                resources_raw.get("pool_size", 3),
                "resources.pool_size",
            ),
        ),
        temporal=TemporalConfig(
            arrival_rate=_require_positive_float(
                temporal_raw.get("arrival_rate", 1.0),
                "temporal.arrival_rate",
            ),
            duration_mu=_require_float(
                temporal_raw.get("duration_mu", 0.0),
                "temporal.duration_mu",
            ),
            duration_sigma=_require_non_negative_float(
                temporal_raw.get("duration_sigma", 1.0),
                "temporal.duration_sigma",
            ),
            epoch=_require_utc_datetime(
                temporal_raw.get("epoch", "2026-01-01T00:00:00Z"),
                "temporal.epoch",
            ),
        ),
        output=OutputConfig(
            export_per_version_xes=_require_bool(
                output_raw.get("export_per_version_xes", False),
                "output.export_per_version_xes",
            ),
        ),
        trace_allocation=trace_allocation,
        cdlg_traces_per_version=cdlg_traces_per_version(trace_allocation),
    )


def allocate_traces(*, total_traces: int, version_count: int) -> tuple[int, ...]:
    total = _require_positive_int(total_traces, "dataset.total_traces")
    versions = _require_positive_int(version_count, "dataset.version_count")
    if total < versions:
        raise ConfigurationError("dataset.total_traces must be at least dataset.version_count")
    base, remainder = divmod(total, versions)
    return tuple(base + (1 if index < remainder else 0) for index in range(versions))


def cdlg_traces_per_version(allocation: tuple[int, ...]) -> int:
    return max(allocation)


def _load_yaml_mapping(path: Path) -> dict[str, Any]:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ConfigurationError(f"Cannot read config file: {path}") from error
    except yaml.YAMLError as error:
        raise ConfigurationError(f"Invalid YAML in config file: {path}") from error

    if loaded is None:
        return {}
    if not isinstance(loaded, dict):
        raise ConfigurationError("Configuration root must be a mapping")
    return loaded


def _optional_mapping(raw: dict[str, Any], key: str) -> dict[str, Any]:
    value = raw.get(key, {})
    if not isinstance(value, dict):
        raise ConfigurationError(f"{key} must be a mapping")
    return value


def _require_positive_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ConfigurationError(f"{field} must be a positive integer")
    return value


def _require_choice(value: object, field: str, allowed: set[str]) -> str:
    if not isinstance(value, str) or value not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ConfigurationError(f"{field} must be one of: {choices}")
    return value


def _require_positive_float(value: object, field: str) -> float:
    resolved = _require_float(value, field)
    if resolved <= 0:
        raise ConfigurationError(f"{field} must be greater than zero")
    return resolved


def _require_non_negative_float(value: object, field: str) -> float:
    resolved = _require_float(value, field)
    if resolved < 0:
        raise ConfigurationError(f"{field} must be greater than or equal to zero")
    return resolved


def _require_float(value: object, field: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ConfigurationError(f"{field} must be a number")
    return float(value)


def _require_utc_datetime(value: object, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{field} must be an ISO-8601 UTC timestamp string")
    try:
        normalized = value.strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise ConfigurationError(f"{field} must be an ISO-8601 UTC timestamp string") from error
    if parsed.tzinfo is None:
        raise ConfigurationError(f"{field} must include UTC timezone")
    return parsed.astimezone(timezone.utc)


def _require_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError(f"{field} must be a boolean")
    return value


def _require_non_empty_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{field} must be a non-empty string")
    return value


def _optional_non_empty_string(value: object, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{field} must be a non-empty string when supplied")
    return value
