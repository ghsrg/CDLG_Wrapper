from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Callable

from wrapper.config import ResolvedConfig, load_config
from wrapper.errors import CdlgExecutionError, exit_code_for


Pipeline = Callable[[Path, ResolvedConfig], Path]


def main(argv: list[str] | None = None, *, pipeline: Pipeline | None = None) -> int:
    parser = _parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return int(error.code)

    try:
        config_path = Path(args.config)
        resolved_config = load_config(config_path)
        published_path = (pipeline or run_generation_pipeline)(config_path, resolved_config)
    except Exception as error:
        code = exit_code_for(error)
        _print_error(error)
        return code

    print(published_path)
    return 0


def run_generation_pipeline(config_path: Path, resolved_config: ResolvedConfig) -> Path:
    raise CdlgExecutionError(
        "end-to-end external CDLG generation is reserved for CDLGW-006 compatibility execution"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate_benchmark",
        description="Generate a validated CDLG structural-drift benchmark dataset.",
    )
    parser.add_argument(
        "--config",
        required=True,
        help="Path to the wrapper YAML configuration.",
    )
    return parser


def _print_error(error: BaseException) -> None:
    error_type = type(error).__name__
    message = str(error)
    print(f"{error_type}: {message}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
