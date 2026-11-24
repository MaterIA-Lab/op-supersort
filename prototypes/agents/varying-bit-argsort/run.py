"""Build and run the registered varying-bit argsort screens."""

import argparse
import csv
import hashlib
import io
import json
import platform
import subprocess
from datetime import datetime, timezone
from itertools import product
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROTOCOL = ROOT / "runs/2026-11-24-varying-bit-argsort/protocol.md"
HIGHWAY_COMMIT = "a3f6f68fcc368e5e3025ca25805eabda9d8a456f"
PDQ_BLOB = "36360cd1d69d0bd6977d9ba2313b10612b889142"
FLAGS = "-O3 -march=znver3 -mavx2 -mbmi2 -DNDEBUG -std=c++20 -Wall -Wextra -Wpedantic".split()
METHODS = {"varying_bits", "field_ranges", "leading_prefix", "high_word_pairs", "pdqsort_indices"}
SHAPES = ((1048576, "composite"), (4194304, "composite"), (1048576, "morton"), (1048576, "uniform"))
SEEDS = {"development": (49331, 93817), "holdout": (155921, 229369)}


def capture(command):
    return subprocess.check_output(command, encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cpu_name():
    if platform.system() == "Windows":
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                            r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("model name"):
            return line.partition(":")[2].strip()
    return platform.processor()


def build(args, executable):
    highway = args.vendor / "highway"
    pdq = args.vendor / "pdqsort.h"
    if capture(["git", "-C", str(highway), "rev-parse", "HEAD"]).strip() != HIGHWAY_COMMIT:
        raise SystemExit("unexpected Highway version")
    if capture(["git", "hash-object", "--no-filters", str(pdq)]).strip() != PDQ_BLOB:
        raise SystemExit("unexpected pdqsort source")
    subprocess.run(["git", "-C", str(highway), "diff", "--quiet", "HEAD", "--", "hwy"], check=True)
    subprocess.run(["g++", *FLAGS, "-isystem", str(args.vendor), "-isystem", str(highway),
                    str(HERE / "bench.cpp"), str(highway / "hwy/abort.cc"), "-o", str(executable)], check=True)
    report = capture([str(executable), "--verify"])
    (executable.parent / "verification.txt").write_text(report, encoding="utf-8", newline="\n")
    print(report, end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=SEEDS)
    parser.add_argument("vendor", type=Path)
    parser.add_argument("work", type=Path)
    parser.add_argument("--cpu", type=int, default=8)
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    raw = work / f"{args.stage}.csv"
    info = work / f"{args.stage}-metadata.json"
    if raw.exists() or info.exists():
        raise SystemExit("measurements already exist")
    executable = work / ("bench.exe" if platform.system() == "Windows" else "bench")
    inputs = [PROTOCOL, HERE / "argsort.hpp", HERE / "bench.cpp", HERE / "run.py"]
    source_hashes = {path.relative_to(ROOT).as_posix(): sha256(path) for path in inputs}
    compiler = capture(["g++", "-dumpfullversion"]).strip()
    if args.stage == "development":
        build(args, executable)
    else:
        frozen = json.loads((work / "development-metadata.json").read_text(encoding="utf-8"))
        if (sha256(executable) != frozen["binary_sha256"]
                or source_hashes != frozen["source_sha256"] or compiler != frozen["compiler"]):
            raise SystemExit("holdout requires the unchanged development build")
    shapes = SHAPES if args.stage == "development" else SHAPES[:2]
    lines = []
    count = 0
    header = None
    start = datetime.now(timezone.utc)
    for (rows, shape), seed in product(shapes, SEEDS[args.stage]):
        data = capture([str(executable), str(rows), shape, str(seed), str(args.cpu)])
        records = csv.DictReader(io.StringIO(data))
        samples = list(records)
        keys = {(sample["method"], int(sample["round"])) for sample in samples}
        expected = set(product(METHODS, range(7)))
        if (keys != expected or len(samples) != len(expected)
                or any(sample["verified"] != "true" or int(sample["total_ns"]) <= 0 for sample in samples)):
            raise RuntimeError("incomplete or unverified result")
        fields = data.splitlines(keepends=True)
        if header is None:
            header = fields[0]
            lines.append(header)
        if fields[0] != header:
            raise RuntimeError("unexpected result columns")
        lines.extend(fields[1:])
        count += len(samples)
        print(f"{rows} {shape} seed {seed}: {len(samples)} calls verified", flush=True)
    finish = datetime.now(timezone.utc)
    with raw.open("x", encoding="utf-8", newline="\n") as stream:
        stream.writelines(lines)
    metadata = {
        "stage": args.stage,
        "started_utc": start.isoformat(),
        "finished_utc": finish.isoformat(),
        "cpu": cpu_name(),
        "platform": platform.platform(),
        "logical_cpu": args.cpu,
        "threads": 1,
        "compiler": compiler,
        "flags": FLAGS,
        "highway_commit": HIGHWAY_COMMIT,
        "pdqsort_blob": PDQ_BLOB,
        "source_sha256": source_hashes,
        "binary_sha256": sha256(executable),
        "raw_sha256": sha256(raw),
        "verified_calls": count,
        "warmups": 2,
        "measured_calls_per_method": 5,
        "model": "gpt-6.2-sol",
        "tokens": "not captured",
        "reasoning_setting": "not captured",
        "session_cost": "not captured",
        "external_compute_spend": 0,
    }
    with info.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(metadata, stream, indent=2)
        stream.write("\n")
    print(f"Verified {count} complete index builds", flush=True)


if __name__ == "__main__":
    main()
