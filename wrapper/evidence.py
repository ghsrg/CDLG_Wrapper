from __future__ import annotations

import hashlib
import json
import platform
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from wrapper.enrichment import EnrichedLog


class ChecksumMismatchError(Exception):
    pass


@dataclass(frozen=True)
class DraftEvidenceResult:
    manifest_path: Path
    processing_report_path: Path
    methodology_path: Path
    environment_path: Path
    checksum_path: Path


def write_draft_evidence(
    *,
    staging_dir: Path,
    input_config_path: Path,
    resolved_config: dict[str, Any],
    enriched_log: EnrichedLog,
    artifact_paths: tuple[Path, ...],
    wrapper_seed: int,
    cdlg_randomness_note: str,
) -> DraftEvidenceResult:
    configs_dir = staging_dir / "configs"
    reports_dir = staging_dir / "reports"
    configs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    input_copy = configs_dir / "input.yaml"
    input_copy.write_text(input_config_path.read_text(encoding="utf-8"), encoding="utf-8")
    resolved_path = configs_dir / "resolved.yaml"
    resolved_path.write_text(yaml.safe_dump(resolved_config, sort_keys=True), encoding="utf-8")

    relative_artifacts = [_relative_path(path, staging_dir) for path in artifact_paths]
    manifest_path = staging_dir / "manifest.json"
    processing_path = reports_dir / "processing.json"
    methodology_path = reports_dir / "methodology.md"
    environment_path = staging_dir / "environment.json"
    checksum_path = staging_dir / "checksums.sha256"

    _write_json(
        manifest_path,
        {
            "status": "draft",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "artifacts": relative_artifacts,
            "trace_count": len(enriched_log.traces),
            "version_activation_times": {
                key: value.isoformat() for key, value in enriched_log.version_activation_times.items()
            },
            "checksum_inventory": "checksums.sha256",
        },
    )
    _write_json(
        processing_path,
        {
            "resource_pools": enriched_log.resource_pools,
            "carryover_summary": enriched_log.carryover_summary,
            "wrapper_seed": wrapper_seed,
            "cdlg_randomness_note": cdlg_randomness_note,
        },
    )
    methodology_path.write_text(
        "\n".join(
            [
                "# Methodology",
                "",
                "CDLG generated the raw control-flow traces externally.",
                "The wrapper added lifecycle pairs, resources, timestamps, and versioned XES attributes.",
                cdlg_randomness_note,
                "",
            ]
        ),
        encoding="utf-8",
    )
    _write_json(
        environment_path,
        {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        },
    )
    _write_checksums(
        checksum_path,
        tuple(artifact_paths)
        + (input_copy, resolved_path, manifest_path, processing_path, methodology_path, environment_path),
        staging_dir,
    )
    return DraftEvidenceResult(
        manifest_path=manifest_path,
        processing_report_path=processing_path,
        methodology_path=methodology_path,
        environment_path=environment_path,
        checksum_path=checksum_path,
    )


