from __future__ import annotations

import json
import shutil
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from wrapper.errors import PublicationError
from wrapper.validation import ValidationReport, validate_bundle


Validator = Callable[[Path, Any], ValidationReport]


def publish_validated_bundle(
    *,
    staging_dir: Path,
    output_root: Path,
    dataset_name: str,
    resolved_config: Any,
    validator: Validator = validate_bundle,
    failed_root: Path | None = None,
) -> Path:
    try:
        validator(staging_dir, resolved_config)
    except Exception as error:
        if failed_root is not None:
            retain_failure(
                staging_dir=staging_dir,
                failed_root=failed_root,
                dataset_name=dataset_name,
                error=error,
                component="DatasetValidator",
                stage="validation",
            )
        raise

    output_root.mkdir(parents=True, exist_ok=True)
    final_path = output_root / dataset_name
    if final_path.exists():
        raise PublicationError(f"published dataset already exists: {dataset_name}")
    _ensure_same_filesystem_parent(staging_dir, output_root)
    staging_dir.replace(final_path)
    return final_path


def retain_failure(
    *,
    staging_dir: Path,
    failed_root: Path,
    dataset_name: str,
    error: BaseException,
    component: str,
    stage: str,
) -> Path:
    failed_root.mkdir(parents=True, exist_ok=True)
    failed_path = failed_root / dataset_name
    if failed_path.exists():
        raise PublicationError(f"failed bundle already exists: {dataset_name}")
    _ensure_same_filesystem_parent(staging_dir, failed_root)
    staging_dir.replace(failed_path)

    logs_dir = failed_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    traceback_path = logs_dir / "traceback.txt"
    traceback_path.write_text(
        "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        encoding="utf-8",
    )
    failure = {
        "status": "failed",
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "component": component,
        "stage": stage,
        "exception_class": type(error).__name__,
        "message": str(error),
        "staging_dir": _relative_name(failed_path),
        "traceback_path": "logs/traceback.txt",
    }
    (failed_path / "failure.json").write_text(
        json.dumps(failure, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return failed_path


def _ensure_same_filesystem_parent(source: Path, destination_parent: Path) -> None:
    source_anchor = source.resolve().anchor
    destination_anchor = destination_parent.resolve().anchor
    if source_anchor.lower() != destination_anchor.lower():
        raise PublicationError("publication requires staging and target on the same filesystem")


def _relative_name(path: Path) -> str:
    return path.name
