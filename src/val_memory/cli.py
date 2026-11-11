"""Local JSONL/SQLite CLI. Commands never download models or call remote APIs."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
from pathlib import Path
import sqlite3
import sys

from .benchmark import counterexamples, run_benchmark
from .core import Observation, VALConfig, VALMemory
from .planning import offline_plan
from .storage import RevisionConflict, SQLiteStore


def write_json_new(path, data):
    path = Path(path)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, allow_nan=False, indent=2)
        handle.write("\n")


def demo(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    config = VALConfig(("mathematics", "biology", "language", "spatial"), (0.05, 0.08, 0.90, 0.90))
    records = [
        Observation("m1", "Example: a graph has vertices and edges.", (1, 0, 0, 0), (0.9, 0.04, 0.03, 0.03), 0.65),
        Observation("b1", "Example: a metabolic network can be represented as a graph.", (0.9, 0.2, 0, 0), (0.48, 0.48, 0.02, 0.02), 0.60),
        Observation("s1", "Example: an unconfirmed weak association.", (0.95, 0.1, 0.1, 0), (0.9, 0.04, 0.03, 0.03), 0.05),
        Observation("l1", "Example: a peripheral language note.", (0, 0, 1, 0), (0.03, 0.03, 0.91, 0.03), 0.45),
    ]
    engine = VALMemory(config)
    decisions = [engine.observe(record) for record in records]
    revision = SQLiteStore(directory/"memory.sqlite").save(engine, expected_revision=0)
    write_json_new(directory/"config.json", asdict(config))
    with (directory/"observations.jsonl").open("x", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), ensure_ascii=False)+"\n")
    write_json_new(directory/"decisions.json", decisions)
    write_json_new(directory/"plan.json", offline_plan(engine))
    write_json_new(directory/"query.json", engine.query((1, 0, 0, 0), (0.5, 0.46, 0.02, 0.02), entropy=0.8))
    return dict(directory=str(directory), revision=revision, stats=engine.stats())


def parser():
    result = argparse.ArgumentParser(description="VAL 0.2.0 - research reference for domain-selective memory")
    sub = result.add_subparsers(dest="command", required=True)
    command = sub.add_parser("demo", help="create a new directory with a complete synthetic example")
    command.add_argument("--output", default="val_demo")
    command = sub.add_parser("ingest", help="create a NEW SQLite state from config and JSONL")
    command.add_argument("--config", required=True)
    command.add_argument("--input", required=True)
    command.add_argument("--state", required=True)
    for name in ("inspect", "query", "plan"):
        command = sub.add_parser(name)
        command.add_argument("--state", required=True)
        if name == "query":
            command.add_argument("--vector", required=True, help="JSON vector")
            command.add_argument("--routing", required=True, help="JSON domain probabilities")
            command.add_argument("--entropy", type=float)
            command.add_argument("--limit", type=int, default=5)
        if name == "plan":
            command.add_argument("--output", required=True)
    command = sub.add_parser("benchmark")
    command.add_argument("--seeds", type=int, default=8)
    command.add_argument("--observations", type=int, default=320)
    command.add_argument("--queries", type=int, default=48)
    command.add_argument("--capacity", type=int, default=64)
    command.add_argument("--shadow-capacity", type=int, default=64)
    command.add_argument("--output", required=True)
    command = sub.add_parser("audit", help="run numerical counterexamples to universal claims")
    command.add_argument("--output")
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "demo":
            result = demo(args.output)
        elif args.command == "ingest":
            if Path(args.state).exists():
                raise FileExistsError("state path already exists; choose a new path")
            config = VALConfig.from_dict(json.loads(Path(args.config).read_text(encoding="utf-8")))
            engine = VALMemory(config)
            with Path(args.input).open(encoding="utf-8") as handle:
                for line_number, line in enumerate(handle, 1):
                    if not line.strip():
                        continue
                    try:
                        engine.observe(Observation(**json.loads(line)))
                    except (ValueError, TypeError, KeyError) as exc:
                        raise ValueError(f"JSONL line {line_number}: {exc}") from exc
            # Save only after the entire input passes validation.
            path = Path(args.state)
            with path.open("xb"):
                pass
            try:
                revision = SQLiteStore(path).save(engine, expected_revision=0)
            except Exception:
                path.unlink(missing_ok=True)
                raise
            result = dict(revision=revision, stats=engine.stats())
        elif args.command == "benchmark":
            if Path(args.output).exists():
                raise FileExistsError(args.output)
            result = run_benchmark(seeds=args.seeds, observations=args.observations,
                                   queries=args.queries, capacity=args.capacity,
                                   shadow_capacity=args.shadow_capacity)
            write_json_new(args.output, result)
            result = dict(output=args.output, runs=len(result["rows"]), settings=result["settings"])
        elif args.command == "audit":
            result = counterexamples()
            if args.output:
                write_json_new(args.output, result)
        else:
            engine, revision = SQLiteStore(args.state).load()
            if args.command == "inspect":
                result = dict(revision=revision, stats=engine.stats())
            elif args.command == "query":
                result = engine.query(json.loads(args.vector), json.loads(args.routing),
                                      entropy=args.entropy, limit=args.limit)
            else:
                result = offline_plan(engine)
                write_json_new(args.output, result)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    except (ValueError, TypeError, OSError, KeyError, sqlite3.Error, RevisionConflict) as exc:
        print(f"val: {exc}", file=sys.stderr)
        return 2

