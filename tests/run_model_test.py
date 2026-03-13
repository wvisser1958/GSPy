#!/usr/bin/env python3
"""
Generic GSPy regression test runner for a model script or module.

Typical usage:
    python tests/run_model_test.py --project-root . --model-script tests/turbojet.py

What this script does
---------------------
1. Derives the test/model name from the model file or module name.
   Examples:
      tests/turbojet.py  -> turbojet
      tests/turbofan.py  -> turbofan
2. Creates/uses the directory structure:
      tests/
        input/<model_name>/
        output/<model_name>/
        validation/<model_name>/
   relative to a chosen project root.
3. Runs the user-provided model.
4. Expects the model to write <model_name>.csv to tests/output/<model_name>/.
5. Compares that output against tests/validation/<model_name>/<model_name>.csv.
6. If differences are found, interactively asks whether to reject or accept the new result.
7. If accepted, overwrites the validation CSV.
8. Appends a JSON log entry to tests/validation/<model_name>/test_log.json.

Model interface expected by this runner
---------------------------------------
The model should accept these CLI arguments:
    --input-dir <path>
    --output-dir <path>

The model should then write its CSV output to:
    <output-dir>/<model_name>.csv

For example, turbojet.py should write:
    tests/output/turbojet/turbojet.csv
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import difflib
import filecmp
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback
from typing import Any, Dict, List, Optional


LOG_NAME = "test_log.json"


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json_log(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return [
            {
                "timestamp": utc_now_iso(),
                "action": "warning",
                "message": f"Existing log at {path} was not a JSON list. New list started.",
            }
        ]
    except Exception as exc:
        return [
            {
                "timestamp": utc_now_iso(),
                "action": "warning",
                "message": f"Failed to read existing log at {path}: {exc}. New list started.",
            }
        ]


def write_json_log(path: Path, entries: List[Dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)


def append_log(path: Path, entry: Dict[str, Any]) -> None:
    entries = load_json_log(path)
    entries.append(entry)
    write_json_log(path, entries)


def read_csv_rows(path: Path) -> List[List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.reader(f))


def unified_csv_diff(reference_csv: Path, candidate_csv: Path, max_lines: int = 200) -> List[str]:
    ref_lines = [",".join(row) + "\n" for row in read_csv_rows(reference_csv)]
    cand_lines = [",".join(row) + "\n" for row in read_csv_rows(candidate_csv)]
    diff = list(
        difflib.unified_diff(
            ref_lines,
            cand_lines,
            fromfile=str(reference_csv),
            tofile=str(candidate_csv),
            lineterm="",
        )
    )
    if len(diff) > max_lines:
        diff = diff[:max_lines] + [f"\n... diff truncated after {max_lines} lines ..."]
    return diff


def compare_csv_files(reference_csv: Path, candidate_csv: Path) -> Dict[str, Any]:
    if not reference_csv.exists():
        return {
            "equal": False,
            "reason": "missing_reference",
            "diff": [f"Reference file does not exist: {reference_csv}"],
        }

    if filecmp.cmp(reference_csv, candidate_csv, shallow=False):
        return {
            "equal": True,
            "reason": "identical_bytes",
            "diff": [],
        }

    diff = unified_csv_diff(reference_csv, candidate_csv)
    return {
        "equal": False,
        "reason": "csv_diff",
        "diff": diff,
    }


def prompt_user_choice() -> str:
    prompt = (
        "\nDifferences were found. Choose an action:\n"
        "  [r] Reject new results\n"
        "  [a] Accept new results and overwrite validation CSV\n"
        "Enter choice (r/a): "
    )
    while True:
        choice = input(prompt).strip().lower()
        if choice in {"r", "reject"}:
            return "reject"
        if choice in {"a", "accept"}:
            return "accept"
        print("Invalid choice. Please enter 'r' or 'a'.")


def normalize_model_args(model_args: List[str]) -> List[str]:
    if model_args and model_args[0] == "--":
        return model_args[1:]
    return model_args


def discover_model_script_near_runner(runner_path: Path) -> Optional[Path]:
    candidates = [
        p for p in runner_path.parent.glob("*.py")
        if p.name not in {runner_path.name, "__init__.py"}
    ]
    if len(candidates) == 1:
        return candidates[0].resolve()
    return None


def derive_model_name(model_script: Optional[Path], model_module: Optional[str]) -> str:
    if model_script is not None:
        return model_script.stem
    if model_module:
        return model_module.split(".")[-1]
    auto_script = discover_model_script_near_runner(Path(__file__).resolve())
    if auto_script is not None:
        return auto_script.stem
    raise ValueError(
        "Could not determine model name. Provide --model-script or --model-module, or place a single model .py next to run_model_test.py."
    )


def ensure_test_structure(project_root: Path, model_name: str) -> Dict[str, Path]:
    tests_root = project_root / "tests"
    input_dir = tests_root / "input" / model_name
    output_dir = tests_root / "output" / model_name
    validation_dir = tests_root / "validation" / model_name

    for p in (tests_root, input_dir, output_dir, validation_dir):
        ensure_dir(p)

    csv_name = f"{model_name}.csv"
    return {
        "tests_root": tests_root,
        "input_dir": input_dir,
        "output_dir": output_dir,
        "validation_dir": validation_dir,
        "output_csv": output_dir / csv_name,
        "validation_csv": validation_dir / csv_name,
        "log_json": validation_dir / LOG_NAME,
    }


def resolve_model_script(args_model_script: Optional[Path]) -> Optional[Path]:
    if args_model_script is not None:
        return args_model_script.resolve()
    return discover_model_script_near_runner(Path(__file__).resolve())


def run_model(
    model_script: Optional[Path],
    model_module: Optional[str],
    project_root: Path,
    input_dir: Path,
    output_dir: Path,
    extra_args: List[str],
) -> subprocess.CompletedProcess[str]:
    if model_script is None and model_module is None:
        raise ValueError(
            "Provide either --model-script or --model-module, or place a single model .py next to run_model_test.py."
        )

    base_cmd = [sys.executable]
    if model_script is not None:
        cmd = base_cmd + [str(model_script)]
    else:
        cmd = base_cmd + ["-m", str(model_module)]

    cmd += [
        "--input-dir",
        str(input_dir),
        "--output-dir",
        str(output_dir),
    ]
    cmd += extra_args

    print("Running model:")
    print(" ".join(f'"{c}"' if " " in c else c for c in cmd))

    return subprocess.run(
        cmd,
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )


def build_log_entry(
    *,
    action: str,
    status: str,
    model_name: str,
    output_csv: Path,
    validation_csv: Path,
    comparison_reason: str,
    model_returncode: Optional[int],
    gspy_version: Optional[str],
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    entry: Dict[str, Any] = {
        "timestamp": utc_now_iso(),
        "model_name": model_name,
        "action": action,
        "status": status,
        "comparison_reason": comparison_reason,
        "model_returncode": model_returncode,
        "output_csv": str(output_csv),
        "validation_csv": str(validation_csv),
        "output_csv_exists": output_csv.exists(),
        "validation_csv_exists": validation_csv.exists(),
        "output_csv_sha256": sha256_of_file(output_csv) if output_csv.exists() else None,
        "validation_csv_sha256": sha256_of_file(validation_csv) if validation_csv.exists() else None,
        "gspy_version": gspy_version,
        "notes": notes,
        "user": os.environ.get("USERNAME") or os.environ.get("USER"),
        "platform": sys.platform,
        "python_version": sys.version.split()[0],
    }
    return entry


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run and validate a generic GSPy model regression test.")
    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Root of the GSPy project. Default: current working directory.",
    )
    parser.add_argument(
        "--model-script",
        type=Path,
        default=None,
        help="Path to the Python script that runs the model. If omitted, the runner tries to auto-discover a single .py model next to itself.",
    )
    parser.add_argument(
        "--model-module",
        default=None,
        help="Dotted Python module path to run with 'python -m'.",
    )
    parser.add_argument(
        "--gspy-version",
        default=None,
        help="GSPy version string to record when new validation data is accepted.",
    )
    parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Do not prompt; differences will cause the test to fail.",
    )
    parser.add_argument(
        "model_args",
        nargs=argparse.REMAINDER,
        help="Extra arguments forwarded to the model after '--'.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.resolve()
    model_script = resolve_model_script(args.model_script)
    model_module = args.model_module
    model_name = derive_model_name(model_script, model_module)
    extra_args = normalize_model_args(args.model_args)

    paths = ensure_test_structure(project_root, model_name)
    input_dir = paths["input_dir"]
    output_dir = paths["output_dir"]
    validation_dir = paths["validation_dir"]
    output_csv = paths["output_csv"]
    validation_csv = paths["validation_csv"]
    log_json = paths["log_json"]

    if model_script is not None and model_module is None and not model_script.exists():
        append_log(
            log_json,
            {
                "timestamp": utc_now_iso(),
                "model_name": model_name,
                "action": "model_script_missing",
                "status": "error",
                "message": f"Model script not found: {model_script}",
            },
        )
        print(f"Test failed: model script not found: {model_script}")
        return 2

    if output_csv.exists():
        output_csv.unlink()

    print(f"Project root     : {project_root}")
    print(f"Model name       : {model_name}")
    print(f"Model script     : {model_script if model_script is not None else '<module mode>'}")
    print(f"Input directory  : {input_dir}")
    print(f"Output directory : {output_dir}")
    print(f"Validation dir   : {validation_dir}")

    try:
        result = run_model(
            model_script=model_script,
            model_module=model_module,
            project_root=project_root,
            input_dir=input_dir,
            output_dir=output_dir,
            extra_args=extra_args,
        )
    except Exception as exc:
        append_log(
            log_json,
            {
                "timestamp": utc_now_iso(),
                "model_name": model_name,
                "action": "model_run_exception",
                "status": "error",
                "message": str(exc),
                "traceback": traceback.format_exc(),
            },
        )
        print("Model execution failed before subprocess launch:")
        print(exc)
        return 2

    print("\n=== Model stdout ===")
    print(result.stdout or "<empty>")
    print("=== Model stderr ===")
    print(result.stderr or "<empty>")

    if result.returncode != 0:
        append_log(
            log_json,
            build_log_entry(
                action="model_run",
                status="failed",
                model_name=model_name,
                output_csv=output_csv,
                validation_csv=validation_csv,
                comparison_reason="model_nonzero_exit",
                model_returncode=result.returncode,
                gspy_version=args.gspy_version,
                notes="Model returned a non-zero exit code.",
            ),
        )
        print(f"Test failed: model returned exit code {result.returncode}.")
        return result.returncode

    if not output_csv.exists():
        append_log(
            log_json,
            build_log_entry(
                action="model_run",
                status="failed",
                model_name=model_name,
                output_csv=output_csv,
                validation_csv=validation_csv,
                comparison_reason="missing_output_csv",
                model_returncode=result.returncode,
                gspy_version=args.gspy_version,
                notes="Model finished but did not produce the expected output CSV.",
            ),
        )
        print(f"Test failed: expected output CSV not found: {output_csv}")
        return 3

    comparison = compare_csv_files(validation_csv, output_csv)

    if comparison["equal"]:
        append_log(
            log_json,
            build_log_entry(
                action="comparison",
                status="passed",
                model_name=model_name,
                output_csv=output_csv,
                validation_csv=validation_csv,
                comparison_reason=comparison["reason"],
                model_returncode=result.returncode,
                gspy_version=args.gspy_version,
                notes="Output matches validation CSV.",
            ),
        )
        print("Test successful: no difference found between output and validation CSV.")
        return 0

    print("\nDifferences detected between generated output and validation data:\n")
    for line in comparison["diff"]:
        print(line)

    if args.non_interactive:
        append_log(
            log_json,
            build_log_entry(
                action="comparison",
                status="failed",
                model_name=model_name,
                output_csv=output_csv,
                validation_csv=validation_csv,
                comparison_reason=comparison["reason"],
                model_returncode=result.returncode,
                gspy_version=args.gspy_version,
                notes="Differences detected in non-interactive mode; validation not updated.",
            ),
        )
        print("Test failed: differences found (non-interactive mode, so nothing was overwritten).")
        return 1

    choice = prompt_user_choice()

    if choice == "reject":
        append_log(
            log_json,
            build_log_entry(
                action="reject_new_results",
                status="failed",
                model_name=model_name,
                output_csv=output_csv,
                validation_csv=validation_csv,
                comparison_reason=comparison["reason"],
                model_returncode=result.returncode,
                gspy_version=args.gspy_version,
                notes="User rejected the new generated CSV.",
            ),
        )
        print("Test rejected. Validation CSV was left unchanged.")
        return 1

    if not args.gspy_version:
        args.gspy_version = input("Enter the GSPy version to log for this accepted result: ").strip() or None

    shutil.copy2(output_csv, validation_csv)
    append_log(
        log_json,
        build_log_entry(
            action="accept_new_results",
            status="accepted",
            model_name=model_name,
            output_csv=output_csv,
            validation_csv=validation_csv,
            comparison_reason=comparison["reason"],
            model_returncode=result.returncode,
            gspy_version=args.gspy_version,
            notes="User accepted the new generated CSV and validation was updated.",
        ),
    )
    print("New results accepted. Validation CSV has been overwritten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
