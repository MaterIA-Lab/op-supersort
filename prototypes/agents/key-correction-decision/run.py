"""Build and run the preregistered single-thread direct-span comparisons."""

import argparse
import csv
import gzip
import io
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from itertools import product
from pathlib import Path

from prepare_flights import digest


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PRIOR = HERE.with_name("key-correction-spans")
PROTOCOL = ROOT / "runs/2026-11-24-key-correction-decision/protocol.md"
SORT_BLOB = "620f2088acb104fe6fb19189339432cedbdf6abf"
DELTA_BLOB = "fcf9774fd5b3c6723f55aed0de873ee1c2b9c760"
DELTA_COMMIT = "89322c7bfb8d5b28b179650d08249398cbe0a977"
FLAGS = "--edition=2021 -C opt-level=3 -C target-cpu=znver3 -C codegen-units=1".split()
FIELDS = ("rows", "edits", "p50", "p95", "maximum", "interval", "minimum_writes", "mode",
          "cache", "round", "method", "total_ns", "writes", "plan_ns", "execute_ns", "verified")


def output(command):
    return subprocess.check_output(command, encoding="utf-8")


def blob(path):
    return output(["git", "hash-object", "--no-filters", str(path)]).strip()


def phase_source(source):
    body = "struct Batch {" + source.split("\nstruct Batch {", 1)[1].split("\npub fn bulk_esm_left(", 1)[0]
    swaps = [
        ("row.order_key()", "row_key(&row)"),
        ("|row| row.order_key() < key", "|row| row_key(row) < key"),
        ("pub fn direct_spans(rows: &mut [Row], edits: &[Edit]) -> usize {\n    if edits.is_empty() {\n        return 0;\n    }",
         "pub fn direct_spans_phases(rows: &mut [Row], edits: &[Edit]) -> (usize, u128, u128) {\n"
         "    let start = std::time::Instant::now();\n"
         "    if edits.is_empty() {\n        return (0, 0, 0);\n    }"),
        ("    let mut moved = 0;", "    let plan = start.elapsed().as_nanos();\n    let mut moved = 0;"),
        ("\n    moved\n}", "\n    (moved, plan, start.elapsed().as_nanos() - plan)\n}"),
    ]
    for before, after in swaps:
        if before not in body:
            raise ValueError("unexpected frozen source for the phase probe")
        body = body.replace(before, after, 1)
    return "use super::{key as row_key, Edit, Row};\n\n" + body


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


def cases(stage, work):
    if stage == "synthetic":
        for rows, distance, seed in product((32768, 262144, 1048576),
                                            ("short", "medium", "random"), (48781, 90271)):
            mib = rows * 128 // (1 << 20)
            yield f"{mib}MiB-{distance}-{seed}", ["synthetic", str(rows), distance, str(seed)]
        return
    observations = work / f"{stage}-observations.bin"
    for day, hour, width in product((9, 13), (7, 12, 17), (15, 60)):
        yield f"{stage}-{day:02d}-{hour:02d}00-{width}m", [
            "flights", str(observations), str(day * 1440 + hour * 60), str(width)
        ]


