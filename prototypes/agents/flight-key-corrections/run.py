"""Build and measure the preregistered flight replay on one logical CPU."""

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
FLIGHT_RUN = ROOT / "runs/2026-11-16-flight-overlap"
RUN = ROOT / "runs/2026-11-23-flight-key-corrections"
FROZEN = HERE.with_name("key-correction-spans")
FLAGS = "--edition=2021 -C opt-level=3 -C target-cpu=znver3 -C codegen-units=1".split()
DELTA_COMMIT = "89322c7bfb8d5b28b179650d08249398cbe0a977"
DELTA_BLOB = "fcf9774fd5b3c6723f55aed0de873ee1c2b9c760"
MONTHS = {1: "jan", 4: "apr", 7: "jul", 10: "oct"}

sys.path.insert(0, str(FLIGHT_RUN))
from flight_sample import DAY, YEAR_START, load_flights  # noqa: E402


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cpu_model():
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


def checked(command):
    return subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8").stdout


def first_week(month):
    first = date(2013, month, 1)
    monday = first + timedelta(days=(-first.weekday()) % 7)
    return [monday + timedelta(days=offset) for offset in range(7)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sample", type=Path, help="the pinned OpenIntro nycflights.rda")
    parser.add_argument("delta_source", type=Path, help="the unchanged DeltaSort lib.rs")
    parser.add_argument("work", type=Path, help="scratch directory for the build and replay input")
    parser.add_argument("output", type=Path, help="where to save the CSV and metadata files")
    parser.add_argument("--cpu", type=int, default=8)
    args = parser.parse_args()
    work = args.work.resolve()
    output = args.output.resolve()
    names = [*MONTHS.values(), "geometry"]
    if any((output / f"{name}.csv").exists() for name in names) or (output / "metadata.json").exists():
        raise SystemExit("a measurement already exists in the output directory")
    work.mkdir(parents=True, exist_ok=True)
    output.mkdir(parents=True, exist_ok=True)

    delta_blob = checked(["git", "hash-object", "--no-filters", str(args.delta_source)]).strip()
    if delta_blob != DELTA_BLOB:
        raise SystemExit(f"unexpected upstream DeltaSort source hash: {delta_blob}")
    flights, sample = load_flights(args.sample)
    if len(flights) != 32735 or sample["excluded"] != 0:
        raise SystemExit("unexpected pinned sample population")
    offset = 2 * DAY  # Preserve signed date order in the candidate's unsigned keys.
    input_path = work / "flights.csv"
    with input_path.open("w", encoding="utf-8", newline="\n") as stream:
        stream.write("id,scheduled,actual\n")
        for flight in flights:
            stream.write(f"{flight.row_number},{flight.scheduled + offset},{flight.actual + offset}\n")

    rlib = work / "libdeltasort.rlib"
    executable = work / ("replay.exe" if platform.system() == "Windows" else "replay")
    subprocess.run([
        "rustc", *FLAGS, "--crate-type=rlib", "--crate-name=deltasort",
        str(args.delta_source), "-o", str(rlib),
    ], check=True)
    subprocess.run([
        "rustc", *FLAGS, str(HERE / "bench.rs"), "--extern", f"deltasort={rlib}",
        "-o", str(executable),
    ], check=True)
    sources = [HERE / "bench.rs", HERE / "run.py", FLIGHT_RUN / "flight_sample.py",
               FROZEN / "sort.rs", FROZEN / "bench.rs", RUN / "protocol.md"]
    metadata = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "cpu_model": cpu_model(),
        "logical_cpu": args.cpu,
        "threads": 1,
        "compiler": checked(["rustc", "--version", "--verbose"]).splitlines(),
        "flags": FLAGS,
        "row_bytes": 128,
        "flights": sample,
        "replay_input_sha256": sha256(input_path),
        "replay_input_offset_minutes": offset,
        "delta_sort": {"commit": DELTA_COMMIT, "blob_sha1": delta_blob},
        "source_sha256": {path.relative_to(ROOT).as_posix(): sha256(path) for path in sources},
        "binary_sha256": sha256(executable),
        "cache_state": {"cold": "copy reset, CLFLUSH and MFENCE", "resident": "copy reset only"},
        "timing": "complete apply-and-sort call including scratch allocation and deallocation",
        "logical_writes": "unchanged rows written into the main array, excluding scratch and edited rows",
        "model": "gpt-6.2-sol",
        "reasoning_setting": "not captured",
        "tokens": "not captured",
        "session_cost": "not captured",
        "external_compute_spend": 0,
    }
    geometry_header = None
    geometry_rows = []
    output_files = {}
    all_days = []
    for month, name in MONTHS.items():
        days = first_week(month)
        all_days.extend(day.isoformat() for day in days)
        specifications = [f"{day.isoformat()}:{(day - YEAR_START).days * DAY + offset}" for day in days]
        geometry_path = work / f"geometry-{name}.csv"
        raw = checked([str(executable), str(input_path), str(geometry_path), str(args.cpu), *specifications])
        measurements = raw.splitlines()
        if len(measurements) != 1 + 7 * 2 * 8 * 8 or not all(
            line.endswith(",true") for line in measurements[1:]
        ):
            raise RuntimeError(f"{name}: incomplete verified timings")
        new_header, *new_rows = geometry_path.read_text(encoding="utf-8").splitlines()
        if len(new_rows) != len(days) or geometry_header not in (None, new_header):
            raise RuntimeError(f"{name}: invalid geometry")
        geometry_header = new_header
        geometry_rows.extend(new_rows)
        output_files[f"{name}.csv"] = "\n".join(measurements) + "\n"
        print(f"{name}: verified {len(measurements) - 1} calls", flush=True)
    output_files["geometry.csv"] = "\n".join([geometry_header, *geometry_rows]) + "\n"
    metadata["days"] = all_days
    metadata["finished_utc"] = datetime.now(timezone.utc).isoformat()
    metadata["csv_sha256"] = {
        name: hashlib.sha256(content.encode("utf-8")).hexdigest() for name, content in output_files.items()
    }
    for name, content in output_files.items():
        with (output / name).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(content)
    with (output / "metadata.json").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(metadata, indent=2) + "\n")


if __name__ == "__main__":
    main()
