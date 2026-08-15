from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from random import Random

import pytest
import yaml

from wrapper.annotate_versions import AnnotatedEvent, AnnotatedTrace
from wrapper.cdlg_metadata import ProcessTreeSnapshot
from wrapper.config import LifecycleConfig, ResourceConfig, TemporalConfig
from wrapper.enrichment import EnrichmentConfig, enrich_traces
from wrapper.evidence import (
    ChecksumMismatchError,
    verify_checksums,
    write_draft_evidence,
    write_downstream_compatibility_artifacts,
)
from wrapper.xes import assemble_xes, write_xes


def test_given_staging_artifacts_when_evidence_written_then_paths_are_relative_and_checksums_verify(tmp_path):
    input_config = tmp_path / "input.yaml"
    input_config.write_text("dataset:\n  total_traces: 1\n", encoding="utf-8")
    dataset_path = tmp_path / "dataset.xes"
    enriched = _enriched()
    write_xes(assemble_xes(enriched), dataset_path)

    result = write_draft_evidence(
        staging_dir=tmp_path,
        input_config_path=input_config,
        resolved_config={
            "dataset": {"total_traces": 1, "version_count": 1},
            "temporal": {"arrival_rate": 1.0},
        },
        enriched_log=enriched,
        artifact_paths=(dataset_path,),
        wrapper_seed=13,
        cdlg_randomness_note="CDLG randomness is external to this wrapper.",
    )

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    processing = json.loads(result.processing_report_path.read_text(encoding="utf-8"))
    resolved = yaml.safe_load((tmp_path / "configs/resolved.yaml").read_text(encoding="utf-8"))

    assert manifest["artifacts"] == ["dataset.xes"]
    assert not Path(manifest["artifacts"][0]).is_absolute()
    assert processing["resource_pools"] == {
        activity: list(pool) for activity, pool in enriched.resource_pools.items()
    }
    assert processing["carryover_summary"] == enriched.carryover_summary
    assert resolved["dataset"]["total_traces"] == 1
    assert verify_checksums(tmp_path / "checksums.sha256") is None


def test_given_artifact_changes_after_checksum_when_verified_then_mismatch_is_reported(tmp_path):
    input_config = tmp_path / "input.yaml"
    input_config.write_text("dataset:\n  total_traces: 1\n", encoding="utf-8")
    dataset_path = tmp_path / "dataset.xes"
    dataset_path.write_text("<log />", encoding="utf-8")
    result = write_draft_evidence(
        staging_dir=tmp_path,
        input_config_path=input_config,
        resolved_config={},
        enriched_log=_enriched(),
        artifact_paths=(dataset_path,),
        wrapper_seed=13,
        cdlg_randomness_note="CDLG randomness is external to this wrapper.",
    )
    dataset_path.write_text("<changed />", encoding="utf-8")

    with pytest.raises(ChecksumMismatchError):
        verify_checksums(result.checksum_path)


def test_given_bundle_context_when_downstream_artifacts_written_then_configs_and_reports_are_compatible(tmp_path):
    paths = write_downstream_compatibility_artifacts(
        staging_dir=tmp_path,
        dataset_name="cdlg_dataset",
        version_ids=("v1", "v2"),
        trace_count=4,
        version_counts={"v1": 2, "v2": 2},
        topology_alignment={
            "v1": {"bpmn_activities": ["A"], "xes_activities": ["A"]},
            "v2": {"bpmn_activities": ["B"], "xes_activities": ["B"]},
        },
    )

    assert {path.relative_to(tmp_path).as_posix() for path in paths} == {
        "configs/bpm_prediction_xes.yaml",
        "configs/bpm_prediction_bpmn.yaml",
        "reports/validation.json",
        "reports/topology_alignment.json",
    }

    xes_config = yaml.safe_load((tmp_path / "configs/bpm_prediction_xes.yaml").read_text(encoding="utf-8"))
    bpmn_config = yaml.safe_load((tmp_path / "configs/bpm_prediction_bpmn.yaml").read_text(encoding="utf-8"))
    validation = json.loads((tmp_path / "reports/validation.json").read_text(encoding="utf-8"))
    topology = json.loads((tmp_path / "reports/topology_alignment.json").read_text(encoding="utf-8"))

    assert xes_config["data"]["log_path"] == "dataset.xes"
    assert xes_config["mapping"]["adapter"] == "xes"
    assert xes_config["mapping"]["xes_adapter"]["version_key"] == "concept:version"
    assert bpmn_config["mapping"]["adapter"] == "camunda"
    assert bpmn_config["mapping"]["camunda_adapter"]["structure"]["files"]["catalog_file"] == "models/process_definitions.csv"
    assert validation["status"] == "passed"
    assert validation["trace_count"] == 4
    assert topology["status"] == "passed"
    assert topology["versions"]["v1"]["missing_in_bpmn"] == []


def _enriched():
    return enrich_traces(
        traces=(
            AnnotatedTrace(
                source_index=0,
                attributes={"concept:version": "v1"},
                events=(AnnotatedEvent(attributes={"concept:name": "A"}),),
            ),
        ),
        snapshots=(ProcessTreeSnapshot(version_id="v1", process_tree="'A'"),),
        config=EnrichmentConfig(
            lifecycle=LifecycleConfig(assign_enabled=False),
            resources=ResourceConfig(pool_size=1),
            temporal=TemporalConfig(
                arrival_rate=1.0,
                duration_mu=-2.0,
                duration_sigma=0.1,
                epoch=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        ),
        rng=Random(13),
    )
