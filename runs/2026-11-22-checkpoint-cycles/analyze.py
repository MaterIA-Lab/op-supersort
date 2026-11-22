"""Validate the complete registered matrix and compute per-cell medians."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

CANDIDATE = "checkpoint64_vqsort"
METHODS = {CANDIDATE, "scalar_cycle_vqsort", "cached_gather_vqsort",
           "stream_gather_vqsort", "stream_gather_x86", "pdqsort_rows"}
CELLS = {(records, distribution, seed) for records, distribution in
         [(1048576, "uniform"), (8192, "uniform"), (1048576, "eight")]
         for seed in (48071, 65827)}


def analyze(path: Path) -> dict:
    samples = defaultdict(dict)
    seen = set()
    with path.open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            cell = (int(row["records"]), row["distribution"], int(row["seed"]))
            method, round_number = row["method"], int(row["round"])
            identity = (*cell, method, round_number)
            if cell not in CELLS or method not in METHODS or round_number not in range(6):
                raise ValueError(f"unexpected sample: {identity}")
            if identity in seen or row["verified"] != "true":
                raise ValueError(f"duplicate or unverified sample: {identity}")
            phases = {field: int(row[field]) for field in ("index_ns", "materialize_ns", "total_ns")}
            if phases["total_ns"] <= 0 or min(phases.values()) < 0:
                raise ValueError(f"invalid timing: {identity}")
            if phases["index_ns"] + phases["materialize_ns"] > phases["total_ns"]:
                raise ValueError(f"phases exceed total: {identity}")
            seen.add(identity)
            samples[cell, method][round_number] = phases
    expected = {(*cell, method, round_number) for cell in CELLS
                for method in METHODS for round_number in range(6)}
    if seen != expected:
        raise ValueError(f"incomplete matrix: {len(expected - seen)} missing samples")

    cells = []
    for cell in sorted(CELLS, key=lambda c: (c[1] != "uniform", -c[0], c[2])):
        medians = {
            method: {field.removesuffix("_ns") + "_ms": median(samples[cell, method][r][field] for r in range(1, 6)) / 1e6
                     for field in ("index_ns", "materialize_ns", "total_ns")}
            for method in sorted(METHODS)
        }
        best = min(METHODS - {CANDIDATE}, key=lambda m: medians[m]["total_ms"])
        candidate_time = medians[CANDIDATE]["total_ms"]
        reference_time = medians[best]["total_ms"]
        cells.append({
            "records": cell[0], "distribution": cell[1], "seed": cell[2],
            "best_reference": best,
            "best_reference_ms": reference_time,
            "candidate_ms": candidate_time,
            "speedup": reference_time / candidate_time,
            "candidate_time_ratio": candidate_time / reference_time,
            "passes_77_percent_gate": candidate_time <= 0.77 * reference_time,
            "paired_wins": sum(samples[cell, CANDIDATE][r]["total_ns"] <
                               samples[cell, best][r]["total_ns"] for r in range(1, 6)),
            "all_median_ms": medians,
            "all_total_ranges_ms": {
                method: [min(samples[cell, method][r]["total_ns"] for r in range(1, 6)) / 1e6,
                         max(samples[cell, method][r]["total_ns"] for r in range(1, 6)) / 1e6]
                for method in sorted(METHODS)
            },
        })
    return {"verified_calls": len(seen), "measured_calls": 180, "warmup_calls": 36, "cells": cells}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = analyze(args.csv)
    print("| Records | Keys | Seed | Best reference | Reference ms | Checkpoints ms | Speedup | Paired wins |")
    print("|---:|---|---:|---|---:|---:|---:|---:|")
    for cell in result["cells"]:
        print(f'| {cell["records"]:,} | {cell["distribution"]} | {cell["seed"]} | '
              f'{cell["best_reference"]} | {cell["best_reference_ms"]:.3f} | '
              f'{cell["candidate_ms"]:.3f} | {cell["speedup"]:.3f}x | {cell["paired_wins"]}/5 |')
    print(f'\nVerified {result["measured_calls"]} measured calls and {result["warmup_calls"]} warm-ups.')
    if args.json:
        args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
