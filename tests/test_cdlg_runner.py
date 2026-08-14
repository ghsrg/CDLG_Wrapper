import sys
from pathlib import Path

import pytest

from tests.conftest import git_head
from wrapper.cdlg_runner import prepare_runtime_copy, render_parameters, run_cdlg, verify_checkout
from wrapper.config import load_config
from wrapper.errors import CdlgExecutionError


def test_given_valid_checkout_when_verified_then_checkout_info_is_returned(fake_cdlg_checkout):
    checkout = fake_cdlg_checkout()

    info = verify_checkout(checkout, required_commit=git_head(checkout))

    assert info.checkout_path == checkout.resolve()
    assert info.commit == git_head(checkout)


@pytest.mark.parametrize(
    "defect",
    [
        "wrong_origin",
        "wrong_commit",
        "dirty",
        "missing_license",
        "wrong_license",
        "missing_entrypoint",
        "missing_parameter_template",
    ],
)
def test_given_invalid_checkout_when_verified_then_generation_is_rejected(fake_cdlg_checkout, defect):
    checkout = fake_cdlg_checkout(defect=defect)
    required_commit = "a" * 40 if defect == "wrong_commit" else git_head(checkout)

    with pytest.raises(CdlgExecutionError, match="checkout"):
        verify_checkout(checkout, required_commit=required_commit)


def test_given_verified_checkout_when_runtime_prepared_then_only_ignored_copy_changes(fake_cdlg_checkout, tmp_path):
    checkout = fake_cdlg_checkout()
    source_parameter = (checkout / "src/input_parameters/default").read_text(encoding="utf-8")

    runtime = prepare_runtime_copy(checkout, work_root=tmp_path / "work", run_id="run-001")
    render_parameters(runtime, resolved_config_with_total_17(tmp_path))

    assert runtime == tmp_path / "work/run-001/cdlg-runtime"
    assert (checkout / "src/input_parameters/default").read_text(encoding="utf-8") == source_parameter
    assert ".git" not in {path.name for path in runtime.iterdir()}


def test_given_runtime_and_resolved_config_when_parameters_rendered_then_only_approved_cdlg_keys_change(
    fake_cdlg_checkout,
    tmp_path,
):
    checkout = fake_cdlg_checkout()
    runtime = prepare_runtime_copy(checkout, work_root=tmp_path / "work", run_id="run-002")
    original_lines = _read_parameter_lines(runtime)

    render_parameters(runtime, resolved_config_with_total_17(tmp_path))

    rendered_lines = _read_parameter_lines(runtime)
    assert rendered_lines["Process_tree_complexity"] == "middle"
    assert rendered_lines["Process_tree_evolution_proportion"] == "0.2"
    assert rendered_lines["Number_event_logs"] == "1"
    assert rendered_lines["Number_traces_per_process_model_version"] == "4"
    assert rendered_lines["Change_type"] == "sudden"
    assert rendered_lines["Drift_types"] == "sudden"
    assert rendered_lines["Number_drifts_per_log"] == "4"
    assert rendered_lines["Noise"] == "False"

    changed_keys = {
        key for key, value in rendered_lines.items() if original_lines[key] != value
    }
    assert changed_keys == {
        "Process_tree_complexity",
        "Process_tree_evolution_proportion",
        "Number_event_logs",
        "Number_traces_per_process_model_version",
        "Change_type",
        "Drift_types",
        "Number_drifts_per_log",
    }


def test_given_one_raw_xes_and_drift_csv_when_child_succeeds_then_artifacts_are_copied(tmp_path):
    result = run_cdlg(
        runtime_dir=prepared_runtime(tmp_path, mode="success"),
        python_executable=Path(sys.executable),
        staging_raw_dir=tmp_path / "staging/raw",
    )

    assert result.exit_code == 0
    assert result.raw_xes_path.name == "cdlg_output.xes"
    assert result.raw_xes_path.read_text(encoding="utf-8") == "<log />\n"
    assert result.raw_drift_csv_path.name == "drift_info.csv"
    assert result.parameters_path.name == "cdlg_parameters.txt"
    assert result.stdout_path.read_text(encoding="utf-8")
    assert result.stderr_path.read_text(encoding="utf-8") == ""


@pytest.mark.parametrize("mode", ["nonzero", "no_xes", "multiple_xes", "missing_csv"])
def test_given_invalid_process_artifacts_when_collected_then_cdlg_execution_error(tmp_path, mode):
    with pytest.raises(CdlgExecutionError):
        run_cdlg(
            runtime_dir=prepared_runtime(tmp_path, mode=mode),
            python_executable=Path(sys.executable),
            staging_raw_dir=tmp_path / "staging/raw",
        )


def test_given_missing_python_executable_when_run_starts_then_generation_is_rejected(tmp_path):
    with pytest.raises(CdlgExecutionError, match="Python executable"):
        run_cdlg(
            runtime_dir=prepared_runtime(tmp_path, mode="success"),
            python_executable=tmp_path / "missing-python",
            staging_raw_dir=tmp_path / "staging/raw",
        )


def resolved_config_with_total_17(tmp_path):
    path = tmp_path / "experiment.yaml"
    path.write_text("dataset:\n  total_traces: 17\n", encoding="utf-8")
    return load_config(path)


def _read_parameter_lines(runtime):
    lines = (runtime / "src/input_parameters/default").read_text(encoding="utf-8").splitlines()
    return dict(line.split(": ", maxsplit=1) for line in lines)


def prepared_runtime(tmp_path, *, mode="success"):
    runtime = tmp_path / "runtime"
    (runtime / "src/input_parameters").mkdir(parents=True)
    (runtime / "src/input_parameters/default").write_text("Number_event_logs: 1\n", encoding="utf-8")
    (runtime / "generate_collection_of_logs.py").write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "import sys",
                f"mode = {mode!r}",
                "print('fake child stdout')",
                "if mode == 'nonzero':",
                "    print('fake child stderr', file=sys.stderr)",
                "    raise SystemExit(17)",
                "output = Path('output/default_123')",
                "output.mkdir(parents=True)",
                "if mode == 'success':",
                "    (output / 'log_1.xes').write_text('<log />\\n', encoding='utf-8')",
                "    (output / 'drift_info.csv').write_text('log_name;value\\n', encoding='utf-8')",
                "elif mode == 'no_xes':",
                "    (output / 'drift_info.csv').write_text('log_name;value\\n', encoding='utf-8')",
                "elif mode == 'multiple_xes':",
                "    (output / 'log_1.xes').write_text('<log />\\n', encoding='utf-8')",
                "    (output / 'log_2.xes').write_text('<log />\\n', encoding='utf-8')",
                "    (output / 'drift_info.csv').write_text('log_name;value\\n', encoding='utf-8')",
                "elif mode == 'missing_csv':",
                "    (output / 'log_1.xes').write_text('<log />\\n', encoding='utf-8')",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return runtime
