import argparse
import csv
from datetime import datetime
from itertools import product
import json
from pathlib import Path
from statistics import median


COVERAGE = Path(__file__).resolve().parent.parent / "2026-11-12-gharchive-page-coverage"
FRESH = ("scalar", "bulk", "hybrid", "concat")
RESIDENT = ("hybrid_reused", "concat_reused")
METHODS = (*FRESH, *RESIDENT, "remap")


def load_cases():
    manifest = json.loads((COVERAGE / "archives.json").read_text(encoding="utf-8"))
    by_name = {entry["file"]: entry for entry in manifest["archives"]}
    cases = {}
    with (COVERAGE / "coverage.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if (row["status"] != "ok" or int(row["overlap_us"]) or int(row["shared_timestamps"]) or
                    int(row["slices"]) != 2):
                raise ValueError("timing fixture requires verified disjoint source slices")
            day = row["day"]
            a, b = row["capture_a"], row["capture_b"]
            groups = [[by_name[f"{day}-{int(hour)}.json.gz"] for hour in capture.split("-")]
                      for capture in (a, b)]
            earliest, latest = ("earliest", "latest")
            last_a = max(datetime.fromisoformat(entry[latest].replace("Z", "+00:00")) for entry in groups[0])
            first_b = min(datetime.fromisoformat(entry[earliest].replace("Z", "+00:00")) for entry in groups[1])
            rows_a, rows_b = int(row["rows_a"]), int(row["rows_b"])
            if last_a >= first_b or [rows_a, rows_b] != [sum(entry["rows"] for entry in group) for group in groups]:
                raise ValueError("capture bounds or counts do not match the verified coverage matrix")
            name = f"{day}_{a}_to_{b}"
            if name in cases:
                raise ValueError("duplicate coverage case")
            cases[name] = (rows_a, rows_b, int(row["mappable_bytes"]), int(row["mappable_extents"]))
    if len(cases) != 8:
        raise ValueError("expected all eight registered batch pairs")
    return cases


def timing_rows(path, cases):
    samples = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            case, method = row["layout"], row["method"]
            repetition = int(row["repetition"])
            key = (case, repetition, method)
            if case not in cases or key in samples:
                raise ValueError("unexpected or duplicated timing sample")
            rows_a, rows_b, mapped, calls = cases[case]
            if (int(row["records"]) != rows_a + rows_b or int(row["seed"]) != 53 or
                    int(row["warmup"]) != (repetition == 0)):
                raise ValueError("benchmark input does not match registered batches")
            expected_mapping = (mapped, calls) if method == "remap" else (0, 0)
            if (int(row["mapped_bytes"]), int(row["map_calls"])) != expected_mapping:
                raise ValueError("measured mappings do not match archive coverage")
            total, assembly, scan, teardown = (int(row[field]) for field in
                                               ("total_ns", "assembly_ns", "scan_ns", "teardown_ns"))
            if min(assembly, scan, teardown) <= 0 or total != assembly + scan:
                raise ValueError("invalid sample times")
            samples[key] = (total, teardown)
    if samples.keys() != set(product(cases, range(6), METHODS)):
        raise ValueError("unexpected timing sample matrix")
    return samples


def summarize(path, cases):
    samples = timing_rows(path, cases)
    print("| Batch pair | Records | Mapped | Fresh concat (ms) | Best fresh (ms) | Best resident (ms) | Remap (ms) | Remap teardown (ms) | Speedup vs fresh | Speedup vs resident |")
    print("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    ratios = []
    for case, (rows_a, rows_b, mapped, _) in cases.items():
        fresh, concat, resident, remap, teardown = [], [], [], [], []
        for repetition in range(1, 6):
            fresh.append(min(samples[case, repetition, method][0] for method in FRESH))
            concat.append(samples[case, repetition, "concat"][0])
            resident.append(min(samples[case, repetition, method][0] for method in RESIDENT))
            elapsed, release = samples[case, repetition, "remap"]
            remap.append(elapsed)
            teardown.append(release)
        ratio = median(a / b for a, b in zip(fresh, remap))
        resident_ratio = median(a / b for a, b in zip(resident, remap))
        ratios.append((ratio, resident_ratio))
        count = rows_a + rows_b
        medians = " | ".join(f"{median(values) / 1e6:.2f}" for values in (concat, fresh, resident, remap, teardown))
        print(f"| {case.replace('_', ' ')} | {count:,} | {mapped / (count * 128):.2%} | {medians} | "
              f"{ratio:.3f}× | {resident_ratio:.3f}× |")
    print()
    for label, index in (("fresh", 0), ("resident", 1)):
        for threshold in (1.3, 1.5):
            passing = sum(pair[index] >= threshold for pair in ratios)
            print(f"- {passing}/{len(cases)} cases reached {threshold}× against the fastest {label} reference.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check and report the disjoint GH Archive timing run.")
    parser.add_argument("samples", nargs="?", type=Path, help="path to disjoint.csv")
    parser.add_argument("--cases", action="store_true", help="emit the eight verified input cases for the benchmark")
    arguments = parser.parse_args()
    cases = load_cases()
    if arguments.cases:
        for name, (rows_a, rows_b, _, _) in cases.items():
            print(name, rows_a, rows_b)
    elif arguments.samples:
        summarize(arguments.samples, cases)
    else:
        parser.error("provide --cases or the path to disjoint.csv")
