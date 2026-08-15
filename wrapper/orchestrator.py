from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from random import Random
from typing import Any, Callable

from wrapper.annotate_versions import annotate_versions
from wrapper.cdlg_metadata import parse_raw_metadata
from wrapper.cdlg_runner import (
    prepare_runtime_copy,
    render_parameters,
    run_cdlg,
    verify_checkout,
)
from wrapper.config import ResolvedConfig
from wrapper.enrichment import EnrichmentConfig, enrich_traces
from wrapper.evidence import write_downstream_compatibility_artifacts, write_draft_evidence
from wrapper.publication import publish_validated_bundle, retain_failure
from wrapper.structure import BPMN_NS, StructureExportResult, export_structures
from wrapper.validation import validate_bundle
from wrapper.xes import assemble_xes, write_xes


REQUIRED_CDLG_COMMIT = "cbe1534de94f06a3f1cca460b079d436f604445e"
DATASET_NAME = "cdlg_dataset"


@dataclass(frozen=True)
class OrchestratorDependencies:
    verify_checkout: Callable[..., Any] = verify_checkout
    prepare_runtime_copy: Callable[..., Path] = prepare_runtime_copy
    render_parameters: Callable[..., Path] = render_parameters
    run_cdlg: Callable[..., Any] = run_cdlg
    parse_raw_metadata: Callable[..., Any] = parse_raw_metadata
    annotate_versions: Callable[..., Any] = annotate_versions
    export_structures: Callable[..., StructureExportResult] = export_structures
    enrich_traces: Callable[..., Any] = enrich_traces
    assemble_xes: Callable[..., Any] = assemble_xes
    write_xes: Callable[..., None] = write_xes
    write_drift_metrics: Callable[..., Path] | None = None
    write_downstream_artifacts: Callable[..., tuple[Path, ...]] = write_downstream_compatibility_artifacts
    write_evidence: Callable[..., Any] = write_draft_evidence
    publish: Callable[..., Path] = publish_validated_bundle
    retain_failure: Callable[..., Path] = retain_failure
    validate: Callable[..., Any] = validate_bundle
    run_id_factory: Callable[[], str] = lambda: datetime.now(timezone.utc).strftime("run-%Y%m%dT%H%M%S%fZ")


