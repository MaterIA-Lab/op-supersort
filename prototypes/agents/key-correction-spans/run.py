"""Measure the registered development or holdout matrix sequentially."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "runs/2026-11-23-key-correction-spans"
SOURCE = Path(__file__).resolve().parent
FLAGS = "--edition=2021 -C opt-level=3 -C target-cpu=znver3 -C codegen-units=1"
DELTA_COMMIT = "89322c7bfb8d5b28b179650d08249398cbe0a977"
DELTA_BLOB = "fcf9774fd5b3c6723f55aed0de873ee1c2b9c760"
DEVELOPMENT = [(1048576, 1024, "uniform"), (1048576, 32, "uniform"),
               (1048576, 1024, "local"), (4096, 16, "uniform")]
HOLDOUT = [(1048576, 1024, "uniform"), (2097152, 2048, "uniform")]
REPEATS = 7


def checked(command: list[str]) -> str:
    return subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cpu_model() -> str:
    if platform.system() == "Windows":
        import winreg

        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            return winreg.QueryValueEx(key, "ProcessorNameString")[0].strip()
    for line in Path("/proc/cpuinfo").read_text(encoding="utf-8").splitlines():
        if line.startswith("model name"):
            return line.partition(":")[2].strip()
    return platform.processor()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("development", "holdout"))
    parser.add_argument("binary", type=Path)
    parser.add_argument("delta_source", type=Path, help="the unchanged upstream lib.rs")
    parser.add_argument("--cpu", type=int, default=8)
    parser.add_argument("--output", type=Path, default=RUN)
    args = parser.parse_args()
    binary = args.binary.resolve()
    output = args.output
    output.mkdir(parents=True, exist_ok=True)
    raw = output / f"{args.stage}.csv"
    metadata_path = output / f"{args.stage}.json"
    if raw.exists() or metadata_path.exists():
        raise SystemExit(f"{args.stage} measurement exists in {output}")

    delta_blob = checked(["git", "hash-object", "--no-filters", str(args.delta_source)]).strip()
    if delta_blob != DELTA_BLOB:
        raise SystemExit(f"unexpected upstream DeltaSort source hash: {delta_blob}")

    source_paths = [SOURCE / name for name in ("bench.rs", "sort.rs", "run.py")]
    source_paths.append(RUN / "protocol.md")
    metadata = {
        "stage": args.stage,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "cpu_model": cpu_model(),
        "logical_cpu": args.cpu,
        "threads": 1,
        "compiler": checked(["rustc", "--version", "--verbose"]).splitlines(),
        "flags": FLAGS,
        "row_bytes": 128,
        "delta_sort": {"commit": DELTA_COMMIT, "blob_sha1": delta_blob},
        "source_sha256": {p.relative_to(ROOT).as_posix(): sha256(p) for p in source_paths},
        "binary_sha256": sha256(binary),
        "logical_writes": "unchanged rows written into the main array, excluding scratch and changed rows",
        "timing": "entire apply-and-sort call including scratch allocation and deallocation",
        "cache_state": "CLFLUSH and MFENCE outside timing above 4096 rows, no explicit flush otherwise",
        "model": "gpt-6.2-sol",
        "reasoning_setting": "not captured",
        "tokens": "not captured",
        "session_cost": "not captured",
        "external_compute_spend": 0,
    }
    if args.stage == "development":
        verification = checked([str(binary), "--verify"])
        (output / "verification.txt").write_text(verification, encoding="utf-8")
        jobs, seeds = DEVELOPMENT, (84731, 190027)
    else:
        jobs, seeds = HOLDOUT, (1000003, 16777259)

    rows = []
    header = None
    arguments = []
    for size, count, distribution in jobs:
        for seed in seeds:
            command = [str(binary), str(size), str(count), distribution,
                       str(seed), str(REPEATS), str(args.cpu)]
            result = checked(command).splitlines()
            if len(result) != 1 + 5 * (REPEATS + 1):
                raise RuntimeError(f"unexpected row count: {len(result)}")
            if header is not None and result[0] != header:
                raise RuntimeError("CSV header changed between cases")
            header = result[0]
            rows.extend(result[1:])
            arguments.append(command[1:])
            print(f"Verified {len(result) - 1} calls for {size} rows, {count} {distribution} edits, seed {seed}", flush=True)

    metadata["arguments"] = arguments
    metadata["finished_utc"] = datetime.now(timezone.utc).isoformat()
    with raw.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join([header, *rows]) + "\n")
    with metadata_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(metadata, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
