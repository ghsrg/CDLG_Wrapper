from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml
from pm4py.objects.bpmn.importer import importer as bpmn_importer
from pm4py.objects.process_tree.importer import importer as ptml_importer

from wrapper.errors import ValidationError
from wrapper.evidence import ChecksumMismatchError, verify_checksums
from wrapper.structure import BPMN_NS


XES_NS = {"xes": "http://www.xes-standard.org/"}
BPMN_QUERY_NS = {"bpmn": BPMN_NS}
REQUIRED_TRACE_ATTRIBUTES = {"concept:name", "concept:version", "sim:generated_by"}
REQUIRED_EVENT_ATTRIBUTES = {
    "concept:name",
    "time:timestamp",
    "lifecycle:transition",
    "org:resource",
    "concept:version",
    "concept:instance",
    "sim:activity_instance_id",
}
TRANSITION_ORDER = {"assign": 0, "start": 1, "complete": 2}


@dataclass(frozen=True)
class ValidationReport:
    trace_count: int
    version_counts: dict[str, int]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _LifecycleInterval:
    instance_id: str
    activity: str
    version_id: str
    resource: str
    start_at: datetime
    complete_at: datetime


def validate_bundle(bundle_dir: Path, resolved_config: Any) -> ValidationReport:
    config = _config_mapping(resolved_config)
    expected_version_ids = tuple(config["dataset"]["version_ids"])
    expected_allocation = tuple(int(value) for value in config["trace_allocation"])
    expected_total = int(config["dataset"]["total_traces"])

    errors: list[str] = []
    bundle_dir = bundle_dir.resolve()
    dataset_path = bundle_dir / "dataset.xes"

    _require_files(bundle_dir, expected_version_ids, errors)
    manifest = _validate_manifest(bundle_dir, errors)
    _validate_checksums(bundle_dir, errors)
    _validate_downstream_reports_and_configs(bundle_dir, errors)

    trace_count, version_counts, intervals, activities_by_version = _validate_xes(
        dataset_path,
        expected_version_ids,
        expected_allocation,
        expected_total,
        errors,
    )
    _validate_resource_intervals(intervals, errors)
    _validate_structures(bundle_dir, expected_version_ids, activities_by_version, errors)
    if manifest is not None:
        _validate_manifest_artifacts(bundle_dir, manifest, errors)

    if errors:
        raise ValidationError("; ".join(errors))
    return ValidationReport(
        trace_count=trace_count,
        version_counts=version_counts,
        warnings=(),
    )


def _config_mapping(resolved_config: Any) -> dict[str, Any]:
    if isinstance(resolved_config, dict):
        return resolved_config
    dataset = resolved_config.dataset
    return {
        "dataset": {
            "total_traces": dataset.total_traces,
            "version_count": dataset.version_count,
            "version_ids": list(dataset.version_ids),
        },
        "trace_allocation": list(resolved_config.trace_allocation),
    }


def _require_files(bundle_dir: Path, expected_version_ids: tuple[str, ...], errors: list[str]) -> None:
    required = [
        "dataset.xes",
        "manifest.json",
        "environment.json",
        "checksums.sha256",
        "configs/input.yaml",
        "configs/resolved.yaml",
        "configs/bpm_prediction_xes.yaml",
        "configs/bpm_prediction_bpmn.yaml",
        "raw/cdlg_output.xes",
        "raw/drift_info.csv",
        "raw/cdlg_parameters.txt",
        "logs/run.log",
        "logs/cdlg_stdout.log",
        "logs/cdlg_stderr.log",
        "reports/drift_metrics.json",
        "reports/processing.json",
        "reports/methodology.md",
        "reports/validation.json",
        "reports/topology_alignment.json",
        "models/process_definitions.csv",
    ]
    for relative_path in required:
        if not (bundle_dir / relative_path).is_file():
            errors.append(f"missing required artifact: {relative_path}")
    for version_id in expected_version_ids:
        if not (bundle_dir / f"models/bpmn/{version_id}.bpmn").is_file():
            errors.append(f"missing BPMN for {version_id}")
        if not (bundle_dir / f"models/ptml/{version_id}.ptml").is_file():
            errors.append(f"missing PTML for {version_id}")


