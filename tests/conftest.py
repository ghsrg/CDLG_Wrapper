from __future__ import annotations

import subprocess
from pathlib import Path

import pytest


UPSTREAM_URL = "https://gitlab.uni-mannheim.de/processanalytics/cdlg_tool"


def _run_git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def git_head(path: Path) -> str:
    return _run_git(path, "rev-parse", "HEAD")


def _write_minimal_checkout(path: Path) -> None:
    (path / "src/input_parameters").mkdir(parents=True)
    (path / "src/data_classes").mkdir(parents=True)
    (path / "LICENSE").write_text("GPL-3.0\n", encoding="utf-8")
    (path / "generate_collection_of_logs.py").write_text(
        "print('fake cdlg entrypoint')\n",
        encoding="utf-8",
    )
    (path / "src/input_parameters/default").write_text(
        "\n".join(
            [
                "Process_tree_complexity: simple, middle, complex",
                "Process_tree_evolution_proportion: 0.1-0.4",
                "Number_event_logs: 3",
                "Number_traces_per_process_model_version: 1000-3000",
                "Number_traces_for_gradual_change: 300-500",
                "Change_type: sudden, gradual",
                "Drift_types: sudden, gradual, incremental, recurring",
                "Number_drifts_per_log: 2-4",
                "Noise: False",
                "Noisy_trace_prob: 0.1-0.7",
                "Noisy_event_prob: 0.1-0.7",
                "Trace_exp_arrival_sec: 40000",
                "Task_exp_duration_sec: 500000",
                "Gradual_drift_type: linear, exponential",
                "Incremental_drift_number: 3-5",
                "Recurring_drift_number: 3-5",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


@pytest.fixture
def fake_cdlg_checkout(tmp_path: Path):
    def factory(defect: str | None = None) -> Path:
        checkout = tmp_path / f"cdlg-{defect or 'valid'}"
        checkout.mkdir()
        _write_minimal_checkout(checkout)
        _run_git(checkout, "init")
        _run_git(checkout, "config", "user.email", "test@example.com")
        _run_git(checkout, "config", "user.name", "Test User")
        _run_git(checkout, "remote", "add", "origin", UPSTREAM_URL)
        _run_git(checkout, "add", ".")
        _run_git(checkout, "commit", "-m", "initial")

        if defect == "wrong_origin":
            _run_git(checkout, "remote", "set-url", "origin", "https://example.invalid/cdlg")
        elif defect == "wrong_commit":
            (checkout / "extra.txt").write_text("extra\n", encoding="utf-8")
            _run_git(checkout, "add", ".")
            _run_git(checkout, "commit", "-m", "extra")
        elif defect == "dirty":
            (checkout / "generate_collection_of_logs.py").write_text(
                "print('dirty')\n",
                encoding="utf-8",
            )
        elif defect == "missing_license":
            (checkout / "LICENSE").unlink()
            _run_git(checkout, "add", "-A")
            _run_git(checkout, "commit", "-m", "remove license")
        elif defect == "wrong_license":
            (checkout / "LICENSE").write_text("MIT\n", encoding="utf-8")
            _run_git(checkout, "add", "-A")
            _run_git(checkout, "commit", "-m", "replace license")
        elif defect == "missing_entrypoint":
            (checkout / "generate_collection_of_logs.py").unlink()
            _run_git(checkout, "add", "-A")
            _run_git(checkout, "commit", "-m", "remove entrypoint")
        elif defect == "missing_parameter_template":
            (checkout / "src/input_parameters/default").unlink()
            _run_git(checkout, "add", "-A")
            _run_git(checkout, "commit", "-m", "remove parameter template")

        return checkout

    return factory
