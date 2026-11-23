"""Verify the recorded flight matrix and reproduce its median comparisons."""

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median


WEEKS = {"jan": ("01", 7), "apr": ("04", 1), "jul": ("07", 1), "oct": ("10", 7)}
CACHES = ("cold", "resident")
CANDIDATE = "direct_spans"
REFERENCES = ("bulk_esm_left", "bulk_esm_right", "delta_sort", "full_sort", "drift_sort",
              "regional_esm_left", "regional_esm_right")
METHODS = (CANDIDATE, *REFERENCES)
COUNTED = {CANDIDATE, "bulk_esm_left", "bulk_esm_right", "regional_esm_left", "regional_esm_right"}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_csv(directory, hashes, stem):
    path = directory / f"{stem}.csv"
    require(hashlib.sha256(path.read_bytes()).hexdigest() == hashes[path.name], f"checksum for {path.name}")
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def describe(values):
    return {"min": min(values), "median": median(values), "max": max(values)}


def analyze(directory):
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    hashes = metadata["csv_sha256"]
    cases = []
    geometry_rows = read_csv(directory, hashes, "geometry")
    geometry = {row["day"]: {key: int(value) for key, value in row.items() if key != "day"}
                for row in geometry_rows}
    require(len(geometry_rows) == len(geometry) == 28, "expected 28 unique days of geometry")

    for name, (month, first_day) in WEEKS.items():
        days = [f"2013-{month}-{number:02}" for number in range(first_day, first_day + 7)]
        measurements = {}
        write_counts = defaultdict(set)
        for row in read_csv(directory, hashes, name):
            day, cache, method, round_number = row["day"], row["cache"], row["method"], int(row["round"])
            key = (day, cache, method, round_number)
            require(day in days and cache in CACHES and method in METHODS and 0 <= round_number <= 7, key)
            time_ns = int(row["total_ns"])
            require(key not in measurements and row["verified"] == "true" and time_ns > 0, key)
            measurements[key] = time_ns
            if method in COUNTED:
                writes = int(row["unchanged_rows_written"])
                minimum = geometry[day]["minimum_unchanged_writes"]
                require(writes == minimum if method == CANDIDATE else writes >= minimum, key)
                write_counts[(day, method)].add(writes)
            else:
                require(row["unchanged_rows_written"] == "", key)
        require(len(measurements) == len(days) * len(CACHES) * len(METHODS) * 8, name)
        require(all(len(counts) == 1 for counts in write_counts.values()), "nondeterministic write counts")

        for day in days:
            writes = {method: next(iter(write_counts[(day, method)])) for method in sorted(COUNTED)}
            for cache in CACHES:
                medians = {method: median(measurements[(day, cache, method, index)] for index in range(1, 8))
                           for method in METHODS}
                fastest = min(REFERENCES, key=medians.__getitem__)
                cases.append({
                    "day": day,
                    "cache": cache,
                    "median_ns": medians,
                    "fastest_reference": fastest,
                    "speedup": medians[fastest] / medians[CANDIDATE],
                    "passes": 100 * medians[CANDIDATE] <= 77 * medians[fastest],
                    "unchanged_writes": writes,
                })

    aggregate = {}
    for cache in CACHES:
        by_cache = [case for case in cases if case["cache"] == cache]
        aggregate[cache] = {
            "speedup": describe([case["speedup"] for case in by_cache]),
            "passing_days": sum(case["passes"] for case in by_cache),
            "winning_days": sum(case["speedup"] > 1 for case in by_cache),
            "fastest_reference_counts": dict(Counter(case["fastest_reference"] for case in by_cache)),
            "median_of_day_medians_ns": {method: median(case["median_ns"][method] for case in by_cache)
                                         for method in METHODS},
        }
    return {
        "verified_calls": 28 * len(CACHES) * len(METHODS) * 8,
        "measured_calls": 28 * len(CACHES) * len(METHODS) * 7,
        "aggregate": aggregate,
        "geometry": {field: describe([record[field] for record in geometry.values()])
                     for field in next(iter(geometry.values()))},
        "cases": cases,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(analyze(args.directory), indent=2))
