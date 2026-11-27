"""Run the registered rolling argsort screen and reproduce its median comparisons."""

import argparse
import csv
import hashlib
import io
import json
import platform
import statistics
import subprocess
import winreg
from datetime import datetime, timezone
from itertools import product
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROTOCOL = ROOT / "runs/2026-11-27-rolling-rank-chunks/protocol.md"
HIGHWAY_COMMIT = "a3f6f68fcc368e5e3025ca25805eabda9d8a456f"
FLAGS = "-O3 -march=znver3 -std=c++20 -DNDEBUG -Wall -Wextra -Wpedantic".split()
WINDOWS, WARMUPS, ROUNDS = 131072, 2, 7
WIDTHS = (32, 64)
SEEDS = {"development": (83179, 152083), "holdout": (273289, 417841)}
REFERENCES = ("window_vq", "rolling_binary", "rolling_simd", "rolling_stream",
              "rolling_direct", "union_walk", "union_pack")
CANDIDATES = ("union_cache", "union_cache_stream")
METHODS = (*REFERENCES, *CANDIDATES)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def capture(command):
    return subprocess.check_output(command, encoding="utf-8")


def system_cpu():
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                        r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
        return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()


def build(executable, highway):
    if capture(["git", "-C", str(highway), "rev-parse", "HEAD"]).strip() != HIGHWAY_COMMIT:
        raise SystemExit("unexpected Highway commit")
    subprocess.run(["git", "-C", str(highway), "diff", "--quiet", "HEAD", "--", "hwy"], check=True)
    subprocess.run(["g++", *FLAGS, "-isystem", str(highway), str(HERE / "bench.cpp"),
                    str(highway / "hwy/abort.cc"), "-o", str(executable)],
                   cwd=executable.parent, check=True)
    log = capture([str(executable), "--verify"])
    (executable.parent / "verification.txt").write_text(log, encoding="utf-8", newline="\n")
    print(log, end="", flush=True)


def validate_case(samples, width, shape, seed):
    expected = set(product(METHODS, range(WARMUPS + ROUNDS)))
    actual = {(row["method"], int(row["round"])) for row in samples}
    order = {(int(row["round"]), int(row["order"])) for row in samples}
    if (len(samples) != len(expected) or actual != expected
            or order != set(product(range(WARMUPS + ROUNDS), range(len(METHODS))))
            or any((int(row["windows"]), int(row["width"]), row["shape"], int(row["seed"]))
                   != (WINDOWS, width, shape, seed) or row["verified"] != "true"
                   or int(row["total_ns"]) <= 0 for row in samples)):
        raise ValueError(f"incomplete or unverified case {width} {shape} {seed}")


def summarize(work, stage):
    raw = work / f"{stage}.csv"
    metadata = json.loads((work / f"{stage}-metadata.json").read_text(encoding="utf-8"))
    if digest(raw) != metadata["raw_sha256"]:
        raise ValueError("sample hash differs from metadata")
    with raw.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    widths = tuple(metadata["widths"])
    shapes = ("uniform", "keys16") if stage == "development" else ("uniform",)
    if len(rows) != len(widths) * len(shapes) * len(SEEDS[stage]) * len(METHODS) * (WARMUPS + ROUNDS):
        raise ValueError("unexpected sample count")
    scores = {width: dict.fromkeys(CANDIDATES, True) for width in widths}
    print("width,shape,seed,best_reference,reference_ms,cache_ms,stream_ms,cache_ratio,stream_ratio,union_pack_ms")
    for width, shape, seed in product(widths, shapes, SEEDS[stage]):
        samples = [row for row in rows if (int(row["width"]), row["shape"], int(row["seed"])) == (width, shape, seed)]
        validate_case(samples, width, shape, seed)
        medians = {method: statistics.median(int(row["total_ns"]) for row in samples
                                            if row["method"] == method and int(row["round"]) >= WARMUPS)
                   for method in METHODS}
        best = min(REFERENCES, key=medians.__getitem__)
        reference = medians[best]
        cache, stream = (medians[method] for method in CANDIDATES)
        print(f"{width},{shape},{seed},{best},{reference / 1e6:.3f},{cache / 1e6:.3f},"
              f"{stream / 1e6:.3f},{reference / cache:.3f},{reference / stream:.3f},"
              f"{medians['union_pack'] / 1e6:.3f}")
        if shape == "uniform":
            for method in CANDIDATES:
                scores[width][method] &= medians[method] * 100 <= reference * 77
    passing = {width: [method for method, passed in variants.items() if passed]
               for width, variants in scores.items()}
    print(f"Passing variants by width: {passing}", flush=True)
    return passing


