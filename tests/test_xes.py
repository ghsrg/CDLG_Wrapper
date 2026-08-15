from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from random import Random

from wrapper.annotate_versions import AnnotatedEvent, AnnotatedTrace
from wrapper.cdlg_metadata import ProcessTreeSnapshot
from wrapper.config import LifecycleConfig, ResourceConfig, TemporalConfig
from wrapper.enrichment import EnrichmentConfig, enrich_traces
from wrapper.xes import assemble_xes, write_xes


XES_NS = {"xes": "http://www.xes-standard.org/"}


def test_given_enriched_traces_when_assembled_then_xes_contract_attributes_are_present(tmp_path):
    enriched = enrich_traces(
        traces=(
            _trace("v1", 0, ("A",)),
            _trace("v1", 1, ("B",)),
            _trace("v2", 2, ("A",)),
        ),
        snapshots=(
            ProcessTreeSnapshot(version_id="v1", process_tree="X('A','B')"),
            ProcessTreeSnapshot(version_id="v2", process_tree="'A'"),
        ),
        config=_config(assign_enabled=True),
        rng=Random(13),
    )

    log = assemble_xes(enriched)

    assert [trace.attributes["concept:version"] for trace in log] == ["v1", "v1", "v2"]
    assert len({trace.attributes["concept:name"] for trace in log}) == 3
    assert [event["lifecycle:transition"] for event in log[0]] == ["assign", "start", "complete"]
    for trace in log:
        for event in trace:
            assert event["concept:version"] == trace.attributes["concept:version"]
            assert event["concept:instance"] == event["sim:activity_instance_id"]
            assert event["org:resource"]
            assert event["time:timestamp"].tzinfo is not None


def test_given_xes_log_when_written_then_file_is_parseable_and_contains_utc_timestamps(tmp_path):
    enriched = enrich_traces(
        traces=(_trace("v1", 0, ("A",)),),
        snapshots=(ProcessTreeSnapshot(version_id="v1", process_tree="'A'"),),
        config=_config(assign_enabled=False),
        rng=Random(13),
    )
    path = tmp_path / "dataset.xes"

    write_xes(assemble_xes(enriched), path)

    root = ET.parse(path).getroot()
    trace = root.find("xes:trace", XES_NS)
    assert trace is not None
    assert _string_value(trace, "concept:version") == "v1"
    event = trace.find("xes:event", XES_NS)
    assert event is not None
    assert _date_value(event, "time:timestamp").endswith("+00:00")


def test_given_per_version_debug_dir_when_written_then_each_version_gets_debug_xes(tmp_path):
    enriched = enrich_traces(
        traces=(
            _trace("v1", 0, ("A",)),
            _trace("v2", 1, ("B",)),
        ),
        snapshots=(
            ProcessTreeSnapshot(version_id="v1", process_tree="'A'"),
            ProcessTreeSnapshot(version_id="v2", process_tree="'B'"),
        ),
        config=_config(assign_enabled=False),
        rng=Random(13),
    )
    path = tmp_path / "dataset.xes"
    debug_dir = tmp_path / "debug"

    write_xes(assemble_xes(enriched), path, per_version_debug_dir=debug_dir)

    v1 = ET.parse(debug_dir / "v1.xes").getroot()
    v2 = ET.parse(debug_dir / "v2.xes").getroot()
    assert [_string_value(trace, "concept:version") for trace in v1.findall("xes:trace", XES_NS)] == ["v1"]
    assert [_string_value(trace, "concept:version") for trace in v2.findall("xes:trace", XES_NS)] == ["v2"]


def _trace(version_id: str, source_index: int, activities: tuple[str, ...]) -> AnnotatedTrace:
    return AnnotatedTrace(
        source_index=source_index,
        attributes={"concept:version": version_id},
        events=tuple(AnnotatedEvent(attributes={"concept:name": activity}) for activity in activities),
    )


def _config(*, assign_enabled: bool) -> EnrichmentConfig:
    return EnrichmentConfig(
        lifecycle=LifecycleConfig(assign_enabled=assign_enabled),
        resources=ResourceConfig(pool_size=3),
        temporal=TemporalConfig(
            arrival_rate=1.0,
            duration_mu=-2.0,
            duration_sigma=0.1,
            epoch=datetime(2026, 1, 1, tzinfo=timezone.utc),
        ),
    )


def _string_value(node: ET.Element, key: str) -> str | None:
    child = node.find(f"xes:string[@key='{key}']", XES_NS)
    return None if child is None else child.attrib["value"]


def _date_value(node: ET.Element, key: str) -> str:
    child = node.find(f"xes:date[@key='{key}']", XES_NS)
    assert child is not None
    return child.attrib["value"]
