from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


def should_run_bpm_prediction_compatibility(env: os._Environ[str] | dict[str, str]) -> bool:
    return env.get("CDLGW_RUN_BPM_COMPAT") == "1"


@pytest.mark.integration
@pytest.mark.skipif(
    not should_run_bpm_prediction_compatibility(os.environ),
    reason="set CDLGW_RUN_BPM_COMPAT=1",
)
def test_published_bundle_is_accepted_by_bpm_prediction_xes_and_bpmn_ingestion(tmp_path):
    bundle = _required_path_env("CDLGW_BUNDLE_PATH")
    downstream_root = _required_path_env("BPM_PREDICTION_ROOT")
    downstream_python = _required_path_env("BPM_PREDICTION_PYTHON")

    xes_summary = _run_downstream_ingest(
        bundle=bundle,
        downstream_root=downstream_root,
        downstream_python=downstream_python,
        config_path=bundle / "configs/bpm_prediction_xes.yaml",
        out_path=tmp_path / "xes_summary.json",
    )
    bpmn_summary = _run_downstream_ingest(
        bundle=bundle,
        downstream_root=downstream_root,
        downstream_python=downstream_python,
        config_path=bundle / "configs/bpm_prediction_bpmn.yaml",
        out_path=tmp_path / "bpmn_summary.json",
    )

    assert xes_summary["status"] == "ok"
    assert xes_summary["adapter"] == "xes"
    assert xes_summary["versions_saved"] == ["v1", "v2", "v3"]
    assert bpmn_summary["status"] == "ok"
    assert bpmn_summary["adapter"] == "camunda"
    assert bpmn_summary["structure_source"] == "bpmn"
    assert bpmn_summary["quarantined_procdefs"] == 0
    assert bpmn_summary["versions_saved"] == ["v1", "v2", "v3"]

    topology_report = json.loads((bundle / "reports/topology_alignment.json").read_text(encoding="utf-8"))
    assert topology_report["status"] == "passed"
    assert all(not payload["missing_in_bpmn"] for payload in topology_report["versions"].values())
    assert all(not payload["missing_in_xes"] for payload in topology_report["versions"].values())


def _run_downstream_ingest(
    *,
    bundle: Path,
    downstream_root: Path,
    downstream_python: Path,
    config_path: Path,
    out_path: Path,
) -> dict:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(downstream_root)
    result = subprocess.run(
        [
            str(downstream_python),
            str(downstream_root / "tools/ingest_topology.py"),
            "--config",
            str(config_path),
            "--split",
            "full",
            "--out",
            str(out_path),
        ],
        cwd=bundle,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(out_path.read_text(encoding="utf-8"))


def _required_path_env(name: str) -> Path:
    value = os.environ.get(name)
    if not value:
        raise AssertionError(f"{name} must be set for CDLGW integration tests")
    path = Path(value)
    assert path.exists(), f"{name} does not exist: {path}"
    return path
