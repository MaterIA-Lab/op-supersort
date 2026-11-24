"""Build and run the registered stable two-run merge probe on Windows."""

import argparse
import csv
import hashlib
import io
import json
import platform
import shutil
import subprocess
from datetime import datetime, timezone
from itertools import product
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROTOCOL = ROOT / "runs/2026-11-24-rank-window-merge/protocol.md"
SOURCE = HERE / "bench.cpp"
FLAGS = ["-std=c++20", "-O3", "-march=znver3", "-DNDEBUG", "-Wall", "-Wextra"]
REFERENCES = ("branchy", "branchless", "branchless_stream", "gallop", "tag_network", "tag_network_stream")
CANDIDATES = ("rank_cached", "rank_stream")
REPLAYS = ("replay_cached", "replay_stream")
METHODS = (*REFERENCES, *CANDIDATES, *REPLAYS)
PRIMARY = ((262144, "uniform"), (1048576, "uniform"))
CONTROL = (262144, "alternate")
SEEDS = {"development": (25771, 63487), "holdout": (90647, 125789)}
WARMUPS = 2
MEASURED = 7


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_hashes():
    return {path.relative_to(ROOT).as_posix(): digest(path)
            for path in (PROTOCOL, SOURCE, Path(__file__).resolve())}


def output(command):
    return subprocess.check_output(command, encoding="utf-8")


def host_processor():
    import winreg

    path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
        return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()


def cases(stage):
    shapes = (*PRIMARY, CONTROL) if stage == "development" else PRIMARY
    return product(shapes, SEEDS[stage])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=SEEDS)
    parser.add_argument("work", type=Path)
    parser.add_argument("--cpu", type=int, default=8)
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    raw = work / f"{args.stage}.csv"
    metadata = work / f"{args.stage}-metadata.json"
    if raw.exists() or metadata.exists():
        raise SystemExit("measurements already exist")

    compiler = shutil.which("g++")
    if not compiler:
        raise SystemExit("could not find g++ on PATH")
    executable = work / "bench.exe"
    sources = source_hashes()
    if args.stage == "development":
        subprocess.run([compiler, *FLAGS, str(SOURCE), "-o", str(executable)], cwd=work, check=True)
        verification = output([str(executable), "--verify"])
        (work / "verification.txt").write_text(verification, encoding="utf-8", newline="\n")
        print(verification, end="", flush=True)
    else:
        development = json.loads((work / "development-metadata.json").read_text(encoding="utf-8"))
        if digest(executable) != development["binary_sha256"] or sources != development["source_sha256"]:
            raise SystemExit("holdout requires the unchanged development build")

    lines = []
    count = 0
    started = datetime.now(timezone.utc)
    for (rows, shape), seed in cases(args.stage):
        result = output([str(executable), str(rows), shape, str(seed), str(args.cpu)])
        current = result.splitlines(keepends=True)
        if not lines:
            lines.append(current[0])
        samples = list(csv.DictReader(io.StringIO(result)))
        expected = set(product(METHODS, range(WARMUPS + MEASURED)))
        observed = {(s["method"], int(s["round"])) for s in samples}
        if (current[0] != lines[0] or len(samples) != len(expected) or observed != expected
                or any(s["verified"] != "true" or int(s["ns"]) <= 0 for s in samples)):
            raise RuntimeError(f"incomplete or unverified case {rows} {shape} {seed}")
        count += len(samples)
        lines.extend(current[1:])
        print(f"{rows} {shape} seed {seed}: {len(samples)} calls verified", flush=True)
    finished = datetime.now(timezone.utc)
    with raw.open("x", encoding="utf-8", newline="\n") as handle:
        handle.writelines(lines)

    data = {
        "stage": args.stage,
        "started_utc": started.isoformat(),
        "finished_utc": finished.isoformat(),
        "host_processor": host_processor(),
        "platform": platform.platform(),
        "logical_cpu": args.cpu,
        "threads": 1,
        "compiler": output([compiler, "--version"]).splitlines()[0],
        "flags": FLAGS,
        "source_sha256": sources,
        "binary_sha256": digest(executable),
        "raw_sha256": digest(raw),
        "verified_calls": count,
        "warmups": WARMUPS,
        "measured_calls_per_method": MEASURED,
        "model": "gpt-6.2-sol",
        "reasoning_setting": "not captured",
        "tokens": "not captured",
        "session_cost": "not captured",
        "external_compute_spend": 0,
    }
    with metadata.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, indent=2)
        handle.write("\n")
    print(f"Verified {count} complete stable merges", flush=True)


if __name__ == "__main__":
    main()
