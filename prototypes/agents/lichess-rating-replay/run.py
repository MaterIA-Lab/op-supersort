"""Run the registered Lichess replay with the shared rating benchmark."""

import argparse
import csv
import gzip
import io
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from prepare import sha256, windows


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FIDE = HERE.with_name("fide-rating-updates")
PRIOR = HERE.with_name("key-correction-spans")
PROTOCOL = ROOT / "runs/2026-11-23-lichess-rating-replay/protocol.md"
RUST_FLAGS = "--edition=2021 -C opt-level=3 -C target-cpu=znver3 -C codegen-units=1".split()
DELTA_COMMIT = "89322c7bfb8d5b28b179650d08249398cbe0a977"
DELTA_BLOB = "fcf9774fd5b3c6723f55aed0de873ee1c2b9c760"
SORT_BLOB = "620f2088acb104fe6fb19189339432cedbdf6abf"
MINIMUM_ROWS = 10_000
WARMUPS = 3
MEASURED = 11
FIELDS = ("rows", "edits", "interval_rows", "cache", "round", "method", "total_ns",
          "unchanged_rows_written", "verified")


def output(command):
    return subprocess.check_output(command, encoding="utf-8")


def blob_hash(path):
    return output(["git", "hash-object", "--no-filters", str(path)]).strip()


def cpu_name():
    if platform.system() == "Windows":
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        ) as key:
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    return platform.processor()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("work", type=Path, help="directory containing the prepared fixtures and geometry")
    parser.add_argument("delta_source", type=Path)
    parser.add_argument("--cpu", default=8, type=int)
    args = parser.parse_args()
    work = args.work.resolve()
    geometry_path = work / "geometry.json"
    raw_path = work / "raw.csv.gz"
    metadata_path = work / "metadata.json"
    if raw_path.exists() or metadata_path.exists():
        raise SystemExit("measurements already exist in the work directory")
    geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
    if geometry["extraction_counts"]["roster"] < MINIMUM_ROWS:
        raise SystemExit("the roster did not pass the preregistered minimum size")
    if [(cell["label"], cell["seconds"]) for cell in geometry["windows"]] != [
        (label, width) for label, _, width in windows()
    ]:
        raise SystemExit("geometry does not match the registered schedule")
    if blob_hash(args.delta_source) != DELTA_BLOB or blob_hash(PRIOR / "sort.rs") != SORT_BLOB:
        raise SystemExit("unexpected DeltaSort or direct-span source")
    compiler = output(["rustc", "--version", "--verbose"]).splitlines()
    rlib = work / "libdeltasort.rlib"
    executable = work / ("bench.exe" if platform.system() == "Windows" else "bench")
    subprocess.run(["rustc", *RUST_FLAGS, "--crate-type=rlib", "--crate-name=deltasort",
                    str(args.delta_source), "-o", str(rlib)], check=True)
    subprocess.run(["rustc", *RUST_FLAGS, str(FIDE / "bench.rs"), "--extern", f"deltasort={rlib}",
                    "-o", str(executable)], check=True)

    combined = io.StringIO(newline="")
    writer = csv.DictWriter(combined, fieldnames=("window", *FIELDS), lineterminator="\n")
    writer.writeheader()
    count = 0
    started = datetime.now(timezone.utc)
    for index, cell in enumerate(geometry["windows"]):
        fixture = work / "fixtures" / f"{index:02d}.csv"
        if sha256(fixture) != cell["fixture_sha256"]:
            raise RuntimeError(f"fixture hash mismatch for {cell['label']}")
        if cell["edits"] == 0:
            continue
        recorded = output([str(executable), str(fixture), str(cell["minimum_unchanged_writes"]),
                           str(args.cpu), str(MINIMUM_ROWS)])
        reader = csv.DictReader(io.StringIO(recorded))
        samples = list(reader)
        if tuple(reader.fieldnames or ()) != FIELDS or len(samples) != 2 * 9 * (WARMUPS + MEASURED):
            raise RuntimeError(f"unexpected sample matrix for {cell['label']}")
        for sample in samples:
            if (sample["verified"] != "true" or int(sample["edits"]) != cell["edits"]
                    or int(sample["interval_rows"]) != cell["affected_interval_rows"]):
                raise RuntimeError(f"unverified sample or geometry mismatch for {cell['label']}")
            writer.writerow({"window": cell["label"], **sample})
        count += len(samples)
        print(f"{cell['label']} verified {len(samples)} calls", flush=True)
    finished = datetime.now(timezone.utc)
    with raw_path.open("xb") as stream:
        stream.write(gzip.compress(combined.getvalue().encode("ascii"), mtime=0))
    sources = [PROTOCOL, HERE / "prepare.py", HERE / "run.py", FIDE / "bench.rs",
               PRIOR / "bench.rs", PRIOR / "sort.rs"]
    details = {
        "started_utc": started.isoformat(),
        "finished_utc": finished.isoformat(),
        "platform": platform.platform(),
        "processor": cpu_name(),
        "logical_cpu": args.cpu,
        "threads": 1,
        "compiler": compiler,
        "flags": RUST_FLAGS,
        "row_bytes": 128,
        "warmups": WARMUPS,
        "measured_rounds_per_state": MEASURED,
        "delta_sort": {"commit": DELTA_COMMIT, "blob_sha1": delta_hash},
        "source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path) for path in sources},
        "geometry_sha256": sha256(geometry_path),
        "binary_sha256": sha256(executable),
        "raw_gzip_sha256": sha256(raw_path),
        "verified_calls": count,
        "timing": "complete apply-and-sort call including all temporary allocations and frees",
        "model": "gpt-6.2-sol",
        "reasoning_setting": "not captured",
        "tokens": "not captured",
        "session_cost": "not captured",
        "external_compute_spend": 0,
    }
    with metadata_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(details, stream, indent=2)
        stream.write("\n")
    print(f"Verified {count} calls in total")


if __name__ == "__main__":
    main()
