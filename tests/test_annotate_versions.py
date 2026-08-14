from pathlib import Path

from wrapper.annotate_versions import annotate_versions
from wrapper.cdlg_metadata import parse_raw_metadata
from wrapper.config import load_config


FIXTURE_DIR = Path(__file__).parent / "fixtures/cdlg_metadata"


def test_given_raw_blocks_when_annotated_then_exact_allocation_and_surplus_are_reported(tmp_path: Path):
    raw_xes_path = FIXTURE_DIR / "valid_five_versions.xes"
    metadata = parse_raw_metadata(
        raw_xes_path=raw_xes_path,
        drift_csv_path=FIXTURE_DIR / "valid_drift_info.csv",
        expected_version_ids=("v1", "v2", "v3", "v4", "v5"),
    )
    resolved = resolved_config_with_total_17(tmp_path)

    annotated = annotate_versions(raw_xes_path=raw_xes_path, metadata=metadata, resolved_config=resolved)

    assert [(report.version_id, report.retained_count, report.discarded_count) for report in annotated.reports] == [
        ("v1", 4, 0),
        ("v2", 4, 0),
        ("v3", 3, 1),
        ("v4", 3, 1),
        ("v5", 3, 1),
    ]
    assert [trace.attributes["concept:version"] for trace in annotated.traces] == (
        ["v1"] * 4 + ["v2"] * 4 + ["v3"] * 3 + ["v4"] * 3 + ["v5"] * 3
    )
    assert all(event.attributes["concept:version"] == trace.attributes["concept:version"] for trace in annotated.traces for event in trace.events)


def test_given_raw_xes_when_annotated_then_source_bytes_and_original_values_are_preserved(tmp_path: Path):
    raw_xes_path = FIXTURE_DIR / "valid_five_versions.xes"
    before = raw_xes_path.read_bytes()
    metadata = parse_raw_metadata(
        raw_xes_path=raw_xes_path,
        drift_csv_path=FIXTURE_DIR / "valid_drift_info.csv",
        expected_version_ids=("v1", "v2", "v3", "v4", "v5"),
    )

    annotated = annotate_versions(
        raw_xes_path=raw_xes_path,
        metadata=metadata,
        resolved_config=resolved_config_with_total_17(tmp_path),
    )

    assert raw_xes_path.read_bytes() == before
    assert annotated.traces[0].attributes["concept:name"] == "case-001"
    assert [event.attributes["concept:name"] for event in annotated.traces[0].events] == ["A"]
    assert [event.attributes["concept:name"] for event in annotated.traces[8].events] == ["A"]


def resolved_config_with_total_17(tmp_path: Path):
    path = tmp_path / "experiment.yaml"
    path.write_text("dataset:\n  total_traces: 17\n", encoding="utf-8")
    return load_config(path)
