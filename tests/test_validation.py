from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from random import Random

import pytest

from wrapper.annotate_versions import AnnotatedEvent, AnnotatedTrace
from wrapper.cdlg_metadata import ProcessTreeSnapshot
from wrapper.config import LifecycleConfig, ResourceConfig, TemporalConfig
from wrapper.enrichment import EnrichmentConfig, enrich_traces
from wrapper.errors import ValidationError
from wrapper.evidence import write_draft_evidence
from wrapper.structure import export_structures
from wrapper.validation import validate_bundle
from wrapper.xes import assemble_xes, write_xes


XES_NS = {"xes": "http://www.xes-standard.org/"}
BPMN_NS = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL"}


def test_given_valid_bundle_when_validated_then_report_is_returned(tmp_path):
    bundle = _valid_bundle(tmp_path)

    report = validate_bundle(bundle, _resolved_config())

    assert report.trace_count == 2
    assert report.version_counts == {"v1": 1, "v2": 1}
    assert report.warnings == ()


@pytest.mark.parametrize(
    ("corrupt", "message"),
    [
        ("missing_bpmn", "missing BPMN"),
        ("missing_raw_xes", "missing required artifact: raw/cdlg_output.xes"),
        ("missing_raw_drift_info", "missing required artifact: raw/drift_info.csv"),
        ("missing_raw_parameters", "missing required artifact: raw/cdlg_parameters.txt"),
        ("missing_run_log", "missing required artifact: logs/run.log"),
        ("missing_cdlg_stdout", "missing required artifact: logs/cdlg_stdout.log"),
        ("missing_cdlg_stderr", "missing required artifact: logs/cdlg_stderr.log"),
        ("missing_drift_metrics", "missing required artifact: reports/drift_metrics.json"),
        ("missing_validation_report", "missing required artifact: reports/validation.json"),
        ("missing_topology_alignment_report", "missing required artifact: reports/topology_alignment.json"),
        ("missing_downstream_xes_config", "missing required artifact: configs/bpm_prediction_xes.yaml"),
        ("missing_downstream_bpmn_config", "missing required artifact: configs/bpm_prediction_bpmn.yaml"),
        ("failed_validation_report", "reports/validation.json status must be passed"),
        ("failed_topology_alignment_report", "reports/topology_alignment.json status must be passed"),
        ("invalid_downstream_xes_adapter", "configs/bpm_prediction_xes.yaml mapping.adapter must be xes"),
        ("invalid_downstream_bpmn_catalog", "configs/bpm_prediction_bpmn.yaml catalog_file must be models/process_definitions.csv"),
        ("wrong_trace_count", "trace count"),
        ("missing_event_version", "event missing concept:version"),
        ("invalid_lifecycle_pair", "lifecycle pair must have one start and one complete"),
        ("unsorted_events", "events are not sorted by timestamp"),
        ("duplicate_instance", "duplicate concept:instance"),
        ("resource_overlap", "resource overlap"),
        ("broken_bpmn_reference", "BPMN sequence flow references missing endpoint"),
        ("tampered_checksum", "checksum mismatch"),
        ("absolute_manifest_path", "manifest artifact path must be relative"),
    ],
)
def test_given_invalid_bundle_when_validated_then_validation_error_lists_contract_failures(
    tmp_path,
    corrupt,
    message,
):
    bundle = _valid_bundle(tmp_path)
    _corrupt_bundle(bundle, corrupt)

    with pytest.raises(ValidationError) as error:
        validate_bundle(bundle, _resolved_config())

    assert message in str(error.value)