def build(work, upstream):
    frozen = PRIOR / "sort.rs"
    if blob(upstream) != DELTA_BLOB or blob(frozen) != SORT_BLOB:
        raise SystemExit("unexpected DeltaSort or direct-span source")
    phase = work / "phase.rs"
    phase.write_text(phase_source(frozen.read_text(encoding="utf-8")), encoding="utf-8", newline="\n")
    library = work / "libdeltasort.rlib"
    executable = work / ("bench.exe" if platform.system() == "Windows" else "bench")
    subprocess.run(["rustc", *FLAGS, "--crate-type=rlib", "--crate-name=deltasort",
                    str(upstream), "-o", str(library)], check=True)
    subprocess.run(["rustc", *FLAGS, str(HERE / "bench.rs"), "--extern", f"deltasort={library}",
                    "-o", str(executable)], env={**os.environ, "SUPERSORT_PHASE_RS": str(phase)}, check=True)
    verify = output([str(executable), "--verify"])
    (work / "verification.txt").write_text(verify, encoding="utf-8", newline="\n")
    print(verify, end="", flush=True)
    return executable, phase


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("synthetic", "january", "april"))
    parser.add_argument("work", type=Path)
    parser.add_argument("delta_source", type=Path)
    parser.add_argument("--cpu", default=8, type=int)
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    stage = args.stage
    raw = work / f"{stage}.csv.gz"
    metadata = work / f"{stage}-metadata.json"
    if raw.exists() or metadata.exists():
        raise SystemExit("stage has already been saved")
    source = None
    if stage != "synthetic":
        source = json.loads((work / f"{stage}-source.json").read_text(encoding="utf-8"))
        observations = work / f"{stage}-observations.bin"
        if (digest(observations) != source["observations_sha256"]
                or observations.stat().st_size != 8 * source["counts"]["roster_rows"]):
            raise RuntimeError("mismatched flight observations")
        if source["counts"]["roster_rows"] * 128 <= 32 * (1 << 20):
            raise SystemExit("the flight roster does not pass the preregistered minimum size")

    executable, phase = build(work, args.delta_source)
    compiler = output(["rustc", "-vV"]).splitlines()
    tmp = io.StringIO(newline="")
    writer = csv.DictWriter(tmp, fieldnames=("case", *FIELDS), lineterminator="\n")
    writer.writeheader()
    verified = 0
    starts = datetime.now(timezone.utc)
    for label, argv in cases(stage, work):
        records = csv.DictReader(io.StringIO(output([str(executable), *argv, str(args.cpu)])))
        rows = list(records)
        expected_calls = 2 * (11 if stage == "synthetic" else 2 * 12) * 7
        if tuple(records.fieldnames or ()) != FIELDS or len(rows) != expected_calls:
            raise ValueError(f"incomplete result for {label}")
        for sample in rows:
            if sample["verified"] != "true" or int(sample["total_ns"]) <= 0:
                raise ValueError(f"unverified result for {label}")
            if source and int(sample["rows"]) != source["counts"]["roster_rows"]:
                raise ValueError(f"flight roster mismatch in {label}")
            writer.writerow({"case": label, **sample})
        verified += len(rows)
        print(f"{label}: {rows[0]['edits']} edits, {len(rows)} calls verified", flush=True)
    finished = datetime.now(timezone.utc)
    with raw.open("xb") as handle:
        handle.write(gzip.compress(tmp.getvalue().encode("ascii"), mtime=0, compresslevel=9))
    inputs = [PROTOCOL, HERE / "bench.rs", HERE / "buffered.rs", HERE / "run.py",
              HERE / "prepare_flights.py", PRIOR / "sort.rs", PRIOR / "bench.rs"]
    record = {
        "stage": stage,
        "started_utc": starts.isoformat(),
        "finished_utc": finished.isoformat(),
        "platform": platform.platform(),
        "processor": cpu_name(),
        "logical_cpu": args.cpu,
        "threads": 1,
        "compiler": compiler,
        "flags": FLAGS,
        "timing": "complete sorting call including scratch; flight calls update the key-by-ID state",
        "row_bytes": 128,
        "warmups": 2,
        "repeats": 5,
        "delta_sort": {"commit": DELTA_COMMIT, "blob": DELTA_BLOB},
        "frozen_sort_blob": SORT_BLOB,
        "source_sha256": {path.relative_to(ROOT).as_posix(): digest(path) for path in inputs},
        "phase_source_sha256": digest(phase),
        "binary_sha256": digest(executable),
        "raw_gzip_sha256": digest(raw),
        "verified_calls": verified,
        "flight_source": source,
        "model": "gpt-6.2-sol",
        "tokens": "not captured",
        "reasoning_setting": "not captured",
        "session_cost": "not captured",
        "external_compute_spend": 0,
    }
    with metadata.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, indent=2)
        handle.write("\n")
    print(f"Verified {verified:,} calls in {stage}")


if __name__ == "__main__":
    main()
