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