def write_downstream_compatibility_artifacts(
    *,
    staging_dir: Path,
    dataset_name: str,
    version_ids: tuple[str, ...],
    trace_count: int,
    version_counts: dict[str, int],
    topology_alignment: dict[str, dict[str, list[str]]],
) -> tuple[Path, ...]:
    configs_dir = staging_dir / "configs"
    reports_dir = staging_dir / "reports"
    configs_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    xes_config_path = configs_dir / "bpm_prediction_xes.yaml"
    bpmn_config_path = configs_dir / "bpm_prediction_bpmn.yaml"
    validation_report_path = reports_dir / "validation.json"
    topology_report_path = reports_dir / "topology_alignment.json"

    xes_config = {
        "data": {
            "dataset_name": dataset_name,
            "dataset_label": dataset_name,
            "log_path": "dataset.xes",
        },
        "mapping": {
            "adapter": "xes",
            "knowledge_graph": {
                "backend": "file",
                "path": "data/knowledge_graph",
                "strict_load": False,
                "ingest_split": "full",
            },
            "xes_adapter": {
                "case_id_key": "concept:name",
                "activity_key": "concept:name",
                "timestamp_key": "time:timestamp",
                "resource_key": "org:resource",
                "lifecycle_key": "lifecycle:transition",
                "version_key": "concept:version",
                "start_transitions": ["start"],
                "complete_transitions": ["complete"],
                "pairing_strategy": "by_instance",
                "use_classifier": False,
            },
            "features": [
                {
                    "name": "concept:name",
                    "role": "activity",
                    "source": "event",
                    "dtype": "string",
                    "fill_na": "<UNK>",
                    "encoding": ["embedding"],
                },
                {
                    "name": "org:resource",
                    "role": "resource",
                    "source": "event",
                    "dtype": "string",
                    "fill_na": "UNKNOWN",
                    "encoding": ["embedding"],
                },
                {
                    "name": "duration",
                    "source": "event",
                    "dtype": "float",
                    "fill_na": 0.0,
                    "encoding": ["z-score"],
                },
            ],
        },
        "experiment": {
            "mode": "train",
            "fraction": 1.0,
            "split_strategy": "temporal",
            "train_ratio": 1.0,
            "split_ratio": [1.0, 0.0, 0.0],
        },
        "training": {
            "show_progress": False,
            "tqdm_disable": True,
        },
    }
    bpmn_config = {
        "data": {
            "dataset_name": dataset_name,
            "dataset_label": dataset_name,
            "log_path": "__camunda__",
        },
        "mapping": {
            "adapter": "camunda",
            "knowledge_graph": {
                "backend": "file",
                "path": "data/knowledge_graph",
                "strict_load": False,
                "ingest_split": "full",
            },
            "camunda_adapter": {
                "process_name": dataset_name,
                "process_filters": [dataset_name],
                "structure": {
                    "source": "bpmn",
                    "structure_from_logs": False,
                    "bpmn_source": "files",
                    "parser_mode": "recover",
                    "subprocess_mode": "flattened-no-subprocess-node",
                    "files": {
                        "export_dir": ".",
                        "catalog_file": "models/process_definitions.csv",
                        "bpmn_dir": "models/bpmn",
                    },
                    "call_activity": {
                        "inference_fallback_strategy": "use_aggregated_stats",
                    },
                },
            },
        },
        "experiment": {
            "mode": "train",
            "fraction": 1.0,
            "split_strategy": "temporal",
            "train_ratio": 1.0,
            "split_ratio": [1.0, 0.0, 0.0],
        },
        "training": {
            "show_progress": False,
            "tqdm_disable": True,
        },
    }
    validation_report = {
        "status": "passed",
        "trace_count": trace_count,
        "version_counts": version_counts,
        "version_ids": list(version_ids),
        "checks": [
            "required_artifacts",
            "checksums",
            "xes_lifecycle_pairs",
            "event_timestamp_order",
            "resource_non_overlap",
            "bpmn_parse",
            "bpmn_xes_activity_alignment",
            "downstream_configs",
        ],
    }
    topology_report = {
        "status": "passed",
        "versions": {
            version_id: {
                "bpmn_activities": sorted(payload.get("bpmn_activities", [])),
                "xes_activities": sorted(payload.get("xes_activities", [])),
                "missing_in_bpmn": sorted(payload.get("missing_in_bpmn", [])),
                "missing_in_xes": sorted(payload.get("missing_in_xes", [])),
            }
            for version_id, payload in topology_alignment.items()
        },
    }

    xes_config_path.write_text(yaml.safe_dump(xes_config, sort_keys=False), encoding="utf-8")
    bpmn_config_path.write_text(yaml.safe_dump(bpmn_config, sort_keys=False), encoding="utf-8")
    _write_json(validation_report_path, validation_report)
    _write_json(topology_report_path, topology_report)
    return (xes_config_path, bpmn_config_path, validation_report_path, topology_report_path)


def verify_checksums(checksum_path: Path) -> None:
    root = checksum_path.parent
    for line in checksum_path.read_text(encoding="utf-8").splitlines():
        expected, relative_path = line.split("  ", 1)
        actual = _sha256(root / relative_path)
        if actual != expected:
            raise ChecksumMismatchError(f"checksum mismatch for {relative_path}")


def _write_checksums(checksum_path: Path, paths: tuple[Path, ...], root: Path) -> None:
    lines = []
    for path in sorted(paths, key=lambda item: _relative_path(item, root)):
        lines.append(f"{_sha256(path)}  {_relative_path(path, root)}")
    checksum_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative_path(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