def run_generation_pipeline(
    config_path: Path,
    resolved_config: ResolvedConfig,
    *,
    dependencies: OrchestratorDependencies | None = None,
    project_root: Path | None = None,
) -> Path:
    deps = dependencies or OrchestratorDependencies()
    root = (project_root or Path.cwd()).resolve()
    run_id = deps.run_id_factory()
    work_root = root / "work"
    staging_dir = work_root / run_id / "bundle"
    output_root = root / "outputs" / "datasets"
    failed_root = root / "outputs" / "failed"
    staging_dir.mkdir(parents=True, exist_ok=False)
    run_log_path = staging_dir / "logs/run.log"
    _write_run_log(run_log_path, "initialize", "passed", "Orchestrator")

    stage = "initialize"
    component = "Orchestrator"
    try:
        stage = "verify_checkout"
        component = "CdlgRunner"
        _write_run_log(run_log_path, stage, "started", component)
        checkout_info = deps.verify_checkout(
            _resolve_against_root(resolved_config.cdlg.checkout_path, root),
            REQUIRED_CDLG_COMMIT,
        )
        _write_run_log(run_log_path, stage, "passed", component)

        stage = "prepare_runtime"
        _write_run_log(run_log_path, stage, "started", component)
        runtime_dir = deps.prepare_runtime_copy(
            checkout_info.checkout_path,
            work_root=work_root,
            run_id=run_id,
        )
        deps.render_parameters(runtime_dir, resolved_config)
        _write_run_log(run_log_path, stage, "passed", component)

        stage = "run_cdlg"
        _write_run_log(run_log_path, stage, "started", component)
        cdlg_result = deps.run_cdlg(
            runtime_dir=runtime_dir,
            python_executable=Path(str(resolved_config.cdlg.python_executable or "")),
            staging_raw_dir=staging_dir / "raw",
        )
        _write_run_log(run_log_path, stage, "passed", component)

        stage = "parse_metadata"
        component = "CdlgMetadataParser"
        _write_run_log(run_log_path, stage, "started", component)
        metadata = deps.parse_raw_metadata(
            raw_xes_path=cdlg_result.raw_xes_path,
            drift_csv_path=cdlg_result.raw_drift_csv_path,
            expected_version_ids=resolved_config.dataset.version_ids,
        )
        _write_run_log(run_log_path, stage, "passed", component)

        stage = "annotate_versions"
        component = "VersionAnnotator"
        _write_run_log(run_log_path, stage, "started", component)
        annotated = deps.annotate_versions(
            raw_xes_path=cdlg_result.raw_xes_path,
            metadata=metadata,
            resolved_config=resolved_config,
        )
        _write_run_log(run_log_path, stage, "passed", component)

        stage = "export_structures"
        component = "StructureExporter"
        _write_run_log(run_log_path, stage, "started", component)
        structures = deps.export_structures(snapshots=metadata.snapshots, output_root=staging_dir)
        _write_run_log(run_log_path, stage, "passed", component)

        stage = "enrich_traces"
        component = "LifecycleEnrichment"
        _write_run_log(run_log_path, stage, "started", component)
        enriched = deps.enrich_traces(
            traces=annotated.traces,
            snapshots=metadata.snapshots,
            config=EnrichmentConfig(
                lifecycle=resolved_config.lifecycle,
                resources=resolved_config.resources,
                temporal=resolved_config.temporal,
            ),
            rng=Random(0),
        )
        _write_run_log(run_log_path, stage, "passed", component)

        stage = "write_xes"
        component = "XesWriter"
        _write_run_log(run_log_path, stage, "started", component)
        dataset_path = staging_dir / "dataset.xes"
        debug_dir = staging_dir / "debug/xes_by_version" if resolved_config.output.export_per_version_xes else None
        xes_log = deps.assemble_xes(enriched)
        deps.write_xes(xes_log, dataset_path, per_version_debug_dir=debug_dir)
        _write_run_log(run_log_path, stage, "passed", component)

        stage = "write_drift_metrics"
        component = "EvidenceWriter"
        _write_run_log(run_log_path, stage, "started", component)
        drift_metrics_path = (
            deps.write_drift_metrics(
                staging_dir=staging_dir,
                metadata=metadata,
                enriched_log=enriched,
                resolved_config=resolved_config,
            )
            if deps.write_drift_metrics is not None
            else _write_drift_metrics_report(
                staging_dir=staging_dir,
                metadata=metadata,
                enriched_log=enriched,
                resolved_config=resolved_config,
            )
        )
        _write_run_log(run_log_path, stage, "passed", component)

        stage = "write_reports"
        _write_run_log(run_log_path, stage, "started", component)
        version_counts = _version_counts(enriched.traces)
        downstream_paths = deps.write_downstream_artifacts(
            staging_dir=staging_dir,
            dataset_name=DATASET_NAME,
            version_ids=resolved_config.dataset.version_ids,
            trace_count=len(enriched.traces),
            version_counts=version_counts,
            topology_alignment=_topology_alignment(staging_dir, structures, enriched.traces),
        )
        _write_run_log(run_log_path, stage, "passed", component)

        artifact_paths = (
            dataset_path,
            cdlg_result.raw_xes_path,
            cdlg_result.raw_drift_csv_path,
            cdlg_result.parameters_path,
            run_log_path,
            cdlg_result.stdout_path,
            cdlg_result.stderr_path,
            drift_metrics_path,
            structures.catalog_path,
            *downstream_paths,
            *(
                path
                for artifact in structures.artifacts
                for path in (artifact.ptml_path, artifact.bpmn_path)
            ),
        )
        if debug_dir is not None:
            artifact_paths = artifact_paths + tuple(sorted(debug_dir.glob("*.xes")))

        stage = "write_evidence"
        _write_run_log(run_log_path, stage, "started", component)
        _write_run_log(run_log_path, "publish", "pending", "DatasetPublisher")
        deps.write_evidence(
            staging_dir=staging_dir,
            input_config_path=config_path,
            resolved_config=_serializable_config(resolved_config, run_id=run_id, checkout_info=checkout_info),
            enriched_log=enriched,
            artifact_paths=artifact_paths,
            wrapper_seed=0,
            cdlg_randomness_note="CDLG randomness is external to this wrapper; wrapper enrichment uses seed 0.",
        )

        stage = "publish"
        component = "DatasetPublisher"
        return deps.publish(
            staging_dir=staging_dir,
            output_root=output_root,
            dataset_name=run_id,
            resolved_config=resolved_config,
            validator=deps.validate,
        )
    except Exception as error:
        _write_run_log(run_log_path, stage, "failed", component)
        if staging_dir.exists():
            deps.retain_failure(
                staging_dir=staging_dir,
                failed_root=failed_root,
                dataset_name=run_id,
                error=error,
                component=component,
                stage=stage,
            )
        raise


