import csv
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median


REFERENCES = ("split_plain", "split16", "split32", "split64", "split128", "split_nt_plain", "split_nt32")
HELPERS = ("hint256", "hint1024", "load256", "load1024", "hint_nt1024")
METHODS = (*REFERENCES, "single32", *HELPERS)
CASES = {
    (placement, rows, seed)
    for placement, rows in [("smt", 2**15), ("smt", 2**21), ("two_cores", 2**21)]
    for seed in (104729, 130363)
}


def load(path):
    trials = defaultdict(lambda: defaultdict(dict))
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            case = (row["placement"], int(row["rows"]), int(row["seed"]))
            methods = trials[case][int(row["round"])]
            method = row["method"]
            elapsed, requests = float(row["ms"]), int(row["requested"])
            request_limit = case[1] - 128 if method in HELPERS else 0
            if (row["verified"] != "1" or method in methods or not 0 < elapsed < float("inf")
                    or not 0 <= requests <= request_limit):
                raise ValueError(f"Invalid measurement: {row}")
            methods[method] = (elapsed, requests)
    if trials.keys() != CASES:
        raise ValueError("Measurements do not cover the preregistered cases")
    for case, rounds in trials.items():
        if rounds.keys() != set(range(8)) or any(vals.keys() != set(METHODS) for vals in rounds.values()):
            raise ValueError(f"Incomplete rounds: {case}")
    return trials


def analyze(path):
    trials = load(path)
    print("| Placement | Rows | Seed | Best split | Split (ms) | Single (ms) | Best helper | Helper (ms) | Split/helper | Single/helper | Helper requests | Paired wins vs split |")
    print("|---|---:|---:|---|---:|---:|---|---:|---:|---:|---:|---:|")
    primary = []
    for (placement, rows, seed), rounds in sorted(trials.items()):
        times = {method: median(rounds[i][method][0] for i in range(1, 8)) for method in METHODS}
        best_split = min(REFERENCES, key=times.__getitem__)
        best_helper = min(HELPERS, key=times.__getitem__)
        split, helper, single = times[best_split], times[best_helper], times["single32"]
        requests = median(rounds[i][best_helper][1] for i in range(1, 8)) / rows
        wins = sum(rounds[i][best_helper][0] < rounds[i][best_split][0] for i in range(1, 8))
        print(f"| {placement} | {rows:,} | {seed} | {best_split} | {split:.3f} | {single:.3f} | {best_helper} | "
              f"{helper:.3f} | {split / helper:.3f}x | {single / helper:.3f}x | {requests:.1%} | {wins}/7 |")
        if placement == "smt" and rows == 2**21:
            primary.append({method: split / times[method] for method in HELPERS})

    print("\nPrimary ratios by helper method (seeds 104729, 130363):")
    for method in HELPERS:
        print(f"- {method}: {primary[0][method]:.3f}x, {primary[1][method]:.3f}x")
    passing = [method for method in HELPERS if all(case[method] >= 1.30 for case in primary)]
    print(f"\nHelper arms at or above 1.30x on both seeds: {', '.join(passing) or 'none'}.")
    print(f"Validated {len(CASES) * 7 * len(METHODS)} measured and {len(CASES) * len(METHODS)} warm-up outputs.")


if __name__ == "__main__":
    analyze(Path(sys.argv[1]))
