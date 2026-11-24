"""Build and run the registered equal-key exception-mask screen."""

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
PROTOCOL = ROOT / "runs/2026-11-24-exception-mask-sort/protocol.md"
HIGHWAY = "a3f6f68fcc368e5e3025ca25805eabda9d8a456f"
FLAGS = "-O3 -march=znver3 -std=c++20 -DNDEBUG -Wall -Wextra -Wpedantic".split()
REFERENCES = ("row_vq", "row_radix", "rle_vq", "rle_radix")
CANDIDATES = ("mask_vq", "mask_radix")
METHODS = (*REFERENCES, *CANDIDATES)
PRIMARY = ((524288, "burst_eighth"), (2097152, "burst_eighth"))
CONTROLS = tuple((524288, shape) for shape in ("burst_clean", "burst_quarter", "uniform"))
SEEDS = {"development": (39281, 87407), "holdout": (135527, 219517)}
WARMUPS, ROUNDS = 2, 7


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def source_hashes():
    files = (PROTOCOL, HERE / "bench.cpp", Path(__file__).resolve())
    return {path.relative_to(ROOT).as_posix(): digest(path) for path in files}


def output(command):
    return subprocess.check_output(command, encoding="utf-8")


def host_processor():
    import winreg

    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                        r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
        return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()


def cases(stage):
    shapes = (*PRIMARY, *CONTROLS) if stage == "development" else PRIMARY
    return product(shapes, SEEDS[stage])


def build(executable, highway):
    if output(["git", "-C", str(highway), "rev-parse", "HEAD"]).strip() != HIGHWAY:
        raise SystemExit("unexpected Highway commit")
    subprocess.run(["git", "-C", str(highway), "diff", "--quiet", "HEAD", "--", "hwy"], check=True)
    subprocess.run(["g++", *FLAGS, "-isystem", str(highway), str(HERE / "bench.cpp"),
                    str(highway / "hwy/abort.cc"), "-o", str(executable)], cwd=executable.parent, check=True)
    log = output([str(executable), "--verify"])
    (executable.parent / "verification.txt").write_text(log, encoding="utf-8", newline="\n")
    print(log, end="", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=SEEDS)
    parser.add_argument("highway", type=Path)
    parser.add_argument("work", type=Path)
    parser.add_argument("--cpu", type=int, default=8)
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    raw = work / f"{args.stage}.csv"
    metadata = work / f"{args.stage}-metadata.json"
    if raw.exists() or metadata.exists():
        raise SystemExit("measurements already exist")

    executable = work / "bench.exe"
    sources = source_hashes()
    compiler = output(["g++", "--version"]).splitlines()[0]
    if args.stage == "development":
        build(executable, args.highway.resolve())
    else:
        prior = json.loads((work / "development-metadata.json").read_text(encoding="utf-8"))
        if (digest(executable) != prior["binary_sha256"] or sources != prior["source_sha256"]
                or compiler != prior["compiler"] or args.cpu != prior["logical_cpu"]):
            raise SystemExit("holdout requires the unchanged development build and affinity")

    count = 0
    lines = []
    start = datetime.now(timezone.utc)
    for (rows, shape), seed in cases(args.stage):
        data = output([str(executable), str(rows), shape, str(seed), str(args.cpu)])
        current = data.splitlines(keepends=True)
        if not lines:
            lines.append(current[0])
        samples = list(csv.DictReader(io.StringIO(data)))
        expected = set(product(METHODS, range(WARMUPS + ROUNDS)))
        actual = {(s["method"], int(s["round"])) for s in samples}
        if (current[0] != lines[0] or len(samples) != len(expected) or actual != expected
                or any(s["verified"] != "true" or int(s["total_ns"]) <= 0 for s in samples)):
            raise RuntimeError(f"incomplete or unverified case {rows} {shape} {seed}")
        count += len(samples)
        lines.extend(current[1:])
        print(f"{rows} {shape} seed {seed}: {len(samples)} calls verified", flush=True)
    finish = datetime.now(timezone.utc)
    with raw.open("x", encoding="utf-8", newline="\n") as handle:
        handle.writelines(lines)
    report = {
        "stage": args.stage,
        "started_utc": start.isoformat(),
        "finished_utc": finish.isoformat(),
        "cpu": host_processor(),
        "platform": platform.platform(),
        "logical_cpu": args.cpu,
        "threads": 1,
        "compiler": compiler,
        "flags": FLAGS,
        "highway_commit": HIGHWAY,
        "source_sha256": sources,
        "binary_sha256": digest(executable),
        "raw_sha256": digest(raw),
        "verified_calls": count,
        "warmups": WARMUPS,
        "measured_calls_per_method": ROUNDS,
        "model": "gpt-6.2-sol",
        "tokens": "not captured",
        "reasoning_setting": "not captured",
        "session_cost": "not captured",
        "external_compute_spend": 0,
    }
    with metadata.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")
    print(f"Verified {count} complete stable sorts", flush=True)


if __name__ == "__main__":
    main()
