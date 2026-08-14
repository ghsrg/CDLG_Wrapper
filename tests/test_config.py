from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from wrapper.config import ConfigurationError, load_config


def test_given_minimal_config_when_loaded_then_first_experiment_defaults_resolve(tmp_path: Path):
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text("dataset:\n  total_traces: 1000\n", encoding="utf-8")

    resolved = load_config(config_path)

    assert resolved.dataset.total_traces == 1000
    assert resolved.dataset.version_count == 5
    assert resolved.dataset.version_ids == ("v1", "v2", "v3", "v4", "v5")
    assert resolved.cdlg.process_tree_complexity == "middle"
    assert resolved.cdlg.evolution_proportion == 0.2
    assert resolved.cdlg.drift_type == "sudden"
    assert resolved.cdlg.noise_enabled is False
    assert resolved.lifecycle.assign_enabled is False
    assert resolved.resources.pool_size == 3
    assert resolved.cdlg.checkout_path == Path("CDLG")


@pytest.mark.parametrize(
    "yaml_text",
    [
        "dataset:\n  total_traces: 0\n",
        "dataset:\n  total_traces: 100\n  version_count: 0\n",
        "cdlg:\n  process_tree_complexity: unsupported\ndataset:\n  total_traces: 100\n",
        "cdlg:\n  evolution_proportion: 0\ndataset:\n  total_traces: 100\n",
        "cdlg:\n  python_executable: '   '\ndataset:\n  total_traces: 100\n",
    ],
)
def test_given_invalid_override_when_loaded_then_configuration_error(tmp_path: Path, yaml_text: str):
    path = tmp_path / "invalid.yaml"
    path.write_text(yaml_text, encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_config(path)


def test_given_resolved_config_when_mutated_then_frozen_instance_error(tmp_path: Path):
    config_path = tmp_path / "experiment.yaml"
    config_path.write_text("dataset:\n  total_traces: 1000\n", encoding="utf-8")

    resolved = load_config(config_path)

    with pytest.raises(FrozenInstanceError):
        resolved.dataset.version_count = 3
