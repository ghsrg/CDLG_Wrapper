from pathlib import Path

import pytest

from wrapper.cdlg_metadata import parse_raw_metadata
from wrapper.errors import ArtifactError


FIXTURE_DIR = Path(__file__).parent / "fixtures/cdlg_metadata"


def test_given_valid_raw_metadata_when_parsed_then_ordered_snapshots_and_boundaries_are_returned():
    metadata = parse_raw_metadata(
        raw_xes_path=FIXTURE_DIR / "valid_five_versions.xes",
        drift_csv_path=FIXTURE_DIR / "valid_drift_info.csv",
        expected_version_ids=("v1", "v2", "v3", "v4", "v5"),
    )

    assert [snapshot.version_id for snapshot in metadata.snapshots] == ["v1", "v2", "v3", "v4", "v5"]
    assert [snapshot.process_tree for snapshot in metadata.snapshots] == [
        "->('A','B')",
        "->('A','C')",
        "->('A','D')",
        "->('B','D')",
        "->('C','D')",
    ]
    assert [(boundary.version_id, boundary.start_index, boundary.end_index) for boundary in metadata.boundaries] == [
        ("v1", 0, 3),
        ("v2", 4, 7),
        ("v3", 8, 11),
        ("v4", 12, 15),
        ("v5", 16, 19),
    ]


@pytest.mark.parametrize(
    ("fixture_name", "message"),
    [
        ("missing_tree_drift_info.csv", "process_tree"),
        ("duplicate_version_drift_info.csv", "duplicate"),
        ("ambiguous_boundary_drift_info.csv", "boundary"),
        ("malformed_tree_drift_info.csv", "process_tree"),
    ],
)
def test_given_invalid_metadata_when_parsed_then_artifact_error_identifies_component(fixture_name, message):
    with pytest.raises(ArtifactError, match=message):
        parse_raw_metadata(
            raw_xes_path=FIXTURE_DIR / "valid_five_versions.xes",
            drift_csv_path=FIXTURE_DIR / fixture_name,
            expected_version_ids=("v1", "v2", "v3", "v4", "v5"),
        )
