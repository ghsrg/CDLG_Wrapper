from __future__ import annotations

import subprocess
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from wrapper.config import ResolvedConfig
from wrapper.errors import CdlgExecutionError


UPSTREAM_URL = "https://gitlab.uni-mannheim.de/processanalytics/cdlg_tool"
RUNTIME_IGNORE_NAMES = {
    ".git",
    ".venv",
    "venv",
    "env",
    ".idea",
    ".vscode",
    "__pycache__",
    "documentation",
}
PARAMETER_KEYS = {
    "Process_tree_complexity",
    "Process_tree_evolution_proportion",
    "Number_event_logs",
    "Number_traces_per_process_model_version",
    "Change_type",
    "Drift_types",
    "Number_drifts_per_log",
    "Noise",
}


@dataclass(frozen=True)
class CheckoutInfo:
    checkout_path: Path
    origin_url: str
    commit: str


@dataclass(frozen=True)
class CdlgRunResult:
    command: tuple[str, ...]
    exit_code: int
    elapsed_seconds: float
    stdout_path: Path
    stderr_path: Path
    raw_xes_path: Path
    raw_drift_csv_path: Path
    parameters_path: Path


def verify_checkout(checkout: Path, required_commit: str) -> CheckoutInfo:
    checkout = checkout.resolve()
    if not checkout.exists():
        raise CdlgExecutionError(f"CDLG checkout does not exist: {checkout}")

    origin_url = _git(checkout, "remote", "get-url", "origin")
    if origin_url != UPSTREAM_URL:
        raise CdlgExecutionError("CDLG checkout origin URL does not match the pinned upstream")

    commit = _git(checkout, "rev-parse", "HEAD")
    if commit != required_commit:
        raise CdlgExecutionError("CDLG checkout commit does not match the required pinned commit")

    status = _git(checkout, "status", "--porcelain")
    if status:
        raise CdlgExecutionError("CDLG checkout has tracked modifications")

    license_path = checkout / "LICENSE"
    required_files = [
        license_path,
        checkout / "generate_collection_of_logs.py",
        checkout / "src/input_parameters/default",
    ]
    for required_file in required_files:
        if not required_file.is_file():
            raise CdlgExecutionError(f"CDLG checkout is missing required file: {required_file.name}")
    license_text = license_path.read_text(encoding="utf-8", errors="ignore")
    if "GPL" not in license_text and "GNU GENERAL PUBLIC LICENSE" not in license_text:
        raise CdlgExecutionError("CDLG checkout license file does not identify GPL")

    return CheckoutInfo(
        checkout_path=checkout,
        origin_url=origin_url,
        commit=commit,
    )


def prepare_runtime_copy(checkout: Path, *, work_root: Path, run_id: str) -> Path:
    checkout = checkout.resolve()
    runtime = work_root / run_id / "cdlg-runtime"
    runtime_resolved = runtime.resolve()
    if _is_relative_to(runtime_resolved, checkout):
        raise CdlgExecutionError("CDLG runtime copy destination must not be inside checkout")
    if runtime.exists():
        raise CdlgExecutionError(f"CDLG runtime copy already exists: {runtime}")

    shutil.copytree(
        checkout,
        runtime,
        ignore=shutil.ignore_patterns(*RUNTIME_IGNORE_NAMES),
    )
    return runtime


def render_parameters(runtime_dir: Path, resolved_config: ResolvedConfig) -> Path:
    parameter_path = runtime_dir / "src/input_parameters/default"
    lines = parameter_path.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    rendered: list[str] = []
    replacements = _parameter_replacements(resolved_config)

    for line in lines:
        key, separator, value = line.partition(":")
        if not separator:
            rendered.append(line)
            continue
        key = key.strip()
        if key in seen:
            raise CdlgExecutionError(f"CDLG parameter template has duplicate key: {key}")
        seen.add(key)
        if key in replacements:
            rendered.append(f"{key}: {replacements[key]}")
        else:
            rendered.append(f"{key}: {value.strip()}")

    missing = PARAMETER_KEYS - seen
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise CdlgExecutionError(f"CDLG parameter template is missing required keys: {missing_list}")

    parameter_path.write_text("\n".join(rendered) + "\n", encoding="utf-8")
    return parameter_path