def _valid_bundle(tmp_path: Path) -> Path:
    bundle = tmp_path / "staging"
    bundle.mkdir()
    input_config = tmp_path / "input.yaml"
    input_config.write_text("dataset:\n  total_traces: 2\n  version_count: 2\n", encoding="utf-8")

    snapshots = (
        ProcessTreeSnapshot(version_id="v1", process_tree="'A'"),
        ProcessTreeSnapshot(version_id="v2", process_tree="'B'"),
    )
    enriched = enrich_traces(
        traces=(
            _trace("v1", 0, "A"),
            _trace("v2", 1, "B"),
        ),
        snapshots=snapshots,
        config=EnrichmentConfig(
            lifecycle=LifecycleConfig(assign_enabled=False),
            resources=ResourceConfig(pool_size=1),
            temporal=TemporalConfig(
                arrival_rate=1.0,
                duration_mu=-2.0,
                duration_sigma=0.0,
                epoch=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ),
        rng=Random(13),
    )
    dataset_path = bundle / "dataset.xes"
    write_xes(assemble_xes(enriched), dataset_path)
    structures = export_structures(snapshots=snapshots, output_root=bundle)
    required_contract_paths = _write_required_contract_artifacts(bundle)
    artifact_paths = (dataset_path, structures.catalog_path) + required_contract_paths + tuple(
        path
        for artifact in structures.artifacts
        for path in (artifact.ptml_path, artifact.bpmn_path)
    )
    write_draft_evidence(
        staging_dir=bundle,
        input_config_path=input_config,
        resolved_config=_resolved_config(),
        enriched_log=enriched,
        artifact_paths=artifact_paths,
        wrapper_seed=13,
        cdlg_randomness_note="CDLG randomness is external to this wrapper.",
    )
    return bundle


def _trace(version_id: str, source_index: int, activity: str) -> AnnotatedTrace:
    return AnnotatedTrace(
        source_index=source_index,
        attributes={"concept:version": version_id},
        events=(AnnotatedEvent(attributes={"concept:name": activity}),),
    )


def _resolved_config() -> dict:
    return {
        "dataset": {
            "total_traces": 2,
            "version_count": 2,
            "version_ids": ["v1", "v2"],
        },
        "trace_allocation": [1, 1],
    }


def _corrupt_bundle(bundle: Path, corrupt: str) -> None:
    if corrupt == "missing_bpmn":
        (bundle / "models/bpmn/v2.bpmn").unlink()
        _rewrite_checksums_for(bundle)
    elif corrupt == "missing_raw_xes":
        (bundle / "raw/cdlg_output.xes").unlink()
        _rewrite_checksums_for(bundle)
    elif corrupt == "missing_raw_drift_info":
        (bundle / "raw/drift_info.csv").unlink()
        _rewrite_checksums_for(bundle)
    elif corrupt == "missing_raw_parameters":
        (bundle / "raw/cdlg_parameters.txt").unlink()
        _rewrite_checksums_for(bundle)
    elif corrupt == "missing_run_log":
        (bundle / "logs/run.log").unlink()
        _rewrite_checksums_for(bundle)
    elif corrupt == "missing_cdlg_stdout":
        (bundle / "logs/cdlg_stdout.log").unlink()
        _rewrite_checksums_for(bundle)
    elif corrupt == "missing_cdlg_stderr":
        (bundle / "logs/cdlg_stderr.log").unlink()
        _rewrite_checksums_for(bundle)
    elif corrupt == "missing_validation_report":
        (bundle / "reports/validation.json").unlink()
        _rewrite_checksums_for(bundle)
    elif corrupt == "missing_topology_alignment_report":
        (bundle / "reports/topology_alignment.json").unlink()
        _rewrite_checksums_for(bundle)
    elif corrupt == "missing_drift_metrics":
        (bundle / "reports/drift_metrics.json").unlink()
        _rewrite_checksums_for(bundle)
    elif corrupt == "missing_downstream_xes_config":
        (bundle / "configs/bpm_prediction_xes.yaml").unlink()
        _rewrite_checksums_for(bundle)
    elif corrupt == "missing_downstream_bpmn_config":
        (bundle / "configs/bpm_prediction_bpmn.yaml").unlink()
        _rewrite_checksums_for(bundle)
    elif corrupt == "failed_validation_report":
        (bundle / "reports/validation.json").write_text('{"status": "failed"}\n', encoding="utf-8")
        _rewrite_checksums_for(bundle)
    elif corrupt == "failed_topology_alignment_report":
        (bundle / "reports/topology_alignment.json").write_text('{"status": "failed"}\n', encoding="utf-8")
        _rewrite_checksums_for(bundle)
    elif corrupt == "invalid_downstream_xes_adapter":
        (bundle / "configs/bpm_prediction_xes.yaml").write_text(
            "data:\n  log_path: dataset.xes\nmapping:\n  adapter: csv\n",
            encoding="utf-8",
        )
        _rewrite_checksums_for(bundle)
    elif corrupt == "invalid_downstream_bpmn_catalog":
        (bundle / "configs/bpm_prediction_bpmn.yaml").write_text(
            "mapping:\n  adapter: camunda\n  camunda_adapter:\n    structure:\n      files:\n        catalog_file: other.csv\n",
            encoding="utf-8",
        )
        _rewrite_checksums_for(bundle)
    elif corrupt == "wrong_trace_count":
        _remove_last_trace(bundle / "dataset.xes")
        _rewrite_checksums_for(bundle)
    elif corrupt == "missing_event_version":
        root = ET.parse(bundle / "dataset.xes").getroot()
        event = root.find(".//xes:event", XES_NS)
        assert event is not None
        version = event.find("xes:string[@key='concept:version']", XES_NS)
        assert version is not None
        event.remove(version)
        _write_xml(root, bundle / "dataset.xes")
        _rewrite_checksums_for(bundle)
    elif corrupt == "invalid_lifecycle_pair":
        root = ET.parse(bundle / "dataset.xes").getroot()
        trace = root.find("xes:trace", XES_NS)
        assert trace is not None
        events = trace.findall("xes:event", XES_NS)
        assert len(events) >= 2
        trace.remove(events[-1])
        _write_xml(root, bundle / "dataset.xes")
        _rewrite_checksums_for(bundle)
    elif corrupt == "unsorted_events":
        root = ET.parse(bundle / "dataset.xes").getroot()
        trace = root.find("xes:trace", XES_NS)
        assert trace is not None
        events = trace.findall("xes:event", XES_NS)
        assert len(events) >= 2
        trace.remove(events[0])
        trace.append(events[0])
        _write_xml(root, bundle / "dataset.xes")
        _rewrite_checksums_for(bundle)
    elif corrupt == "duplicate_instance":
        root = ET.parse(bundle / "dataset.xes").getroot()
        instances = root.findall(".//xes:string[@key='concept:instance']", XES_NS)
        assert len(instances) >= 4
        instances[2].attrib["value"] = instances[0].attrib["value"]
        instances[3].attrib["value"] = instances[0].attrib["value"]
        _write_xml(root, bundle / "dataset.xes")
        _rewrite_checksums_for(bundle)
    elif corrupt == "resource_overlap":
        root = ET.parse(bundle / "dataset.xes").getroot()
        resources = root.findall(".//xes:string[@key='org:resource']", XES_NS)
        timestamps = root.findall(".//xes:date[@key='time:timestamp']", XES_NS)
        assert len(resources) >= 4 and len(timestamps) >= 4
        resources[2].attrib["value"] = resources[0].attrib["value"]
        resources[3].attrib["value"] = resources[0].attrib["value"]
        timestamps[2].attrib["value"] = timestamps[0].attrib["value"]
        timestamps[3].attrib["value"] = timestamps[1].attrib["value"]
        _write_xml(root, bundle / "dataset.xes")
        _rewrite_checksums_for(bundle)
    elif corrupt == "broken_bpmn_reference":
        root = ET.parse(bundle / "models/bpmn/v1.bpmn").getroot()
        flow = root.find(".//bpmn:sequenceFlow", BPMN_NS)
        assert flow is not None
        flow.attrib["targetRef"] = "missing_node"
        _write_xml(root, bundle / "models/bpmn/v1.bpmn")
        _rewrite_checksums_for(bundle)
    elif corrupt == "tampered_checksum":
        (bundle / "dataset.xes").write_text("<changed />", encoding="utf-8")
    elif corrupt == "absolute_manifest_path":
        manifest_path = bundle / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["artifacts"][0] = str((bundle / "dataset.xes").resolve())
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        _rewrite_checksums_for(bundle)


def _remove_last_trace(path: Path) -> None:
    root = ET.parse(path).getroot()
    traces = root.findall("xes:trace", XES_NS)
    assert traces
    root.remove(traces[-1])
    _write_xml(root, path)


def _write_xml(root: ET.Element, path: Path) -> None:
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)


