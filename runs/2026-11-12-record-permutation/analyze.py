import argparse
import csv
from itertools import product
from pathlib import Path
from statistics import median


COUNTS = (1 << 20, 1 << 22)
WIDTHS = (64, 128)
DISTRIBUTIONS = ("uniform32", "low12")
SEEDS = (271, 1601)
METHODS = ("vq_gather", "x86_gather", "pdq_rows", "sequential_copy")


def read_samples(path):
    samples = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            repetition = int(row["repetition"])
            key = (int(row["n"]), int(row["record_bytes"]), row["distribution"],
                   int(row["seed"]), repetition, row["method"])
            times = tuple(int(row[f"{phase}_ns"]) for phase in ("total", "pack", "sort", "materialize"))
            if (key in samples or int(row["warmup"]) != (repetition == 0) or
                    min(times) < 0 or not times[0] or times[0] < sum(times[1:])):
                raise ValueError(f"invalid or duplicated sample {key}")
            samples[key] = times
    expected = set(product(COUNTS, WIDTHS, DISTRIBUTIONS, SEEDS, range(4), METHODS))
    if samples.keys() != expected:
        raise ValueError(f"expected {len(expected)} unique preregistered samples")
    return samples


def summarize(samples):
    passed = []
    print("| Records | Bytes per row | Keys | Seed | vq + gather | x86 + gather | pdqsort rows | Copy | Gather share (vq / x86) | Estimated speedup |")
    print("|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|")
    for case in product(COUNTS, WIDTHS, DISTRIBUTIONS):
        seed_ratios = []
        for seed in SEEDS:
            trials = [[samples[(*case, seed, rep, method)] for method in METHODS] for rep in range(1, 4)]
            totals = [median(trial[index][0] for trial in trials) / 1e6 for index in range(len(METHODS))]
            shares = [median(trial[index][3] / trial[index][0] for trial in trials) for index in (0, 1)]
            ratios = []
            for vq, x86, pdq, copy in trials:
                actual = min(vq[0], x86[0], pdq[0])
                estimate = min(sort[0] - sort[3] + copy[0] for sort in (vq, x86))
                ratios.append(actual / estimate)
            ratio = median(ratios)
            seed_ratios.append(ratio)
            times = " | ".join(f"{time:.2f}" for time in totals)
            print(f"| {case[0]:,} | {case[1]} | {case[2]} | {seed} | {times} | "
                  f"{shares[0]:.1%} / {shares[1]:.1%} | {ratio:.3f}× |")
        if min(seed_ratios) >= 1.3:
            passed.append(case)
    print(f"\nCases reaching the diagnostic threshold on both seeds ({len(passed)}/8)")
    for count, width, distribution in passed:
        print(f"- {count:,} records, {width} bytes, {distribution}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check the paired samples and summarize the pilot.")
    parser.add_argument("raw", type=Path)
    summarize(read_samples(parser.parse_args().raw))
