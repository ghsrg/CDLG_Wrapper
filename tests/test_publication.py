from __future__ import annotations

import json
from pathlib import Path

import pytest

from wrapper.errors import PublicationError, ValidationError
from wrapper.publication import publish_validated_bundle, retain_failure
from wrapper.validation import ValidationReport


def test_given_valid_staging_when_published_then_bundle_is_atomically_promoted(tmp_path):
    staging = _staging(tmp_path)
    output_root = tmp_path / "published"

    final_path = publish_validated_bundle(
        staging_dir=staging,
        output_root=output_root,
        dataset_name="dataset_001",
        resolved_config={},
        validator=_passing_validator,
    )

    assert final_path == output_root / "dataset_001"
    assert final_path.joinpath("dataset.xes").read_text(encoding="utf-8") == "<log />"
    assert not staging.exists()


def test_given_existing_final_target_when_published_then_publication_refuses_overwrite(tmp_path):
    staging = _staging(tmp_path)
    output_root = tmp_path / "published"
    output_root.joinpath("dataset_001").mkdir(parents=True)

    with pytest.raises(PublicationError, match="already exists"):
        publish_validated_bundle(
            staging_dir=staging,
            output_root=output_root,
            dataset_name="dataset_001",
            resolved_config={},
            validator=_passing_validator,
        )

    assert staging.exists()
    assert output_root.joinpath("dataset_001").is_dir()


def test_given_invalid_staging_when_publication_attempted_then_failed_bundle_is_retained(tmp_path):
    staging = _staging(tmp_path)
    failed_root = tmp_path / "failed"

    with pytest.raises(ValidationError):
        publish_validated_bundle(
            staging_dir=staging,
            output_root=tmp_path / "published",
            dataset_name="dataset_001",
            resolved_config={},
            validator=_failing_validator,
            failed_root=failed_root,
        )

    retained = failed_root / "dataset_001"
    assert retained.joinpath("dataset.xes").is_file()
    failure = json.loads(retained.joinpath("failure.json").read_text(encoding="utf-8"))
    assert failure["status"] == "failed"
    assert failure["component"] == "DatasetValidator"
    assert failure["stage"] == "validation"
    assert not Path(failure["staging_dir"]).is_absolute()
    assert retained.joinpath("logs/traceback.txt").is_file()
    assert not staging.exists()


def test_given_error_when_failure_retained_then_paths_are_relative_and_existing_failed_target_is_not_overwritten(tmp_path):
    staging = _staging(tmp_path)
    failed_root = tmp_path / "failed"
    failed_root.joinpath("dataset_001").mkdir(parents=True)

    with pytest.raises(PublicationError, match="failed bundle already exists"):
        retain_failure(
            staging_dir=staging,
            failed_root=failed_root,
            dataset_name="dataset_001",
            error=RuntimeError("boom"),
            component="CLI",
            stage="unexpected",
        )

    assert staging.exists()


def _staging(tmp_path: Path) -> Path:
    staging = tmp_path / "work" / "staging"
    staging.mkdir(parents=True)
    staging.joinpath("dataset.xes").write_text("<log />", encoding="utf-8")
    return staging


def _passing_validator(staging_dir, resolved_config):
    return ValidationReport(trace_count=1, version_counts={"v1": 1}, warnings=())


def _failing_validator(staging_dir, resolved_config):
    raise ValidationError("invalid bundle")
