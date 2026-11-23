"""Verify the registered matrix and summarize the published medians."""

import argparse
import csv
import hashlib
import json
from pathlib import Path
from statistics import median


CACHE_STATES = ("flushed", "copy_reset")
METHODS = (
    "direct_spans", "bulk_esm_left", "bulk_esm_right", "delta_sort", "full_sort",
    "drift_sort", "regional_esm_left", "regional_esm_right", "counting_gather",
)
COUNTED = ("direct_spans", "bulk_esm_left", "bulk_esm_right", "regional_esm_left", "regional_esm_right")
WARMUPS = 3
ROUNDS = 14


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(directory):
    raw = directory / "raw.csv"
    geometry_path = directory / "geometry.json"
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    require(digest(raw) == metadata["raw_sha256"], "raw timing digest mismatch")
    require(digest(geometry_path) == metadata["geometry_sha256"], "geometry digest mismatch")
    geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
    require(geometry["fixture_sha256"] == metadata["fixture_sha256"], "fixture digest mismatch")
    measured = {}
    counted = {}
    interval_sizes = set()
    with raw.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            require(int(row["rows"]) == geometry["shared_rows"], "row count mismatch")
            require(int(row["edits"]) == geometry["edits"], "edit count mismatch")
            cache, method, round_index = row["cache"], row["method"], int(row["round"])
            key = (cache, method, round_index)
            require(cache in CACHE_STATES and method in METHODS and 0 <= round_index < ROUNDS, key)
            ns = int(row["total_ns"])
            require(key not in measured and ns > 0 and row["verified"] == "true", key)
            measured[key] = ns
            interval_sizes.add(int(row["interval_rows"]))
            if method in COUNTED:
                writes = int(row["unchanged_rows_written"])
                minimum = geometry["minimum_unchanged_writes"]
                require(writes >= minimum and counted.get(method, writes) == writes, key)
                counted[method] = writes
            else:
                require(not row["unchanged_rows_written"], key)
    require(len(measured) == len(CACHE_STATES) * len(METHODS) * ROUNDS, "incomplete matrix")
    require(counted["direct_spans"] == geometry["minimum_unchanged_writes"], "non-minimal writes")
    require(len(interval_sizes) == 1, "inconsistent interval size")
    summary = {}
    for cache in CACHE_STATES:
        times = {method: [measured[(cache, method, r)] for r in range(WARMUPS, ROUNDS)]
                 for method in METHODS}
        medians = {method: median(samples) for method, samples in times.items()}
        reference = min(METHODS[1:], key=medians.__getitem__)
        summary[cache] = {
            "fastest_reference": reference,
            "speedup": medians[reference] / medians["direct_spans"],
            "passes": 100 * medians["direct_spans"] <= 77 * medians[reference],
            "paired_wins_vs_reference": sum(c < b for c, b in zip(times["direct_spans"], times[reference], strict=True)),
            "times_ns": {method: {"min": min(samples), "median": medians[method], "max": max(samples)}
                         for method, samples in times.items()},
        }
    return {
        "verified_calls": len(measured),
        "measured_calls": len(CACHE_STATES) * len(METHODS) * (ROUNDS - WARMUPS),
        "comparison": summary,
        "unchanged_writes": counted,
        "affected_interval_rows": next(iter(interval_sizes)),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(analyze(args.directory), indent=2))
