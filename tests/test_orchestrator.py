from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from wrapper.cdlg_metadata import ProcessTreeSnapshot
from wrapper.config import load_config
from wrapper.enrichment import EnrichedActivityInstance, EnrichedLog, EnrichedTrace
from wrapper.errors import ArtifactError, ValidationError
from wrapper.orchestrator import OrchestratorDependencies, run_generation_pipeline
from wrapper.publication import publish_validated_bundle
from wrapper.structure import StructureArtifact, StructureExportResult


def test_given_stage_results_when_orchestrated_then_pipeline_order_and_published_path_are_exact(tmp_path):
    calls: list[str] = []
    config_path = _config(tmp_path)
    resolved_config = load_config(config_path)

    deps = _dependencies(tmp_path, calls)

    published = run_generation_pipeline(
        config_path,
        resolved_config,
        dependencies=deps,
        project_root=tmp_path,
    )

    assert calls == [
        "verify",
        "runtime",
        "parameters",
        "run",
        "metadata",
        "annotate",
        "structures",
        "enrich",
        "assemble_xes",
        "write_xes",
        "drift_metrics",
        "downstream",
        "evidence",
        "validate",
        "publish",
    ]
    assert published == tmp_path / "outputs/datasets/run-001"
    assert published.joinpath("dataset.xes").is_file()
    assert published.joinpath("raw/cdlg_output.xes").is_file()
    assert published.joinpath("raw/drift_info.csv").is_file()
    assert published.joinpath("logs/run.log").is_file()
    assert published.joinpath("logs/cdlg_stdout.log").is_file()
    assert published.joinpath("reports/drift_metrics.json").is_file()
    assert not tmp_path.joinpath("outputs/failed/run-001").exists()


@pytest.mark.parametrize(
    ("failing_stage", "error", "expected_stage", "expected_component"),
    [
        ("metadata", ArtifactError("bad metadata"), "parse_metadata", "CdlgMetadataParser"),
        ("validate", ValidationError("invalid bundle"), "publish", "DatasetPublisher"),
    ],
)
def test_given_failure_after_staging_when_orchestrated_then_failed_bundle_is_retained(
    tmp_path,
    failing_stage,
    error,
    expected_stage,
    expected_component,
):
    calls: list[str] = []
    config_path = _config(tmp_path)
    resolved_config = load_config(config_path)
    deps = _dependencies(tmp_path, calls, failing_stage=failing_stage, error=error)

    with pytest.raises(type(error), match=str(error)):
        run_generation_pipeline(
            config_path,
            resolved_config,
            dependencies=deps,
            project_root=tmp_path,
        )

    failed = tmp_path / "outputs/failed/run-001"
    assert failed.is_dir()
    assert not tmp_path.joinpath("outputs/datasets/run-001").exists()
    failure = json.loads(failed.joinpath("failure.json").read_text(encoding="utf-8"))
    assert failure["status"] == "failed"
    assert failure["stage"] == expected_stage
    assert failure["component"] == expected_component
    assert failed.joinpath("logs/traceback.txt").is_file()
    if failing_stage in {"metadata", "validate"}:
        assert failed.joinpath("raw/cdlg_output.xes").is_file()


def _dependencies(
    tmp_path: Path,
    calls: list[str],
    *,
    failing_stage: str | None = None,
    error: Exception | None = None,
) -> OrchestratorDependencies:
    epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)

    def verify(checkout, required_commit):
        calls.append("verify")
        _ = (checkout, required_commit)
        return SimpleNamespace(
            checkout_path=tmp_path / "CDLG",
            origin_url="https://gitlab.uni-mannheim.de/processanalytics/cdlg_tool",
            commit="cbe1534de94f06a3f1cca460b079d436f604445e",
        )

    def runtime(checkout_path, *, work_root, run_id):
        calls.append("runtime")
        path = work_root / run_id / "cdlg-runtime"
        path.mkdir(parents=True)
        return path

    def parameters(runtime_dir, resolved_config):
        calls.append("parameters")
        path = runtime_dir / "src/input_parameters/default"
        path.parent.mkdir(parents=True)
        path.write_text("Number_event_logs: 1\n", encoding="utf-8")
        return path

    def run(*, runtime_dir, python_executable, staging_raw_dir):
        calls.append("run")
        _ = (runtime_dir, python_executable)
        staging_raw_dir.mkdir(parents=True)
        logs_dir = staging_raw_dir.parent / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        raw_xes = staging_raw_dir / "cdlg_output.xes"
        drift = staging_raw_dir / "drift_info.csv"
        params = staging_raw_dir / "cdlg_parameters.txt"
        stdout = logs_dir / "cdlg_stdout.log"
        stderr = logs_dir / "cdlg_stderr.log"
        raw_xes.write_text("<log />\n", encoding="utf-8")
        drift.write_text("log_name;drift_or_noise_id;drift_attribute;drift_sub_attribute;value\n", encoding="utf-8")
        params.write_text("Number_event_logs: 1\n", encoding="utf-8")
        stdout.write_text("ok\n", encoding="utf-8")
        stderr.write_text("", encoding="utf-8")
        return SimpleNamespace(
            raw_xes_path=raw_xes,
            raw_drift_csv_path=drift,
            parameters_path=params,
            stdout_path=stdout,
            stderr_path=stderr,
        )

    def metadata(**kwargs):
        calls.append("metadata")
        _ = kwargs
        if failing_stage == "metadata":
            raise error
        return SimpleNamespace(snapshots=(ProcessTreeSnapshot(version_id="v1", process_tree="'A'"),))

    def annotate(**kwargs):
        calls.append("annotate")
        _ = kwargs
        return SimpleNamespace(traces=("annotated",))

    def structures(*, snapshots, output_root, **kwargs):
        calls.append("structures")
        _ = (snapshots, kwargs)
        bpmn = output_root / "models/bpmn/v1.bpmn"
        ptml = output_root / "models/ptml/v1.ptml"
        catalog = output_root / "models/process_definitions.csv"
        bpmn.parent.mkdir(parents=True)
        ptml.parent.mkdir(parents=True)
        catalog.parent.mkdir(parents=True, exist_ok=True)
        bpmn.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL">
  <bpmn:process id="process_cdlg">
    <bpmn:task id="task_a" name="A" />
  </bpmn:process>
