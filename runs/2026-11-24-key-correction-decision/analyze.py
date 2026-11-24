"""Verify a direct-span timing matrix and summarize the registered comparisons."""

import argparse
import csv
import gzip
import hashlib
import json
from collections import Counter
from itertools import product
from pathlib import Path
from statistics import median


CACHES = ("copy_reset", "flushed")
METHODS = ("direct_spans", "bulk_esm_left", "bulk_esm_right", "delta_sort", "full_sort",
           "drift_sort", "regional_esm_left", "regional_esm_right",
           "buffered_esm_32k", "buffered_esm_128k", "direct_spans_phases")
BUFFERED = {"buffered_esm_32k", "buffered_esm_128k"}
COUNTED = BUFFERED | {"direct_spans", "bulk_esm_left", "bulk_esm_right",
                      "regional_esm_left", "regional_esm_right", "direct_spans_phases"}
PHASES = "direct_spans_phases"
CANDIDATE = "direct_spans"
GEOMETRY = ("rows", "edits", "p50", "p95", "maximum", "interval", "minimum_writes")
WARMUPS = 2
REPEATS = 5


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def summarize(cells):
    ratios = [cell["speedup"] for cell in cells]
    return {
        "cases": len(cells),
        "passed": sum(cell["passed"] for cell in cells),
        "speedup_min": min(ratios),
        "speedup_median": median(ratios),
        "speedup_max": max(ratios),
        "prior_reference_speedup_min": min(cell["prior_reference_speedup"] for cell in cells),
        "prior_reference_speedup_max": max(cell["prior_reference_speedup"] for cell in cells),
        "fastest_references": dict(Counter(cell["reference"] for cell in cells)),
        "median_candidate_ms": median(cell["median_ns"][CANDIDATE] for cell in cells) / 1e6,
        "median_reference_ms": median(cell["median_ns"][cell["reference"]] for cell in cells) / 1e6,
        "median_planning_share": median(cell["planning_share"] for cell in cells),
    }


def schedule(stage):
    if stage == "synthetic":
        for mib, distance, seed in product((4, 32, 128), ("short", "medium", "random"), (48781, 90271)):
            yield f"{mib}MiB-{distance}-{seed}", f"{mib}MiB-{distance}"
    else:
        for day, hour, width in product((9, 13), (7, 12, 17), (15, 60)):
            yield f"{stage}-{day:02d}-{hour:02d}00-{width}m", f"{width}m"


def analyze(stage, directory):
    archive = directory / f"{stage}.csv.gz"
    metadata = json.loads((directory / f"{stage}-metadata.json").read_text(encoding="utf-8"))
    require(hashlib.sha256(archive.read_bytes()).hexdigest() == metadata["raw_gzip_sha256"],
            "raw timing digest mismatch")
    synthetic = stage == "synthetic"
    cases = dict(schedule(stage))
    modes = ("positions",) if synthetic else ("id", "positions")
    methods = METHODS if synthetic else (*METHODS, "counting_gather")
    rounds = range(WARMUPS + REPEATS)
    geometry, timings, counts, phases = {}, {}, {}, {}
    with gzip.open(archive, "rt", encoding="ascii", newline="") as stream:
        for row in csv.DictReader(stream):
            case, mode, cache, method = (row[k] for k in ("case", "mode", "cache", "method"))
            repeat = int(row["round"])
            key = (case, mode, cache, method, repeat)
            require(case in cases and mode in modes and cache in CACHES and method in methods and repeat in rounds, key)
            require(key not in timings and row["verified"] == "true", key)
            shape = {k: (float(row[k]) if k == "p50" else int(row[k])) for k in GEOMETRY}
            require(geometry.setdefault(case, shape) == shape, key)
            if synthetic:
                expected_mib = int(cases[case].split("MiB")[0])
                require(shape["rows"] * 128 == expected_mib * (1 << 20), key)
                require(shape["edits"] == shape["rows"] // 1024, key)
            else:
                require(shape["rows"] == metadata["flight_source"]["counts"]["roster_rows"], key)
            ns = int(row["total_ns"])
            require(ns > 0, key)
            timings[key] = ns
            if method in COUNTED:
                writes = int(row["writes"])
                require(writes >= shape["minimum_writes"], key)
                require(counts.setdefault((case, method), writes) == writes, key)
                if method in (CANDIDATE, PHASES):
                    require(writes == shape["minimum_writes"], key)
            else:
                require(not row["writes"], key)
            if method == PHASES:
                plan, execute = int(row["plan_ns"]), int(row["execute_ns"])
                require(0 <= plan + execute <= ns, key)
                phases[key] = (plan, execute)
            else:
                require(not row["plan_ns"] and not row["execute_ns"], key)
    expected = len(cases) * len(modes) * len(CACHES) * len(methods) * len(rounds)
    require(len(timings) == expected == metadata["verified_calls"], "incomplete timing matrix")

    details = []
    by_class = {}
    measured = range(WARMUPS, WARMUPS + REPEATS)
    for case, mode, cache in product(cases, modes, CACHES):
        series = {method: [timings[case, mode, cache, method, i] for i in measured] for method in methods}
        medians = {method: median(values) for method, values in series.items()}
        eligible = [method for method in methods if method not in (CANDIDATE, PHASES)]
        reference = min(eligible, key=medians.__getitem__)
        prior = min((m for m in eligible if m not in BUFFERED), key=medians.__getitem__)
        phase_samples = [phases[case, mode, cache, PHASES, i] for i in measured]
        applied = [plan / (plan + execute) for plan, execute in phase_samples if plan + execute]
        cell = {
            "case": case,
            "mode": mode,
            "cache": cache,
            "reference": reference,
            "speedup": medians[reference] / medians[CANDIDATE],
            "prior_reference": prior,
            "prior_reference_speedup": medians[prior] / medians[CANDIDATE],
            "passed": 100 * medians[reference] >= 130 * medians[CANDIDATE],
            "paired_wins": sum(a < b for a, b in zip(series[CANDIDATE], series[reference], strict=True)),
            "median_ns": medians,
            "median_plan_ns": median(p for p, _ in phase_samples),
            "median_execute_ns": median(e for _, e in phase_samples),
            "planning_share": median(applied) if applied else 0.0,
            "writes": {method: counts[case, method] for method in methods if method in COUNTED},
        }
        details.append(cell)
        by_class.setdefault(f"{cases[case]}_{mode}_{cache}", []).append(cell)
    groups = {kind: summarize(cells) for kind, cells in by_class.items()}
    qualified = [width for width in (15, 60) if groups[f"{width}m_id_copy_reset"]["passed"] >= 4] if not synthetic else []
    return {
        "stage": stage,
        "verified_calls": len(timings),
        "measured_calls": len(timings) * REPEATS // (WARMUPS + REPEATS),
        "qualified_widths_minutes": qualified,
        "geometry": geometry,
        "groups": groups,
        "comparisons": details,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("synthetic", "january", "april"))
    parser.add_argument("directory", nargs="?", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(analyze(args.stage, args.directory), indent=2))
