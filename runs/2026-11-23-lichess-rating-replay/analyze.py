"""Recompute the preregistered Lichess replay comparisons from a saved timing archive."""

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from itertools import product
from pathlib import Path
from statistics import median


CACHES = ("flushed", "copy_reset")
METHODS = ("direct_spans", "bulk_esm_left", "bulk_esm_right", "delta_sort", "full_sort",
           "drift_sort", "regional_esm_left", "regional_esm_right", "counting_gather")
COUNTED = {"direct_spans", "bulk_esm_left", "bulk_esm_right", "regional_esm_left", "regional_esm_right"}
CANDIDATE = METHODS[0]
WARMUPS = 3
MEASURED = 11


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(directory):
    raw = directory / "raw.csv.gz"
    geometry_path = directory / "geometry.json"
    metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
    require(digest(raw) == metadata["raw_gzip_sha256"], "raw gzip digest mismatch")
    require(digest(geometry_path) == metadata["geometry_sha256"], "geometry digest mismatch")
    geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
    roster = geometry["extraction_counts"]["roster"]
    schedule = [(f"2015-01-{day}T{hour:02d}:00Z/{width}s", width)
                for day, hour, width in product((22, 25, 28, 31), (6, 12, 18), (60, 600))]
    require(schedule == [(cell["label"], cell["seconds"]) for cell in geometry["windows"]],
            "incomplete geometry or altered schedule")
    cells = {cell["label"]: cell for cell in geometry["windows"]}
    timed_cells = {name for name, cell in cells.items() if cell["edits"] > 0}
    rounds = range(WARMUPS + MEASURED)
    samples = {}
    counts = {}
    with gzip.open(raw, "rt", encoding="ascii", newline="") as stream:
        for row in csv.DictReader(stream):
            window, cache, method, repeat = row["window"], row["cache"], row["method"], int(row["round"])
            key = (window, cache, method, repeat)
            require(window in timed_cells and cache in CACHES and method in METHODS and repeat in rounds, key)
            ns = int(row["total_ns"])
            cell = cells[window]
            require(key not in samples and row["verified"] == "true" and ns > 0, key)
            require(int(row["rows"]) == roster and int(row["edits"]) == cell["edits"]
                    and int(row["interval_rows"]) == cell["affected_interval_rows"], key)
            samples[key] = ns
            if method in COUNTED:
                count = int(row["unchanged_rows_written"])
                minimum = cell["minimum_unchanged_writes"]
                require(count >= minimum and (method != CANDIDATE or count == minimum), key)
                require(counts.setdefault((window, method), count) == count, key)
            else:
                require(not row["unchanged_rows_written"], key)
    require(len(samples) == len(timed_cells) * len(CACHES) * len(METHODS) * len(rounds),
            "incomplete raw timing matrix")
    require(len(samples) == metadata["verified_calls"], "inconsistent sample count")

    comparisons = []
    for window, cell in cells.items():
        if window not in timed_cells:
            continue
        for cache in CACHES:
            measured = {method: [samples[(window, cache, method, repeat)]
                                 for repeat in range(WARMUPS, WARMUPS + MEASURED)] for method in METHODS}
            medians = {method: median(times) for method, times in measured.items()}
            reference = min(METHODS[1:], key=medians.__getitem__)
            comparisons.append({
                "window": window,
                "seconds": cell["seconds"],
                "cache": cache,
                "fastest_reference": reference,
                "speedup": medians[reference] / medians[CANDIDATE],
                "passes": 100 * medians[CANDIDATE] <= 77 * medians[reference],
                "paired_wins_vs_reference": sum(
                    left < right for left, right in zip(measured[CANDIDATE], measured[reference], strict=True)
                ),
                "median_ns": medians,
                "unchanged_rows_written": {method: counts[(window, method)] for method in METHODS if method in COUNTED},
            })

    groups = {}
    for width, cache in product((60, 600), CACHES):
        group = [cmp for cmp in comparisons if cmp["seconds"] == width and cmp["cache"] == cache]
        ratios = [cmp["speedup"] for cmp in group]
        passes = sum(cmp["passes"] for cmp in group)
        central = median(ratios) if ratios else None
        groups[f"{width}s_{cache}"] = {
            "timed_windows": len(group),
            "passing_windows": passes,
            "median_speedup": central,
            "min_speedup": min(ratios, default=None),
            "max_speedup": max(ratios, default=None),
            "fastest_references": dict(Counter(cmp["fastest_reference"] for cmp in group)),
            "passes_screen": passes >= 9 and central is not None and central >= 100 / 77,
        }
    return {
        "verified_calls": len(samples),
        "measured_calls": len(timed_cells) * len(CACHES) * len(METHODS) * MEASURED,
        "groups": groups,
        "comparisons": comparisons,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(analyze(args.directory), indent=2))