def _write_required_contract_artifacts(bundle: Path) -> tuple[Path, ...]:
    paths = (
        bundle / "raw/cdlg_output.xes",
        bundle / "raw/drift_info.csv",
        bundle / "raw/cdlg_parameters.txt",
        bundle / "logs/run.log",
        bundle / "logs/cdlg_stdout.log",
        bundle / "logs/cdlg_stderr.log",
        bundle / "reports/drift_metrics.json",
        bundle / "reports/validation.json",
        bundle / "reports/topology_alignment.json",
        bundle / "configs/bpm_prediction_xes.yaml",
        bundle / "configs/bpm_prediction_bpmn.yaml",
    )
    for path in paths:
        path.parent.mkdir(parents=True, exist_ok=True)
    (bundle / "raw/cdlg_output.xes").write_text("<log />\n", encoding="utf-8")
    (bundle / "raw/drift_info.csv").write_text(
        "log_name;drift_or_noise_id;drift_attribute;drift_sub_attribute;value\n",
        encoding="utf-8",
    )
    (bundle / "raw/cdlg_parameters.txt").write_text("Number_event_logs: 1\n", encoding="utf-8")
    (bundle / "logs/run.log").write_text("initialize\tpassed\tOrchestrator\n", encoding="utf-8")
    (bundle / "logs/cdlg_stdout.log").write_text("stdout\n", encoding="utf-8")
    (bundle / "logs/cdlg_stderr.log").write_text("", encoding="utf-8")
    (bundle / "reports/drift_metrics.json").write_text('{"status": "passed"}\n', encoding="utf-8")
    (bundle / "reports/validation.json").write_text('{"status": "passed"}\n', encoding="utf-8")
    (bundle / "reports/topology_alignment.json").write_text('{"status": "passed"}\n', encoding="utf-8")
    (bundle / "configs/bpm_prediction_xes.yaml").write_text(
        "\n".join(
            [
                "data:",
                "  log_path: dataset.xes",
                "mapping:",
                "  adapter: xes",
                "  xes_adapter:",
                "    version_key: concept:version",
                "    lifecycle_key: lifecycle:transition",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (bundle / "configs/bpm_prediction_bpmn.yaml").write_text(
        "\n".join(
            [
                "mapping:",
                "  adapter: camunda",
                "  camunda_adapter:",
                "    structure:",
                "      source: bpmn",
                "      files:",
                "        catalog_file: models/process_definitions.csv",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return paths


def _rewrite_checksums_for(bundle: Path) -> None:
    from wrapper.evidence import _write_checksums

    paths = tuple(
        path
        for path in bundle.rglob("*")
        if path.is_file() and path.name != "checksums.sha256"
    )
    _write_checksums(bundle / "checksums.sha256", paths, bundle)