def _validate_manifest(bundle_dir: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"manifest cannot be read: {error}")
        return None
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("manifest artifacts must be a list")
    return manifest


def _validate_manifest_artifacts(bundle_dir: Path, manifest: dict[str, Any], errors: list[str]) -> None:
    for artifact in manifest.get("artifacts", []):
        artifact_path = Path(str(artifact))
        if artifact_path.is_absolute():
            errors.append(f"manifest artifact path must be relative: {artifact}")
            continue
        if ".." in artifact_path.parts:
            errors.append(f"manifest artifact path must stay inside bundle: {artifact}")
            continue
        if not (bundle_dir / artifact_path).is_file():
            errors.append(f"manifest artifact is missing: {artifact}")


def _validate_checksums(bundle_dir: Path, errors: list[str]) -> None:
    checksum_path = bundle_dir / "checksums.sha256"
    if not checksum_path.is_file():
        return
    try:
        verify_checksums(checksum_path)
    except (ChecksumMismatchError, OSError, ValueError) as error:
        errors.append(str(error))


def _validate_xes(
    dataset_path: Path,
    expected_version_ids: tuple[str, ...],
    expected_allocation: tuple[int, ...],
    expected_total: int,
    errors: list[str],
) -> tuple[int, dict[str, int], list[_LifecycleInterval], dict[str, set[str]]]:
    try:
        root = ET.parse(dataset_path).getroot()
    except (OSError, ET.ParseError) as error:
        errors.append(f"dataset XES cannot be parsed: {error}")
        return 0, {}, [], {}

    traces = root.findall("xes:trace", XES_NS)
    version_counts: Counter[str] = Counter()
    activities_by_version: dict[str, set[str]] = defaultdict(set)
    intervals: list[_LifecycleInterval] = []
    seen_instances: set[str] = set()

    for trace in traces:
        trace_attrs = _attributes(trace)
        missing_trace = REQUIRED_TRACE_ATTRIBUTES - trace_attrs.keys()
        if missing_trace:
            errors.append(f"trace missing required attributes: {', '.join(sorted(missing_trace))}")
            continue
        trace_version = trace_attrs["concept:version"]
        version_counts[trace_version] += 1
        instance_events: dict[str, list[dict[str, str]]] = defaultdict(list)
        event_order_keys: list[tuple[datetime, int, str, str]] = []
        for event in trace.findall("xes:event", XES_NS):
            event_attrs = _attributes(event)
            missing_event = REQUIRED_EVENT_ATTRIBUTES - event_attrs.keys()
            if missing_event:
                for field in sorted(missing_event):
                    errors.append(f"event missing {field}")
                continue
            if event_attrs["concept:version"] != trace_version:
                errors.append("event concept:version does not match trace concept:version")
            if event_attrs["concept:instance"] != event_attrs["sim:activity_instance_id"]:
                errors.append("sim:activity_instance_id must match concept:instance")
            instance_events[event_attrs["concept:instance"]].append(event_attrs)
            activities_by_version[trace_version].add(event_attrs["concept:name"])
            timestamp = _parse_timestamp(event_attrs["time:timestamp"], errors)
            if timestamp is not None:
                event_order_keys.append(
                    (
                        timestamp,
                        TRANSITION_ORDER.get(event_attrs["lifecycle:transition"], 99),
                        event_attrs["concept:name"],
                        event_attrs["concept:instance"],
                    )
                )
        if event_order_keys != sorted(event_order_keys):
            errors.append(f"events are not sorted by timestamp in trace {trace_attrs['concept:name']}")
        intervals.extend(_validate_lifecycle_pairs(instance_events, seen_instances, errors))

    if len(traces) != expected_total:
        errors.append(f"trace count {len(traces)} does not match expected {expected_total}")
    expected_counts = dict(zip(expected_version_ids, expected_allocation))
    if dict(version_counts) != expected_counts:
        errors.append(f"version trace counts {dict(version_counts)} do not match expected {expected_counts}")
    return len(traces), dict(version_counts), intervals, activities_by_version


