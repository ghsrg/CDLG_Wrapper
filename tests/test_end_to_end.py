from __future__ import annotations

import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
import pytest

from wrapper.config import load_config
from wrapper.evidence import verify_checksums
from wrapper.validation import validate_bundle


XES_NS = {"xes": "http://www.xes-standard.org/"}


def should_run_real_cdlg_integration(env: os._Environ[str] | dict[str, str]) -> bool:
    return env.get("CDLGW_RUN_REAL_CDLG") == "1"


@pytest.mark.integration
@pytest.mark.skipif(not should_run_real_cdlg_integration(os.environ), reason="set CDLGW_RUN_REAL_CDLG=1")
def test_real_cdlg_smoke_cli_publishes_valid_bundle(tmp_path):
    repo_root = Path(__file__).resolve().parents[1]
    config_path = _smoke_config(tmp_path, repo_root)
    python_executable = repo_root / ".venv/Scripts/python.exe"
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root)

    result = subprocess.run(
        [str(python_executable), "-m", "wrapper.generate_benchmark", "--config", str(config_path)],
        cwd=tmp_path,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    published = Path(result.stdout.strip())
    assert published.is_dir()
    assert published.parent == tmp_path / "outputs/datasets"
    assert result.stderr == ""

    resolved = load_config(config_path)
    report = validate_bundle(published, resolved)
    assert report.trace_count == 9
    assert report.version_counts == {"v1": 3, "v2": 3, "v3": 3}
    assert len(list(published.glob("models/bpmn/*.bpmn"))) == 3
    assert len(list(published.glob("models/ptml/*.ptml"))) == 3
    assert len(list(published.glob("debug/xes_by_version/*.xes"))) == 3
    assert published.joinpath("raw/cdlg_output.xes").is_file()
    assert published.joinpath("raw/drift_info.csv").is_file()
    assert published.joinpath("raw/cdlg_parameters.txt").is_file()
    assert published.joinpath("logs/run.log").is_file()
    assert published.joinpath("reports/drift_metrics.json").is_file()
    assert published.joinpath("configs/bpm_prediction_xes.yaml").is_file()
    assert published.joinpath("configs/bpm_prediction_bpmn.yaml").is_file()
    assert verify_checksums(published / "checksums.sha256") is None
    assert len(ET.parse(published / "dataset.xes").getroot().findall("xes:trace", XES_NS)) == 9


def _smoke_config(tmp_path: Path, repo_root: Path) -> Path:
    source = yaml.safe_load((repo_root / "configs/cdlg_smoke.yaml").read_text(encoding="utf-8"))
    source["cdlg"]["checkout_path"] = str((repo_root / "CDLG").resolve())
    source["cdlg"]["python_executable"] = str((repo_root / ".venv/Scripts/python.exe").resolve())
    config_path = tmp_path / "cdlg_smoke.yaml"
    config_path.write_text(yaml.safe_dump(source, sort_keys=False), encoding="utf-8")
    return config_path
