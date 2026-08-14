from pathlib import Path

import pytest

from wrapper.config import ConfigurationError, allocate_traces, load_config


def test_given_remainder_when_allocated_then_earliest_versions_receive_one_extra_trace():
    assert allocate_traces(total_traces=17, version_count=5) == (4, 4, 3, 3, 3)


def test_given_exact_division_when_allocated_then_each_version_receives_same_count():
    assert allocate_traces(total_traces=20, version_count=5) == (4, 4, 4, 4, 4)


@pytest.mark.parametrize("total, versions", [(0, 5), (4, 5), (10, 0)])
def test_given_impossible_allocation_when_allocated_then_configuration_error(total, versions):
    with pytest.raises(ConfigurationError):
        allocate_traces(total_traces=total, version_count=versions)


def test_given_resolved_config_when_total_has_remainder_then_cdlg_count_is_ceiling(tmp_path: Path):
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text(
        "dataset:\n  total_traces: 17\n  version_count: 5\n",
        encoding="utf-8",
    )

    resolved = load_config(config_path)

    assert resolved.trace_allocation == (4, 4, 3, 3, 3)
    assert resolved.cdlg_traces_per_version == 4
