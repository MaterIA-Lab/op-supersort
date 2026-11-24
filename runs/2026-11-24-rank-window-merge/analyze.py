"""Validate merge samples and evaluate the preregistered gate."""

import argparse
import csv
import json
from collections import defaultdict
from itertools import product
from pathlib import Path
from runpy import run_path
from statistics import median


HERE = Path(__file__).resolve().parent
DRIVER = run_path(str(HERE.parents[1] / "prototypes/agents/rank-window-merge/run.py"))
METHODS = DRIVER["METHODS"]
REFERENCES = DRIVER["REFERENCES"]
CANDIDATES = DRIVER["CANDIDATES"]
REPLAYS = DRIVER["REPLAYS"]


def read_stage(work, stage):
    data = work / f"{stage}.csv"
    metadata = json.loads((work / f"{stage}-metadata.json").read_text(encoding="utf-8"))
    warmups, measured = DRIVER["WARMUPS"], DRIVER["MEASURED"]
    if (metadata["stage"] != stage or metadata["raw_sha256"] != DRIVER["digest"](data)
            or metadata["source_sha256"] != DRIVER["source_hashes"]()
            or (metadata["warmups"], metadata["measured_calls_per_method"]) != (warmups, measured)):
        raise ValueError("sample or build metadata mismatch")
    if stage == "holdout":
        prior = json.loads((work / "development-metadata.json").read_text(encoding="utf-8"))
        if metadata["binary_sha256"] != prior["binary_sha256"]:
            raise ValueError("holdout used a different build")

    cases = [(n, shape, seed) for (n, shape), seed in DRIVER["cases"](stage)]
    schedule = set(product(cases, METHODS, range(warmups + measured)))
    samples = defaultdict(list)
    geometry = {}
    with data.open(encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle))
    for record in records:
        n, seed, round_id = (int(record[k]) for k in ("rows", "seed", "round"))
        case = n, record["distribution"], seed
        method = record["method"]
        ns, windows, switches, plan_bytes = (int(record[k]) for k in ("ns", "windows", "source_switches", "plan_bytes"))
        schedule.remove((case, method, round_id))
        geometry.setdefault(case, (windows, switches))
        if (record["verified"] != "true" or ns <= 0 or not 0 < 8 * windows <= n
                or not 0 <= switches < n or geometry[case] != (windows, switches)
                or plan_bytes != (4 * windows if method in REPLAYS else 0)):
            raise ValueError(f"invalid sample for {case} {method} round {round_id}")
        if round_id >= warmups:
            samples[case, method].append(ns)
    if schedule or len(records) != metadata["verified_calls"]:
        raise ValueError("incomplete measurement schedule")

    results = []
    for case in cases:
        medians = {name: median(samples[case, name]) for name in METHODS}
        best = min(REFERENCES, key=medians.__getitem__)
        results.append((case, medians, best, geometry[case]))
    return results, len(records)


def evaluate(results):
    primary = [row for row in results if row[0][:2] in DRIVER["PRIMARY"]]
    counts = {}
    worst = {}
    for method in CANDIDATES:
        counts[method] = sum(100 * times[method] <= 77 * times[best] for _, times, best, _ in primary)
        worst[method] = min(times[best] / times[method] for _, times, best, _ in primary)
    eligible = [method for method in CANDIDATES if counts[method] == len(primary)]
    selected = max(eligible, key=worst.get, default=None)
    return counts, len(primary), selected


def report(work, stage):
    results, count = read_stage(work, stage)
    print(f"{stage}: {count} verified calls including warm-ups")
    print("MiB | distribution | seed | " + " | ".join(METHODS) + " | best reference")
    for (n, shape, seed), medians, best, (windows, switches) in results:
        times = " | ".join(f"{medians[method] / 1e6:.3f}" for method in METHODS)
        print(f"{n * 64 // 2**20} | {shape} | {seed} | {times} | {best}")
        details = " / ".join(f"{medians[best] / medians[m]:.4f}x" for m in (*CANDIDATES, *REPLAYS))
        print(f"  {switches / (n - 1):.4%} source switches, {windows:,d} windows, {4 * windows:,d} plan bytes")
        print(f"  ratios against {best}: {details} (rank cached / stream / replay cached / stream)")

    counts, cases, selected = evaluate(results)
    if stage == "holdout":
        development, _ = read_stage(work, "development")
        _, _, frozen = evaluate(development)
        if frozen is None:
            raise ValueError("development did not qualify for holdout")
        print(f"Frozen {frozen} passed {counts[frozen]}/{cases} primary holdout cases")
    else:
        for method in CANDIDATES:
            print(f"{method} passed {counts[method]}/{cases} primary cases")
        print(f"Select for holdout: {selected or 'none'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=DRIVER["SEEDS"], default="development", nargs="?")
    parser.add_argument("--work", type=Path, default=HERE)
    args = parser.parse_args()
    report(args.work, args.stage)
