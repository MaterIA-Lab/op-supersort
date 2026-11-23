"""Validate the registered timing matrix and recalculate cell summaries."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from statistics import median

CANDIDATE = "direct_spans"
MOVEMENT_METHODS = {CANDIDATE, "bulk_esm_left", "bulk_esm_right"}
METHODS = MOVEMENT_METHODS | {"delta_sort", "full_sort"}
DEVELOPMENT = [(1048576, 1024, "uniform"), (1048576, 32, "uniform"),
               (1048576, 1024, "local"), (4096, 16, "uniform")]
HOLDOUT = [(1048576, 1024, "uniform"), (2097152, 2048, "uniform")]
REFERENCE_AUDIT_SEEDS = (1234567, 98765431)


def analyze(path: Path, stage: str) -> dict:
    shape, seeds, methods = {
        "development": (DEVELOPMENT, (84731, 190027), METHODS),
        "holdout": (HOLDOUT, (1000003, 16777259), METHODS),
        "reference-audit": (HOLDOUT, REFERENCE_AUDIT_SEEDS, METHODS | {"drift_sort"}),
    }[stage]
    expected_cells = [(size, count, distribution, seed)
                      for size, count, distribution in shape for seed in seeds]
    expected = {(*cell, method, repeat) for cell in expected_cells
                for method in methods for repeat in range(8)}
    seen = set()
    timing = defaultdict(dict)
    movement = defaultdict(set)
    with path.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            cell = (int(row["rows"]), int(row["edits"]), row["distribution"], int(row["seed"]))
            method = row["method"]
            repeat = int(row["round"])
            sample = (*cell, method, repeat)
            elapsed = int(row["total_ns"])
            if sample not in expected or sample in seen or row["verified"] != "true" or elapsed <= 0:
                raise ValueError(f"unexpected, duplicate or invalid measurement: {sample}")
            seen.add(sample)
            timing[cell, method][repeat] = elapsed
            written = row["unchanged_rows_written"]
            if method in MOVEMENT_METHODS:
                count = int(written)
                limit = (cell[0] - cell[1]) * (1 if method == CANDIDATE else 2)
                if not 0 <= count <= limit:
                    raise ValueError(f"movement count out of range for {sample}")
                movement[cell, method].add(count)
            elif written:
                raise ValueError(f"unexpected movement count for {sample}")
    if seen != expected:
        raise ValueError(f"matrix is incomplete: {len(expected - seen)} samples missing")
    if any(len(counts) != 1 for counts in movement.values()):
        raise ValueError("a method reported inconsistent write counts on identical inputs")

    cells = []
    for cell in expected_cells:
        medians = {method: median(timing[cell, method][r] for r in range(1, 8)) / 1e6
                   for method in sorted(methods)}
        best = min(sorted(methods - {CANDIDATE}), key=medians.__getitem__)
        primary = stage != "development" or cell[:3] == DEVELOPMENT[0]
        cells.append({
            "rows": cell[0], "edits": cell[1], "distribution": cell[2], "seed": cell[3],
            "primary": primary,
            "best_reference": best,
            "candidate_ms": medians[CANDIDATE],
            "reference_ms": medians[best],
            "speedup": medians[best] / medians[CANDIDATE],
            "passes_77_percent_gate": medians[CANDIDATE] <= 0.77 * medians[best],
            "paired_wins": sum(timing[cell, CANDIDATE][r] < timing[cell, best][r] for r in range(1, 8)),
            "median_ms": medians,
            "sample_range_ms": {
                method: [min(timing[cell, method][r] for r in range(1, 8)) / 1e6,
                         max(timing[cell, method][r] for r in range(1, 8)) / 1e6]
                for method in sorted(methods)
            },
            "unchanged_rows_written": {m: next(iter(movement[cell, m])) for m in sorted(MOVEMENT_METHODS)},
        })
    warmups = len(expected_cells) * len(methods)
    return {"stage": stage, "verified_calls": len(seen), "measured_calls": len(seen) - warmups,
            "warmups": warmups, "cells": cells,
            "primary_passed": all(c["passes_77_percent_gate"] for c in cells if c["primary"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("development", "holdout", "reference-audit"))
    parser.add_argument("csv", type=Path)
    parser.add_argument("--json", type=Path)
    args = parser.parse_args()
    result = analyze(args.csv, args.stage)
    print("| Rows | Edits | Distribution | Seed | Best reference | Ref., ms | Spans, ms | Speedup | Wins |")
    print("|---:|---:|---|---:|---|---:|---:|---:|---:|")
    for cell in result["cells"]:
        print(f'| {cell["rows"]:,} | {cell["edits"]:,} | {cell["distribution"]} | {cell["seed"]} | '
              f'{cell["best_reference"]} | {cell["reference_ms"]:.3f} | {cell["candidate_ms"]:.3f} | '
              f'{cell["speedup"]:.3f}x | {cell["paired_wins"]}/7 |')
    print(f'Primary gate passed: {result["primary_passed"]}. Verified {result["measured_calls"]} measured calls '
          f'and {result["warmups"]} warm-ups.')
    if args.json:
        args.json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