def _validate_lifecycle_pairs(
    instance_events: dict[str, list[dict[str, str]]],
    seen_instances: set[str],
    errors: list[str],
) -> list[_LifecycleInterval]:
    intervals: list[_LifecycleInterval] = []
    for instance_id, events in instance_events.items():
        if instance_id in seen_instances:
            errors.append(f"duplicate concept:instance: {instance_id}")
        seen_instances.add(instance_id)
        starts = [event for event in events if event["lifecycle:transition"] == "start"]
        completes = [event for event in events if event["lifecycle:transition"] == "complete"]
        if len(starts) != 1 or len(completes) != 1:
            errors.append(f"lifecycle pair must have one start and one complete for {instance_id}")
            continue
        start = starts[0]
        complete = completes[0]
        if start["concept:name"] != complete["concept:name"]:
            errors.append(f"lifecycle activity mismatch for {instance_id}")
        if start["org:resource"] != complete["org:resource"]:
            errors.append(f"lifecycle resource mismatch for {instance_id}")
        start_at = _parse_timestamp(start["time:timestamp"], errors)
        complete_at = _parse_timestamp(complete["time:timestamp"], errors)
        if start_at is None or complete_at is None:
            continue
        if complete_at < start_at:
            errors.append(f"lifecycle complete precedes start for {instance_id}")
        intervals.append(
            _LifecycleInterval(
                instance_id=instance_id,
                activity=start["concept:name"],
                version_id=start["concept:version"],
                resource=start["org:resource"],
                start_at=start_at,
                complete_at=complete_at,
            )
        )
    return intervals


def _validate_resource_intervals(intervals: list[_LifecycleInterval], errors: list[str]) -> None:
    by_resource: dict[str, list[_LifecycleInterval]] = defaultdict(list)
    for interval in intervals:
        by_resource[interval.resource].append(interval)
    for resource, resource_intervals in by_resource.items():
        ordered = sorted(resource_intervals, key=lambda item: (item.start_at, item.complete_at, item.instance_id))
        for previous, current in zip(ordered, ordered[1:]):
            if current.start_at < previous.complete_at:
                errors.append(
                    f"resource overlap for {resource}: {previous.instance_id} overlaps {current.instance_id}"
                )


def _validate_structures(
    bundle_dir: Path,
    expected_version_ids: tuple[str, ...],
    activities_by_version: dict[str, set[str]],
    errors: list[str],
) -> None:
    catalog_path = bundle_dir / "models/process_definitions.csv"
    if catalog_path.is_file():
        _validate_catalog(catalog_path, expected_version_ids, errors)

    for version_id in expected_version_ids:
        ptml_path = bundle_dir / f"models/ptml/{version_id}.ptml"
        bpmn_path = bundle_dir / f"models/bpmn/{version_id}.bpmn"
        if ptml_path.is_file():
            try:
                ptml_importer.apply(str(ptml_path))
            except Exception as error:
                errors.append(f"PTML cannot be parsed for {version_id}: {error}")
        if bpmn_path.is_file():
            task_names = _validate_bpmn(bpmn_path, errors)
            xes_names = activities_by_version.get(version_id, set())
            missing_in_bpmn = xes_names - task_names
            if missing_in_bpmn:
                errors.append(
                    f"BPMN/XES activity alignment mismatch for {version_id}: "
                    f"BPMN={sorted(task_names)} XES={sorted(xes_names)}"
                )


