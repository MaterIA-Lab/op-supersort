"""Validate the registered matrix and summarize reference/candidate medians."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

METHODS = {"bitplane_membership", "avx2_network16", "vqsort32", "x86_simd_sort32", "stable_counting256"}
CANDIDATE = "bitplane_membership"
CELLS = {(groups, distribution, seed) for groups, distribution in
         [(65536, "uniform"), (128, "uniform"), (65536, "eight")]
         for seed in (104729, 130363)}


def analyze(path: Path) -> dict:
    samples = defaultdict(dict)
    seen = set()
    count = 0
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            cell = (int(row["groups"]), row["distribution"], int(row["seed"]))
            method, round_number = row["method"], int(row["round"])
            identity = (*cell, method, round_number)
            if cell not in CELLS or method not in METHODS or round_number not in range(8):
                raise ValueError(f"unexpected matrix entry: {identity}")
            if identity in seen:
                raise ValueError(f"duplicate sample: {identity}")
            if row["verified"] != "true" or int(row["total_ns"]) <= 0:
                raise ValueError(f"invalid or unverified sample: {identity}")
            seen.add(identity)
            count += 1
            samples[cell, method][round_number] = int(row["total_ns"])
    expected = {(*cell, method, round_number) for cell in CELLS
                for method in METHODS for round_number in range(8)}
    if seen != expected:
        raise ValueError(f"incomplete matrix: {len(expected - seen)} missing entries")

    results = []
    for cell in sorted(CELLS, key=lambda cell: (cell[1] != "uniform", -cell[0], cell[2])):
        medians = {method: median(samples[cell, method][r] for r in range(1, 8)) for method in METHODS}
        best = min(METHODS - {CANDIDATE}, key=lambda method: medians[method])
        wins = sum(samples[cell, CANDIDATE][r] < samples[cell, best][r] for r in range(1, 8))
        results.append({
            "groups": cell[0], "distribution": cell[1], "seed": cell[2],
            "best_reference": best,
            "reference_ns_per_group": medians[best] / cell[0],
            "candidate_ns_per_group": medians[CANDIDATE] / cell[0],
            "speedup": medians[best] / medians[CANDIDATE],
            "candidate_time_ratio": medians[CANDIDATE] / medians[best],
            "passes_77_percent_gate": medians[CANDIDATE] <= 0.77 * medians[best],
            "paired_wins": wins,
            "all_median_ns_per_group": {method: value / cell[0] for method, value in sorted(medians.items())},
            "all_sample_ranges_ns_per_group": {
                method: [min(samples[cell, method][r] for r in range(1, 8)) / cell[0],
                         max(samples[cell, method][r] for r in range(1, 8)) / cell[0]]
                for method in sorted(METHODS)
            },
        })
    return {"verified_calls": count, "warmup_calls": 30, "measured_calls": 210, "cells": results}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = analyze(args.csv)
    print("| Groups | Keys | Seed | Best reference | Reference ns/group | Masks ns/group | Speedup | Paired wins |")
    print("|---:|---|---:|---|---:|---:|---:|---:|")
    for cell in result["cells"]:
        print(f'| {cell["groups"]:,} | {cell["distribution"]} | {cell["seed"]} | {cell["best_reference"]} | '
              f'{cell["reference_ns_per_group"]:.3f} | {cell["candidate_ns_per_group"]:.3f} | '
              f'{cell["speedup"]:.3f}x | {cell["paired_wins"]}/7 |')
    print(f'\nVerified {result["measured_calls"]} measured outputs and {result["warmup_calls"]} warm-ups.')
    if args.json:
        args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
