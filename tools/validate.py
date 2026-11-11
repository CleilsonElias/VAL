"""Rebuild the local validation record. Run from any directory with Python 3.11+."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--full-benchmark", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    validation = root / "validation"
    validation.mkdir(exist_ok=True)
    env = dict(os.environ, PYTHONPATH=str(root/"src"))
    records = []
    with tempfile.TemporaryDirectory() as directory:
        commands = [
            ["-m", "unittest", "discover", "-s", "tests", "-v"],
            ["-m", "val_memory", "demo", "--output", str(Path(directory)/"demo")],
            ["-m", "val_memory", "audit", "--output", str(Path(directory)/"counterexamples.json")],
        ]
        if args.full_benchmark:
            commands.append(["-m", "val_memory", "benchmark", "--output", str(Path(directory)/"benchmark.json")])
        for command in commands:
            result = subprocess.run([sys.executable, *command], cwd=root, env=env,
                                    capture_output=True, text=True)
            record = dict(command=["python", *command], exit_code=result.returncode,
                          stdout=result.stdout, stderr=result.stderr)
            records.append(record)
            if result.returncode:
                print(result.stdout, result.stderr)
                raise SystemExit(result.returncode)
        (validation/"counterexamples.json").write_bytes((Path(directory)/"counterexamples.json").read_bytes())
        if args.full_benchmark:
            (validation/"benchmark.json").write_bytes((Path(directory)/"benchmark.json").read_bytes())
    match = re.search(r"Ran (\d+) tests", records[0]["stderr"])
    count = int(match.group(1)) if match else None
    (validation/"tests.log").write_text(records[0]["stdout"]+records[0]["stderr"], encoding="utf-8")
    files = {}
    for name in ("benchmark.json", "counterexamples.json", "tests.log"):
        path = validation/name
        if path.exists():
            files[name] = dict(size_bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    report = dict(
        release="0.2.0", run_at_utc=datetime.now(timezone.utc).isoformat(),
        platform=platform.platform(), python=platform.python_version(),
        runtime_dependencies=[], test_count=count, tests_passed=True,
        full_benchmark_executed=args.full_benchmark, commands=records, files=files,
        not_executed=["Python 3.11/3.13 execution", "GitHub-hosted CI", "real LLM or encoder",
                      "LoRA training", "REM generation", "LLI-CAMS database integration",
                      "human or biological experiment", "learned intrinsic motivation"],
    )
    (validation/"validation.json").write_text(json.dumps(report, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(dict(tests=count, full_benchmark=args.full_benchmark, status="passed")))


if __name__ == "__main__":
    main()