def benchmark(work, stage, highway, cpu):
    work.mkdir(parents=True, exist_ok=True)
    raw = work / f"{stage}.csv"
    metadata = work / f"{stage}-metadata.json"
    if raw.exists() or metadata.exists():
        raise SystemExit("measurements already exist")

    executable = work / "bench.exe"
    sources = {path.relative_to(ROOT).as_posix(): digest(path)
               for path in (PROTOCOL, HERE / "bench.cpp", Path(__file__).resolve())}
    compiler = capture(["g++", "--version"]).splitlines()[0]
    if stage == "development":
        if highway is None:
            raise SystemExit("--highway is required to build the development benchmark")
        build(executable, highway.resolve())
        widths, shapes = WIDTHS, ("uniform", "keys16")
    else:
        development = json.loads((work / "development-metadata.json").read_text(encoding="utf-8"))
        if (digest(executable) != development["binary_sha256"] or sources != development["source_sha256"]
                or compiler != development["compiler"] or cpu != development["logical_cpu"]):
            raise SystemExit("holdout requires the unchanged build, compiler and affinity")
        widths = tuple(width for width, variants in summarize(work, "development").items() if variants)
        if not widths:
            raise SystemExit("the development run did not qualify for holdout")
        shapes = ("uniform",)

    header, samples = None, []
    started = datetime.now(timezone.utc)
    for width, shape, seed in product(widths, shapes, SEEDS[stage]):
        data = capture([str(executable), str(WINDOWS), str(width), shape, str(seed), str(cpu)])
        reader = csv.DictReader(io.StringIO(data))
        case = list(reader)
        if header is not None and header != reader.fieldnames:
            raise ValueError("CSV columns changed between cases")
        header = reader.fieldnames
        validate_case(case, width, shape, seed)
        samples.extend(case)
        print(f"Width {width}, {shape}, seed {seed}: {len(case)} verified calls", flush=True)
    finished = datetime.now(timezone.utc)

    with raw.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(samples)
    report = {
        "stage": stage, "started_utc": started.isoformat(), "finished_utc": finished.isoformat(),
        "cpu": system_cpu(), "platform": platform.platform(), "logical_cpu": cpu, "threads": 1,
        "compiler": compiler, "flags": FLAGS, "highway_commit": HIGHWAY_COMMIT,
        "widths": widths, "windows": WINDOWS, "source_sha256": sources,
        "binary_sha256": digest(executable), "raw_sha256": digest(raw), "verified_calls": len(samples),
        "warmups": WARMUPS, "measured_calls_per_method": ROUNDS, "model": "gpt-6.2-sol",
        "tokens": "not captured", "reasoning_setting": "not captured", "session_cost": "not captured",
        "external_compute_spend": 0,
    }
    with metadata.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    summarize(work, stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=SEEDS)
    parser.add_argument("work", type=Path)
    parser.add_argument("--highway", type=Path)
    parser.add_argument("--cpu", type=int, default=8)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    if args.report_only:
        summarize(args.work.resolve(), args.stage)
    else:
        benchmark(args.work.resolve(), args.stage, args.highway, args.cpu)


if __name__ == "__main__":
    main()
