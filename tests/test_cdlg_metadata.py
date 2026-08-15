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


def test_given_real_flat_cdlg_metadata_with_independent_drift_before_trees_when_parsed_then_versions_follow_ordered_afters(tmp_path):
    raw_xes = tmp_path / "raw.xes"
    raw_xes.write_text(
        """<?xml version="1.0" encoding="UTF-8" ?>
<log xmlns="http://www.xes-standard.org/">
  <trace /><trace /><trace /><trace /><trace /><trace /><trace /><trace /><trace />
</log>
""",
        encoding="utf-8",
    )
    drift_csv = tmp_path / "drift_info.csv"
    drift_csv.write_text(
        "\n".join(
            [
                "log_name;drift_or_noise_id;drift_attribute;drift_sub_attribute;value",
                "log.xes;drift_1;change_info_1;change_trace_index;[4]",
                "log.xes;drift_1;change_info_1;process_tree_before;->( 'a', 'b' )",
                "log.xes;drift_1;change_info_1;process_tree_after;->( 'a', *tau* )",
                "log.xes;drift_2;change_info_1;change_trace_index;[7]",
                "log.xes;drift_2;change_info_1;process_tree_before;->( 'a', 'b' )",
                "log.xes;drift_2;change_info_1;process_tree_after;->( 'a', 'Random activity 1' )",
                "",
            ]
        ),
        encoding="utf-8",
    )

    metadata = parse_raw_metadata(
        raw_xes_path=raw_xes,
        drift_csv_path=drift_csv,
        expected_version_ids=("v1", "v2", "v3"),
    )

    assert [snapshot.process_tree for snapshot in metadata.snapshots] == [
        "->( 'a', 'b' )",
        "->( 'a', *tau* )",
        "->( 'a', 'Random activity 1' )",
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
