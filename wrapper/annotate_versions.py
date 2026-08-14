from __future__ import annotations

import copy
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from wrapper.cdlg_metadata import RawMetadata
from wrapper.config import ResolvedConfig
from wrapper.errors import ArtifactError


XES_NS = {"xes": "http://www.xes-standard.org/"}


@dataclass(frozen=True)
class AnnotatedEvent:
    attributes: dict[str, str]


@dataclass(frozen=True)
class AnnotatedTrace:
    source_index: int
    attributes: dict[str, str]
    events: tuple[AnnotatedEvent, ...]


@dataclass(frozen=True)
class VersionAnnotationReport:
    version_id: str
    source_start_index: int
    source_end_index: int
    retained_count: int
    discarded_count: int


@dataclass(frozen=True)
class AnnotatedLog:
    traces: tuple[AnnotatedTrace, ...]
    reports: tuple[VersionAnnotationReport, ...]


def annotate_versions(
    *,
    raw_xes_path: Path,
    metadata: RawMetadata,
    resolved_config: ResolvedConfig,
) -> AnnotatedLog:
    raw_traces = _read_raw_traces(raw_xes_path)
    annotated_traces: list[AnnotatedTrace] = []
    reports: list[VersionAnnotationReport] = []

    for boundary, retained_count in zip(metadata.boundaries, resolved_config.trace_allocation):
        available_count = boundary.end_index - boundary.start_index + 1
        if retained_count > available_count:
            raise ArtifactError(f"not enough raw traces for {boundary.version_id}")
        retained_indices = range(boundary.start_index, boundary.start_index + retained_count)
        for source_index in retained_indices:
            annotated_traces.append(_annotate_trace(raw_traces[source_index], boundary.version_id))
        reports.append(
            VersionAnnotationReport(
                version_id=boundary.version_id,
                source_start_index=boundary.start_index,
                source_end_index=boundary.end_index,
                retained_count=retained_count,
                discarded_count=available_count - retained_count,
            )
        )

    return AnnotatedLog(traces=tuple(annotated_traces), reports=tuple(reports))


def _annotate_trace(trace: AnnotatedTrace, version_id: str) -> AnnotatedTrace:
    trace_attributes = copy.deepcopy(trace.attributes)
    trace_attributes["concept:version"] = version_id
    events = []
    for event in trace.events:
        event_attributes = copy.deepcopy(event.attributes)
        event_attributes["concept:version"] = version_id
        events.append(AnnotatedEvent(attributes=event_attributes))
    return AnnotatedTrace(
        source_index=trace.source_index,
        attributes=trace_attributes,
        events=tuple(events),
    )


def _read_raw_traces(raw_xes_path: Path) -> tuple[AnnotatedTrace, ...]:
    root = ET.parse(raw_xes_path).getroot()
    traces: list[AnnotatedTrace] = []
    for source_index, trace_node in enumerate(root.findall("xes:trace", XES_NS)):
        trace_attributes = _attributes(trace_node)
        events = tuple(AnnotatedEvent(attributes=_attributes(event_node)) for event_node in trace_node.findall("xes:event", XES_NS))
        traces.append(AnnotatedTrace(source_index=source_index, attributes=trace_attributes, events=events))
    return tuple(traces)


def _attributes(node: ET.Element) -> dict[str, str]:
    values: dict[str, str] = {}
    for child in node:
        key = child.attrib.get("key")
        value = child.attrib.get("value")
        if key is not None and value is not None:
            values[key] = value
    return values
