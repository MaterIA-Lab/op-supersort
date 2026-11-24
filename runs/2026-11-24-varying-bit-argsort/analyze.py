"""Verify the registered wide-key argsort matrix and summarize its medians."""

import argparse
import csv
import hashlib
import json
from itertools import product
from pathlib import Path
from statistics import median


METHODS = ("varying_bits", "field_ranges", "leading_prefix", "high_word_pairs", "pdqsort_indices")
SHAPES = ((1048576, "composite"), (4194304, "composite"), (1048576, "morton"), (1048576, "uniform"))
SEEDS = {"development": (49331, 93817), "holdout": (155921, 229369)}
PHASES = ("prepare_ns", "sort_ns", "finish_ns")
GEOMETRY = ("variable_bits", "prefix_bits", "repaired", "largest_repair", "scratch_bytes")
WARMUPS = 2
ROUNDS = 7


def require(condition, detail):
    if not condition:
        raise ValueError(detail)


def analyze(stage, directory):
    raw = directory / f"{stage}.csv"
    metadata = json.loads((directory / f"{stage}-metadata.json").read_text(encoding="utf-8"))
    require(hashlib.sha256(raw.read_bytes()).hexdigest() == metadata["raw_sha256"], "raw digest mismatch")
    shapes = SHAPES if stage == "development" else SHAPES[:2]
    cases = [(rows, shape, seed) for (rows, shape), seed in product(shapes, SEEDS[stage])]
    matrix, geometry = {}, {}
    with raw.open(encoding="utf-8", newline="") as stream:
        for row in csv.DictReader(stream):
            case = (int(row["rows"]), row["shape"], int(row["seed"]))
            method, repeat = row["method"], int(row["round"])
            key = (*case, method, repeat)
            require(case in cases and method in METHODS and 0 <= repeat < ROUNDS, key)
            require(row["verified"] == "true" and key not in matrix, key)
            timings = {name: int(row[name]) for name in ("total_ns", *PHASES)}
            require(0 <= sum(timings[name] for name in PHASES) <= timings["total_ns"], key)
            require(timings["total_ns"] > 0 and all(timings[name] >= 0 for name in PHASES), key)
            matrix[key] = timings
            shape = {field: int(row[field]) for field in GEOMETRY}
            require(0 <= shape["largest_repair"] <= shape["repaired"] <= case[0], key)
            require(0 <= shape["prefix_bits"] <= 64 and 0 <= shape["variable_bits"] <= 128, key)
            require(geometry.setdefault((*case, method), shape) == shape, key)
    require(len(matrix) == len(cases) * len(METHODS) * ROUNDS == metadata["verified_calls"], "incomplete matrix")

    results = []
    measured = range(WARMUPS, ROUNDS)
    for case in cases:
        samples = {method: [matrix[(*case, method, i)] for i in measured] for method in METHODS}
        medians = {method: {phase: median(row[phase] for row in samples[method])
                           for phase in ("total_ns", *PHASES)} for method in METHODS}
        reference = min(METHODS[1:], key=lambda method: medians[method]["total_ns"])
        best, candidate = medians[reference]["total_ns"], medians[METHODS[0]]["total_ns"]
        results.append({
            "rows": case[0],
            "shape": case[1],
            "seed": case[2],
            "fastest_reference": reference,
            "speedup": best / candidate,
            "passed": 100 * candidate <= 77 * best,
            "paired_wins": sum(a["total_ns"] < b["total_ns"] for a, b in
                               zip(samples[METHODS[0]], samples[reference], strict=True)),
            "times_ns": medians,
            "geometry": {method: geometry[(*case, method)] for method in METHODS},
        })
    return {
        "verified_calls": len(matrix),
        "measured_calls": len(matrix) * len(measured) // ROUNDS,
        "passed_primary": all(cell["passed"] for cell in results if cell["shape"] == "composite"),
        "cells": results,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=SEEDS)
    parser.add_argument("directory", nargs="?", type=Path, default=Path(__file__).resolve().parent)
    args = parser.parse_args()
    print(json.dumps(analyze(args.stage, args.directory), indent=2))