def _resolve_against_root(path: Path, root: Path) -> Path:
    return path if path.is_absolute() else root / path


def _serializable_config(resolved_config: ResolvedConfig, *, run_id: str, checkout_info: Any) -> dict[str, Any]:
    payload = _to_jsonable(asdict(resolved_config) if is_dataclass(resolved_config) else resolved_config)
    payload["run_id"] = run_id
    payload["cdlg_checkout"] = {
        "origin_url": str(checkout_info.origin_url),
        "commit": str(checkout_info.commit),
    }
    return payload


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Path):
        return value.as_posix()
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    return value


def _version_counts(traces: Any) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trace in traces:
        counts[trace.version_id] = counts.get(trace.version_id, 0) + 1
    return counts


def _topology_alignment(
    bundle_dir: Path,
    structures: StructureExportResult,
    traces: Any,
) -> dict[str, dict[str, list[str]]]:
    xes_activities: dict[str, set[str]] = {}
    for trace in traces:
        activities = xes_activities.setdefault(trace.version_id, set())
        for instance in trace.instances:
            activities.add(instance.activity)

    alignment: dict[str, dict[str, list[str]]] = {}
    for artifact in structures.artifacts:
        bpmn_activities = _bpmn_task_names(artifact.bpmn_path)
        version_xes = xes_activities.get(artifact.version_id, set())
        alignment[artifact.version_id] = {
            "bpmn_activities": sorted(bpmn_activities),
            "xes_activities": sorted(version_xes),
            "missing_in_bpmn": sorted(version_xes - bpmn_activities),
            "missing_in_xes": sorted(bpmn_activities - version_xes),
        }
    return alignment


def _bpmn_task_names(path: Path) -> set[str]:
    root = ET.parse(path).getroot()
    return {task.attrib["name"] for task in root.findall(f".//{{{BPMN_NS}}}task")}


def _write_run_log(path: Path, stage: str, status: str, component: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(
            "\t".join(
                [
                    datetime.now(timezone.utc).isoformat(),
                    stage,
                    status,
                    component,
                ]
            )
            + "\n"
        )


def _write_drift_metrics_report(
    *,
    staging_dir: Path,
    metadata: Any,
    enriched_log: Any,
    resolved_config: ResolvedConfig,
) -> Path:
    reports_dir = staging_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    path = reports_dir / "drift_metrics.json"
    payload = {
        "status": "passed",
        "drift_type": resolved_config.cdlg.drift_type,
        "drift_count": max(len(metadata.snapshots) - 1, 0),
        "raw_trace_count": metadata.raw_trace_count,
        "published_trace_count": len(enriched_log.traces),
        "version_counts": _version_counts(enriched_log.traces),
        "boundaries": [
            {
                "version": boundary.version_id,
                "start_index": boundary.start_index,
                "end_index": boundary.end_index,
            }
            for boundary in metadata.boundaries
        ],
        "snapshots": [
            {
                "version": snapshot.version_id,
                "process_tree_sha256": hashlib.sha256(snapshot.process_tree.encode("utf-8")).hexdigest(),
                "process_tree": snapshot.process_tree,
            }
            for snapshot in metadata.snapshots
        ],
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
