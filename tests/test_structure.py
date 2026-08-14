import csv
import xml.etree.ElementTree as ET

import pytest
from pm4py.objects.bpmn.importer import importer as bpmn_importer
from pm4py.objects.process_tree.importer import importer as ptml_importer

from wrapper.cdlg_metadata import ProcessTreeSnapshot
from wrapper.errors import ArtifactError
import wrapper.structure as structure
from wrapper.structure import export_structures


BPMN_NS = {"bpmn": "http://www.omg.org/spec/BPMN/20100524/MODEL"}


def test_given_snapshots_when_structures_exported_then_artifact_pairs_and_catalog_are_deterministic(tmp_path):
    snapshots = (
        ProcessTreeSnapshot(version_id="v1", process_tree="->('A','B')"),
        ProcessTreeSnapshot(version_id="v2", process_tree="->('A','C')"),
    )

    first = export_structures(snapshots=snapshots, output_root=tmp_path / "first")
    second = export_structures(snapshots=snapshots, output_root=tmp_path / "second")

    assert [item.version_id for item in first.artifacts] == ["v1", "v2"]
    for item in first.artifacts:
        assert item.ptml_path.is_file()
        assert item.bpmn_path.is_file()
        assert item.bpmn_path.read_text(encoding="utf-8").startswith("<?xml")
        assert ptml_importer.apply(str(item.ptml_path)) is not None
        assert bpmn_importer.apply(str(item.bpmn_path)) is not None

    assert _catalog_rows(first.catalog_path) == [
        {
            "process_key": "cdlg_v1",
            "proc_def_id": "cdlg_v1",
            "version": "v1",
            "bpmn_path": "models/bpmn/v1.bpmn",
        },
        {
            "process_key": "cdlg_v2",
            "proc_def_id": "cdlg_v2",
            "version": "v2",
            "bpmn_path": "models/bpmn/v2.bpmn",
        },
    ]
    assert _bpmn_ids(first.artifacts[0].bpmn_path) == _bpmn_ids(second.artifacts[0].bpmn_path)
    assert _catalog_rows(first.catalog_path) == _catalog_rows(second.catalog_path)


def test_given_unchanged_activity_when_bpmn_normalized_then_task_id_is_stable_and_references_are_valid(tmp_path):
    result = export_structures(
        snapshots=(
            ProcessTreeSnapshot(version_id="v1", process_tree="->('A','B')"),
            ProcessTreeSnapshot(version_id="v2", process_tree="->('A','C')"),
        ),
        output_root=tmp_path,
    )

    v1_ids = _task_ids_by_name(result.artifacts[0].bpmn_path)
    v2_ids = _task_ids_by_name(result.artifacts[1].bpmn_path)
    assert v1_ids["A"] == v2_ids["A"]
    assert set(v1_ids) == {"A", "B"}
    assert set(v2_ids) == {"A", "C"}

    for artifact in result.artifacts:
        ids = _bpmn_ids(artifact.bpmn_path)
        assert len(ids) == len(set(ids))
        for source_ref, target_ref in _sequence_flow_refs(artifact.bpmn_path):
            assert source_ref in ids
            assert target_ref in ids


def test_given_normalized_id_collision_when_exporting_bpmn_then_deterministic_suffix_is_added(tmp_path, monkeypatch):
    monkeypatch.setattr(structure, "_task_id", lambda label: "task_collision")

    result = export_structures(
        snapshots=(ProcessTreeSnapshot(version_id="v1", process_tree="->('A','B')"),),
        output_root=tmp_path,
    )

    task_ids = _task_ids_by_name(result.artifacts[0].bpmn_path)
    assert task_ids == {
        "A": "task_collision",
        "B": "task_collision_002",
    }
    ids = _bpmn_ids(result.artifacts[0].bpmn_path)
    assert len(ids) == len(set(ids))
    for source_ref, target_ref in _sequence_flow_refs(result.artifacts[0].bpmn_path):
        assert source_ref in ids
        assert target_ref in ids


def test_given_parallel_operator_when_bpmn_normalized_then_gateway_ids_are_deterministic(tmp_path):
    snapshots = (ProcessTreeSnapshot(version_id="v1", process_tree="+('A','B')"),)

    first = export_structures(snapshots=snapshots, output_root=tmp_path / "first")
    second = export_structures(snapshots=snapshots, output_root=tmp_path / "second")

    first_gateway_ids = _element_ids(first.artifacts[0].bpmn_path, "parallelGateway")
    second_gateway_ids = _element_ids(second.artifacts[0].bpmn_path, "parallelGateway")
    assert first_gateway_ids == second_gateway_ids
    assert first_gateway_ids == [
        "gateway_parallel_split_24fc2542",
        "gateway_parallel_join_24fc2542",
    ]

    ids = _bpmn_ids(first.artifacts[0].bpmn_path)
    for source_ref, target_ref in _sequence_flow_refs(first.artifacts[0].bpmn_path):
        assert source_ref in ids
        assert target_ref in ids


def test_given_snapshot_when_exporting_bpmn_then_pm4py_process_tree_conversion_is_used(tmp_path, monkeypatch):
    calls = {"convert": 0, "export": 0}
    original_convert = structure.process_tree_converter.apply
    original_export = structure.bpmn_exporter.apply

    def convert_spy(*args, **kwargs):
        calls["convert"] += 1
        return original_convert(*args, **kwargs)

    def export_spy(*args, **kwargs):
        calls["export"] += 1
        return original_export(*args, **kwargs)

    monkeypatch.setattr(structure.process_tree_converter, "apply", convert_spy)
    monkeypatch.setattr(structure.bpmn_exporter, "apply", export_spy)

    export_structures(
        snapshots=(ProcessTreeSnapshot(version_id="v1", process_tree="*('A','B')"),),
        output_root=tmp_path,
    )

    assert calls == {"convert": 1, "export": 1}
    assert len(_element_ids(tmp_path / "models/bpmn/v1.bpmn", "exclusiveGateway")) == 2


def test_given_duplicate_visible_labels_when_structures_exported_then_alignment_error(tmp_path):
    with pytest.raises(ArtifactError, match="duplicate visible activity"):
        export_structures(
            snapshots=(ProcessTreeSnapshot(version_id="v1", process_tree="->('A','A')"),),
            output_root=tmp_path,
        )


def _catalog_rows(path):
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _bpmn_ids(path):
    root = ET.parse(path).getroot()
    return [element.attrib["id"] for element in root.findall(".//*[@id]")]


def _task_ids_by_name(path):
    root = ET.parse(path).getroot()
    tasks = root.findall(".//bpmn:task", BPMN_NS)
    return {task.attrib["name"]: task.attrib["id"] for task in tasks}


def _sequence_flow_refs(path):
    root = ET.parse(path).getroot()
    flows = root.findall(".//bpmn:sequenceFlow", BPMN_NS)
    return [(flow.attrib["sourceRef"], flow.attrib["targetRef"]) for flow in flows]


def _element_ids(path, tag_name):
    root = ET.parse(path).getroot()
    return [element.attrib["id"] for element in root.findall(f".//bpmn:{tag_name}", BPMN_NS)]