</bpmn:definitions>
""",
            encoding="utf-8",
        )
        ptml.write_text("<ptml />\n", encoding="utf-8")
        catalog.write_text(
            "proc_def_id,proc_def_key,version,tenant_id,deployment_id,bpmn_path\n"
            "cdlg_v1,cdlg_dataset,v1,,cdlg_deployment_v1,models/bpmn/v1.bpmn\n",
            encoding="utf-8",
        )
        return StructureExportResult(
            artifacts=(StructureArtifact(version_id="v1", ptml_path=ptml, bpmn_path=bpmn, id_mapping={}),),
            catalog_path=catalog,
        )

    def enrich(**kwargs):
        calls.append("enrich")
        _ = kwargs
        instance = EnrichedActivityInstance(
            activity="A",
            occurrence_index=1,
            instance_id="case_000001_a_001",
            resource="resource_a_001",
            start_at=epoch,
            complete_at=epoch,
            events=(),
        )
        trace = EnrichedTrace(
            source_index=0,
            case_id="case_000001",
            version_id="v1",
            arrival_at=epoch,
            complete_at=epoch,
            attributes={},
            instances=(instance,),
        )
        return EnrichedLog(
            traces=(trace,),
            resource_pools={"A": ("resource_a_001",)},
            version_activation_times={"v1": epoch},
            carryover_summary={"same_version": 1},
        )

    def assemble_xes(enriched, **kwargs):
        calls.append("assemble_xes")
        _ = kwargs
        return enriched

    def write_xes(log, path, *, per_version_debug_dir=None):
        calls.append("write_xes")
        _ = (log, per_version_debug_dir)
        path.write_text("<log />\n", encoding="utf-8")

    def downstream(**kwargs):
        calls.append("downstream")
        staging_dir = kwargs["staging_dir"]
        paths = (
            staging_dir / "configs/bpm_prediction_xes.yaml",
            staging_dir / "configs/bpm_prediction_bpmn.yaml",
            staging_dir / "reports/validation.json",
            staging_dir / "reports/topology_alignment.json",
        )
        for path in paths:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
        return paths

    def drift_metrics(**kwargs):
        calls.append("drift_metrics")
        staging_dir = kwargs["staging_dir"]
        path = staging_dir / "reports/drift_metrics.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"status": "passed"}\n', encoding="utf-8")
        return path

    def evidence(**kwargs):
        calls.append("evidence")
        artifact_relatives = {path.relative_to(kwargs["staging_dir"]).as_posix() for path in kwargs["artifact_paths"]}
        assert "raw/drift_info.csv" in artifact_relatives
        assert "logs/run.log" in artifact_relatives
        assert "reports/drift_metrics.json" in artifact_relatives
        staging_dir = kwargs["staging_dir"]
        (staging_dir / "manifest.json").write_text("{}\n", encoding="utf-8")
        (staging_dir / "checksums.sha256").write_text("", encoding="utf-8")
        (staging_dir / "environment.json").write_text("{}\n", encoding="utf-8")
        return SimpleNamespace()

    def validate(bundle_dir, resolved_config):
        calls.append("validate")
        _ = (bundle_dir, resolved_config)
        if failing_stage == "validate":
            raise error
        return SimpleNamespace()

    def publish(**kwargs):
        result = publish_validated_bundle(**kwargs)
        calls.append("publish")
        return result

    return OrchestratorDependencies(
        verify_checkout=verify,
        prepare_runtime_copy=runtime,
        render_parameters=parameters,
        run_cdlg=run,
        parse_raw_metadata=metadata,
        annotate_versions=annotate,
        export_structures=structures,
        enrich_traces=enrich,
        assemble_xes=assemble_xes,
        write_xes=write_xes,
        write_drift_metrics=drift_metrics,
        write_downstream_artifacts=downstream,
        write_evidence=evidence,
        publish=publish,
        validate=validate,
        run_id_factory=lambda: "run-001",
    )


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        "\n".join(
            [
                "dataset:",
                "  total_traces: 1",
                "  version_count: 1",
                "cdlg:",
                "  checkout_path: CDLG",
                f"  python_executable: {tmp_path.joinpath('python.exe').as_posix()}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path