def _validate_catalog(catalog_path: Path, expected_version_ids: tuple[str, ...], errors: list[str]) -> None:
    try:
        with catalog_path.open("r", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as error:
        errors.append(f"process_definitions.csv cannot be read: {error}")
        return
    versions = [row.get("version") for row in rows]
    if versions != list(expected_version_ids):
        errors.append(f"process_definitions.csv versions {versions} do not match expected {list(expected_version_ids)}")
    for row in rows:
        for field in ("proc_def_id", "proc_def_key", "version", "deployment_id", "bpmn_path"):
            if field not in row:
                errors.append(f"process_definitions.csv missing column: {field}")
        bpmn_path = row.get("bpmn_path", "")
        if Path(bpmn_path).is_absolute() or ".." in Path(bpmn_path).parts:
            errors.append(f"process_definitions.csv bpmn_path must be relative: {bpmn_path}")
        elif bpmn_path and not (catalog_path.parents[1] / bpmn_path).is_file():
            errors.append(f"process_definitions.csv bpmn_path is missing: {bpmn_path}")


def _validate_downstream_reports_and_configs(bundle_dir: Path, errors: list[str]) -> None:
    validation_report = _read_json(bundle_dir / "reports/validation.json", errors)
    if validation_report is not None and validation_report.get("status") != "passed":
        errors.append("reports/validation.json status must be passed")

    topology_report = _read_json(bundle_dir / "reports/topology_alignment.json", errors)
    if topology_report is not None and topology_report.get("status") != "passed":
        errors.append("reports/topology_alignment.json status must be passed")

    xes_config = _read_yaml(bundle_dir / "configs/bpm_prediction_xes.yaml", errors)
    if xes_config is not None:
        if _get(xes_config, ("mapping", "adapter")) != "xes":
            errors.append("configs/bpm_prediction_xes.yaml mapping.adapter must be xes")
        if _get(xes_config, ("data", "log_path")) != "dataset.xes":
            errors.append("configs/bpm_prediction_xes.yaml data.log_path must be dataset.xes")
        if _get(xes_config, ("mapping", "xes_adapter", "version_key")) != "concept:version":
            errors.append("configs/bpm_prediction_xes.yaml xes_adapter.version_key must be concept:version")
        if _get(xes_config, ("mapping", "xes_adapter", "lifecycle_key")) != "lifecycle:transition":
            errors.append("configs/bpm_prediction_xes.yaml xes_adapter.lifecycle_key must be lifecycle:transition")

    bpmn_config = _read_yaml(bundle_dir / "configs/bpm_prediction_bpmn.yaml", errors)
    if bpmn_config is not None:
        if _get(bpmn_config, ("mapping", "adapter")) != "camunda":
            errors.append("configs/bpm_prediction_bpmn.yaml mapping.adapter must be camunda")
        if _get(bpmn_config, ("mapping", "camunda_adapter", "structure", "source")) != "bpmn":
            errors.append("configs/bpm_prediction_bpmn.yaml camunda structure.source must be bpmn")
        catalog_file = _get(
            bpmn_config,
            ("mapping", "camunda_adapter", "structure", "files", "catalog_file"),
        )
        if catalog_file != "models/process_definitions.csv":
            errors.append("configs/bpm_prediction_bpmn.yaml catalog_file must be models/process_definitions.csv")


def _read_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        errors.append(f"{path.name} cannot be read: {error}")
        return None
    if not isinstance(loaded, dict):
        errors.append(f"{path.name} must be a JSON object")
        return None
    return loaded


def _read_yaml(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        loaded = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        errors.append(f"{path.name} cannot be read: {error}")
        return None
    if not isinstance(loaded, dict):
        errors.append(f"{path.name} must be a YAML mapping")
        return None
    return loaded


def _get(payload: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _validate_bpmn(bpmn_path: Path, errors: list[str]) -> set[str]:
    try:
        root = ET.parse(bpmn_path).getroot()
        bpmn_importer.apply(str(bpmn_path))
    except Exception as error:
        errors.append(f"BPMN cannot be parsed: {error}")
        return set()

    ids = [element.attrib["id"] for element in root.findall(".//*[@id]")]
    if len(ids) != len(set(ids)):
        errors.append("BPMN IDs are not unique")
    id_set = set(ids)
    for flow in root.findall(".//bpmn:sequenceFlow", BPMN_QUERY_NS):
        if flow.attrib.get("sourceRef") not in id_set or flow.attrib.get("targetRef") not in id_set:
            errors.append("BPMN sequence flow references missing endpoint")
    return {task.attrib["name"] for task in root.findall(".//bpmn:task", BPMN_QUERY_NS)}


def _attributes(node: ET.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for child in node:
        key = child.attrib.get("key")
        value = child.attrib.get("value")
        if key is not None and value is not None:
            values[key] = value
    return values


def _parse_timestamp(value: str, errors: list[str]) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"invalid timestamp: {value}")
        return None
