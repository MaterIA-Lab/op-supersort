"""Build and run the registered FIDE ranking benchmark."""

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRIOR = HERE.with_name("key-correction-spans")
PROTOCOL = ROOT / "runs/2026-11-23-fide-rating-updates/protocol.md"
RUST_FLAGS = "--edition=2021 -C opt-level=3 -C target-cpu=znver3 -C codegen-units=1".split()
DELTA_COMMIT = "89322c7bfb8d5b28b179650d08249398cbe0a977"
DELTA_BLOB = "fcf9774fd5b3c6723f55aed0de873ee1c2b9c760"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def checked(command):
    return subprocess.check_output(command, encoding="utf-8")


def cpu_name():
    if platform.system() == "Windows":
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        ) as key:
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("model name"):
            return line.partition(":")[2].strip()
    return platform.processor()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixture", type=Path)
    parser.add_argument("geometry", type=Path)
    parser.add_argument("delta_source", type=Path)
    parser.add_argument("work", type=Path, help="build directory")
    parser.add_argument("output", type=Path, help="directory for verified timings and metadata")
    parser.add_argument("--cpu", type=int, default=8)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    timings = args.output / "raw.csv"
    metadata = args.output / "metadata.json"
    if timings.exists() or metadata.exists():
        raise SystemExit("measurement already exists in the output directory")

    geometry = json.loads(args.geometry.read_text(encoding="utf-8"))
    fixture_hash = sha256(args.fixture)
    if fixture_hash != geometry["fixture_sha256"] or geometry["shared_rows"] < 100_000:
        raise SystemExit("fixture differs from the input that passed the geometry check")
    delta_hash = checked(["git", "hash-object", "--no-filters", str(args.delta_source)]).strip()
    if delta_hash != DELTA_BLOB:
        raise SystemExit("unexpected DeltaSort source")

    compiler = checked(["rustc", "--version", "--verbose"]).splitlines()
    rlib = args.work / "libdeltasort.rlib"
    executable = (args.work / ("bench.exe" if platform.system() == "Windows" else "bench")).resolve()
    subprocess.run(["rustc", *RUST_FLAGS, "--crate-type=rlib", "--crate-name=deltasort",
                    str(args.delta_source), "-o", str(rlib)], check=True)
    subprocess.run(["rustc", *RUST_FLAGS, str(HERE / "bench.rs"), "--extern", f"deltasort={rlib}",
                    "-o", str(executable)], check=True)
    sources = [PROTOCOL, HERE / "bench.rs", HERE / "prepare.py", HERE / "run.py",
               PRIOR / "bench.rs", PRIOR / "sort.rs"]
    started = datetime.now(timezone.utc).isoformat()
    raw = checked([str(executable), str(args.fixture), str(geometry["minimum_unchanged_writes"]), str(args.cpu)])
    finished = datetime.now(timezone.utc).isoformat()
    samples = raw.splitlines()[1:]
    if len(samples) != 2 * 9 * (3 + 11) or not all(row.endswith(",true") for row in samples):
        raise RuntimeError("incomplete verified trials")
    with timings.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(raw)
    details = {
        "started_utc": started,
        "finished_utc": finished,
        "platform": platform.platform(),
        "processor": cpu_name(),
        "logical_cpu": args.cpu,
        "threads": 1,
        "compiler": compiler,
        "flags": RUST_FLAGS,
        "row_bytes": 128,
        "warmups": 3,
        "measured_rounds_per_state": 11,
        "delta_sort": {"commit": DELTA_COMMIT, "blob_sha1": delta_hash},
        "source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path) for path in sources},
        "fixture_sha256": fixture_hash,
        "geometry_sha256": sha256(args.geometry),
        "binary_sha256": sha256(executable),
        "raw_sha256": sha256(timings),
        "timing": "complete apply-and-sort call including all temporary allocations and frees",
        "model": "gpt-6.2-sol",
        "reasoning_setting": "not captured",
        "tokens": "not captured",
        "session_cost": "not captured",
        "external_compute_spend": 0,
    }
    with metadata.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(details, indent=2) + "\n")
    print(f"Verified all {len(samples)} calls")


if __name__ == "__main__":
    main()
