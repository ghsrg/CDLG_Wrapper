from __future__ import annotations

from pathlib import Path

import pytest

from wrapper.errors import ArtifactError, CdlgExecutionError, ConfigurationError, PublicationError, ValidationError
from wrapper.generate_benchmark import main


def test_given_valid_config_when_cli_pipeline_succeeds_then_path_is_printed_and_exit_zero(tmp_path, capsys):
    config_path = _config(tmp_path)
    published_path = tmp_path / "outputs" / "dataset_001"

    exit_code = main(
        ["--config", str(config_path)],
        pipeline=lambda config_path, resolved_config: published_path,
    )

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out.strip() == str(published_path)
    assert captured.err == ""


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ConfigurationError("bad config"), 2),
        (CdlgExecutionError("cdlg failed"), 3),
        (ArtifactError("artifact failed"), 4),
        (ValidationError("invalid bundle"), 5),
        (PublicationError("cannot publish"), 6),
        (RuntimeError("unexpected"), 1),
    ],
)
def test_given_expected_pipeline_error_when_cli_runs_then_documented_exit_code_is_returned(
    tmp_path,
    capsys,
    error,
    expected,
):
    config_path = _config(tmp_path)

    def pipeline(config_path, resolved_config):
        raise error

    exit_code = main(["--config", str(config_path)], pipeline=pipeline)

    captured = capsys.readouterr()
    assert exit_code == expected
    assert type(error).__name__ in captured.err
    assert str(error) in captured.err
    assert captured.out == ""


def test_given_missing_config_when_cli_runs_then_configuration_exit_code_is_returned(tmp_path, capsys):
    missing_path = tmp_path / "missing.yaml"

    exit_code = main(["--config", str(missing_path)], pipeline=lambda *_: tmp_path)

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "ConfigurationError" in captured.err
    assert captured.out == ""


def test_given_no_config_argument_when_cli_runs_then_argparse_exit_code_is_returned(capsys):
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "--config" in captured.err


def _config(tmp_path: Path) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(
        "\n".join(
            [
                "dataset:",
                "  total_traces: 2",
                "  version_count: 2",
                "cdlg:",
                "  checkout_path: CDLG",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path
