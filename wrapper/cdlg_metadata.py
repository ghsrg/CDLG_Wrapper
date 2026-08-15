from __future__ import annotations

import csv
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from wrapper.errors import ArtifactError


XES_NS = {"xes": "http://www.xes-standard.org/"}
PROCESS_TREE_PATTERN = re.compile(r"^(->|X|\+|\*)\(.+\)$")
REQUIRED_FLAT_COLUMNS = {
    "log_name",
    "drift_or_noise_id",
    "drift_attribute",
    "drift_sub_attribute",
    "value",
}


@dataclass(frozen=True)
class ProcessTreeSnapshot:
    version_id: str
    process_tree: str


@dataclass(frozen=True)
class VersionBoundary:
    version_id: str
    start_index: int
    end_index: int


@dataclass(frozen=True)
class RawMetadata:
    snapshots: tuple[ProcessTreeSnapshot, ...]
    boundaries: tuple[VersionBoundary, ...]
    raw_trace_count: int


def parse_raw_metadata(
    *,
    raw_xes_path: Path,
    drift_csv_path: Path,
    expected_version_ids: tuple[str, ...],
) -> RawMetadata:
    raw_trace_count = _count_xes_traces(raw_xes_path)
    rows = _read_rows(drift_csv_path)
    changes = _extract_ordered_changes(rows)
    if len(changes) != len(expected_version_ids) - 1:
        raise ArtifactError("drift metadata change count does not match expected versions")

    process_trees = [changes[0]["process_tree_before"]]
    process_trees.extend(change["process_tree_after"] for change in changes)
    if len(process_trees) != len(expected_version_ids):
        raise ArtifactError("drift metadata process_tree count does not match expected versions")

    snapshots = []
    for version_id, process_tree in zip(expected_version_ids, process_trees):
        _validate_process_tree(version_id, process_tree)
        snapshots.append(ProcessTreeSnapshot(version_id=version_id, process_tree=process_tree))

    boundary_starts = [0]
    seen_change_starts: set[int] = set()
    for change in changes:
        start_index = _change_trace_index_to_zero_based(change["change_trace_index"])
        if start_index in seen_change_starts:
            raise ArtifactError(f"duplicate change_trace_index boundary: {start_index + 1}")
        seen_change_starts.add(start_index)
        boundary_starts.append(start_index)

    boundaries = _build_boundaries(boundary_starts, expected_version_ids, raw_trace_count)

    return RawMetadata(
        snapshots=tuple(snapshots),
        boundaries=boundaries,
        raw_trace_count=raw_trace_count,
    )


def _count_xes_traces(raw_xes_path: Path) -> int:
    try:
        root = ET.parse(raw_xes_path).getroot()
    except ET.ParseError as error:
        raise ArtifactError(f"raw XES is malformed: {raw_xes_path}") from error
    return len(root.findall("xes:trace", XES_NS))


def _read_rows(drift_csv_path: Path) -> list[dict[str, str]]:
    with drift_csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        fieldnames = set(reader.fieldnames or ())
        if not REQUIRED_FLAT_COLUMNS.issubset(fieldnames):
            raise ArtifactError("drift metadata flat CDLG columns are missing")
        return list(reader)


def _extract_ordered_changes(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    log_names = {row["log_name"].strip() for row in rows if row.get("log_name", "").strip()}
    if len(log_names) != 1:
        raise ArtifactError("drift metadata must describe exactly one log_name")

    drift_ids = sorted(
        {
            row["drift_or_noise_id"].strip()
            for row in rows
            if row.get("drift_or_noise_id", "").strip().startswith("drift_")
        },
        key=_drift_sort_key,
    )
    changes = []
    for drift_id in drift_ids:
        drift_rows = [row for row in rows if row["drift_or_noise_id"].strip() == drift_id]
        change_ids = sorted(
            {
                row["drift_attribute"].strip()
                for row in drift_rows
                if row.get("drift_attribute", "").strip().startswith("change_info_")
            },
            key=_change_sort_key,
        )
        if len(change_ids) != 1:
            raise ArtifactError(f"drift metadata must contain exactly one change_info for {drift_id}")
        change_id = change_ids[0]
        changes.append(
            {
                "change_trace_index": _change_value(drift_rows, change_id, "change_trace_index"),
                "process_tree_before": _change_value(drift_rows, change_id, "process_tree_before"),
                "process_tree_after": _change_value(drift_rows, change_id, "process_tree_after"),
            }
        )
    return changes


def _change_value(rows: list[dict[str, str]], change_id: str, sub_attribute: str) -> str:
    values = [
        row["value"].strip()
        for row in rows
        if row.get("drift_attribute", "").strip() == change_id
        and row.get("drift_sub_attribute", "").strip() == sub_attribute
        and row.get("value", "").strip()
    ]
    if len(values) != 1:
        raise ArtifactError(f"drift metadata missing {sub_attribute}")
    return values[0]


def _drift_sort_key(drift_id: str) -> int:
    match = re.fullmatch(r"drift_(\d+)", drift_id)
    if not match:
        raise ArtifactError(f"invalid drift_or_noise_id: {drift_id}")
    return int(match.group(1))


def _change_sort_key(change_id: str) -> int:
    match = re.fullmatch(r"change_info_(\d+)", change_id)
    if not match:
        raise ArtifactError(f"invalid drift_attribute: {change_id}")
    return int(match.group(1))


def _validate_process_tree(version_id: str, process_tree: str) -> None:
    if not PROCESS_TREE_PATTERN.match(process_tree):
        raise ArtifactError(f"invalid process_tree for {version_id}")


def _change_trace_index_to_zero_based(value: str) -> int:
    indexes = [int(item) for item in re.findall(r"\d+", value)]
    if len(indexes) != 1:
        raise ArtifactError(f"ambiguous change_trace_index boundary: {value}")
    one_based_index = indexes[0]
    if one_based_index <= 1:
        raise ArtifactError(f"ambiguous trace boundary: {value}")
    return one_based_index - 1


def _build_boundaries(
    boundary_starts: list[int],
    expected_version_ids: tuple[str, ...],
    raw_trace_count: int,
) -> tuple[VersionBoundary, ...]:
    if boundary_starts != sorted(boundary_starts):
        raise ArtifactError("ambiguous trace boundary order")
    if boundary_starts[-1] >= raw_trace_count:
        raise ArtifactError("trace boundary exceeds raw XES trace count")

    boundaries = []
    for index, version_id in enumerate(expected_version_ids):
        start_index = boundary_starts[index]
        end_index = boundary_starts[index + 1] - 1 if index + 1 < len(boundary_starts) else raw_trace_count - 1
        if end_index < start_index:
            raise ArtifactError(f"ambiguous trace boundary for {version_id}")
        boundaries.append(VersionBoundary(version_id=version_id, start_index=start_index, end_index=end_index))
    return tuple(boundaries)
