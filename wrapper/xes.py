from __future__ import annotations

import contextlib
import io
from pathlib import Path

from pm4py.objects.log.exporter.xes import exporter as xes_exporter
from pm4py.objects.log.obj import Event, EventLog, Trace

from wrapper.enrichment import EnrichedLog, EnrichedTrace


TRANSITION_ORDER = {"assign": 0, "start": 1, "complete": 2}


def assemble_xes(enriched_log: EnrichedLog, dataset_name: str = "cdlg_versioned_dataset") -> EventLog:
    log = EventLog()
    log.attributes["concept:name"] = dataset_name
    log.attributes["sim:generated_by"] = "cdlg_tool_wrapper"
    for enriched_trace in enriched_log.traces:
        log.append(_assemble_trace(enriched_trace))
    return log


def write_xes(log: EventLog, path: Path, *, per_version_debug_dir: Path | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _export_xes_silently(log, path)
    if per_version_debug_dir is not None:
        _write_per_version_debug_xes(log, per_version_debug_dir)


def _write_per_version_debug_xes(log: EventLog, debug_dir: Path) -> None:
    debug_dir.mkdir(parents=True, exist_ok=True)
    version_logs: dict[str, EventLog] = {}
    for trace in log:
        version_id = trace.attributes["concept:version"]
        version_log = version_logs.setdefault(version_id, EventLog())
        version_log.attributes.update(log.attributes)
        version_log.attributes["concept:name"] = f"{log.attributes.get('concept:name', 'dataset')}_{version_id}"
        version_log.append(trace)
    for version_id, version_log in sorted(version_logs.items()):
        _export_xes_silently(version_log, debug_dir / f"{version_id}.xes")


def _export_xes_silently(log: EventLog, path: Path) -> None:
    with contextlib.redirect_stderr(io.StringIO()):
        xes_exporter.apply(log, str(path))


def _assemble_trace(enriched_trace: EnrichedTrace) -> Trace:
    trace = Trace()
    trace.attributes["concept:name"] = enriched_trace.case_id
    trace.attributes["concept:version"] = enriched_trace.version_id
    trace.attributes["sim:generated_by"] = "cdlg_tool_wrapper"
    events = [
        event
        for instance in enriched_trace.instances
        for event in instance.events
    ]
    for event in sorted(
        events,
        key=lambda item: (
            item.timestamp,
            TRANSITION_ORDER[item.transition],
            item.activity,
            item.instance_id,
        ),
    ):
        trace.append(
            Event(
                {
                    "concept:name": event.activity,
                    "time:timestamp": event.timestamp,
                    "lifecycle:transition": event.transition,
                    "org:resource": event.resource,
                    "concept:version": event.version_id,
                    "concept:instance": event.instance_id,
                    "sim:activity_instance_id": event.instance_id,
                }
            )
        )
    return trace