def run_cdlg(
    *,
    runtime_dir: Path,
    python_executable: Path,
    staging_raw_dir: Path,
) -> CdlgRunResult:
    runtime_dir = runtime_dir.resolve()
    if not python_executable.is_file():
        raise CdlgExecutionError(f"Python executable does not exist: {python_executable}")
    staging_raw_dir.mkdir(parents=True, exist_ok=True)
    logs_dir = staging_raw_dir.parent / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = logs_dir / "cdlg_stdout.log"
    stderr_path = logs_dir / "cdlg_stderr.log"
    launcher = _platform_launcher()
    command = _launcher_command(launcher, python_executable, runtime_dir)

    start = time.perf_counter()
    result = subprocess.run(
        [str(part) for part in command],
        check=False,
        capture_output=True,
        text=True,
    )
    elapsed = time.perf_counter() - start
    stdout_path.write_text(result.stdout, encoding="utf-8")
    stderr_path.write_text(result.stderr, encoding="utf-8")

    if result.returncode != 0:
        raise CdlgExecutionError(f"CDLG child process failed with exit code {result.returncode}")

    output_root = runtime_dir / "output"
    if not output_root.is_dir():
        raise CdlgExecutionError("CDLG output root is missing")

    xes_candidates = sorted(output_root.rglob("*.xes"))
    if len(xes_candidates) != 1:
        raise CdlgExecutionError("CDLG output must contain exactly one XES file")

    drift_candidates = sorted(output_root.rglob("drift_info.csv"))
    if len(drift_candidates) != 1:
        raise CdlgExecutionError("CDLG output must contain exactly one drift_info.csv")

    raw_xes_path = staging_raw_dir / "cdlg_output.xes"
    raw_drift_csv_path = staging_raw_dir / "drift_info.csv"
    parameters_path = staging_raw_dir / "cdlg_parameters.txt"
    shutil.copy2(xes_candidates[0], raw_xes_path)
    shutil.copy2(drift_candidates[0], raw_drift_csv_path)
    shutil.copy2(runtime_dir / "src/input_parameters/default", parameters_path)

    return CdlgRunResult(
        command=tuple(str(part) for part in command),
        exit_code=result.returncode,
        elapsed_seconds=elapsed,
        stdout_path=stdout_path,
        stderr_path=stderr_path,
        raw_xes_path=raw_xes_path,
        raw_drift_csv_path=raw_drift_csv_path,
        parameters_path=parameters_path,
    )


def _git(checkout: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(checkout), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise CdlgExecutionError(f"CDLG checkout git command failed: {' '.join(args)}")
    return result.stdout.strip()


def _parameter_replacements(resolved_config: ResolvedConfig) -> dict[str, str]:
    return {
        "Process_tree_complexity": resolved_config.cdlg.process_tree_complexity,
        "Process_tree_evolution_proportion": str(resolved_config.cdlg.evolution_proportion),
        "Number_event_logs": "1",
        "Number_traces_per_process_model_version": str(resolved_config.cdlg_traces_per_version),
        "Change_type": resolved_config.cdlg.drift_type,
        "Drift_types": resolved_config.cdlg.drift_type,
        "Number_drifts_per_log": str(resolved_config.dataset.version_count - 1),
        "Noise": str(resolved_config.cdlg.noise_enabled),
    }


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _platform_launcher() -> Path:
    project_root = Path(__file__).resolve().parents[1]
    if sys.platform.startswith("win"):
        return project_root / "scripts/run_cdlg.ps1"
    return project_root / "scripts/run_cdlg.sh"


def _launcher_command(launcher: Path, python_executable: Path, runtime_dir: Path) -> tuple[str | Path, ...]:
    if sys.platform.startswith("win"):
        return (
            "powershell",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            launcher,
            python_executable,
            runtime_dir,
        )
    return (launcher, python_executable, runtime_dir)
