import csv
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median


METHODS = {"memcpy32", "stream32", "memcpy24", "stream24", "pack", "unpack"}
CASES = {
    (keys, workers, seed)
    for keys, worker_counts in [(2**24, (1, 4, 8)), (2**26, (4, 8))]
    for workers in worker_counts
    for seed in (104729, 130363)
}


def analyze(path):
    trials = defaultdict(lambda: defaultdict(dict))
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            case = tuple(int(row[field]) for field in ("keys", "workers", "seed"))
            methods = trials[case][int(row["round"])]
            method = row["method"]
            elapsed = float(row["ms"])
            if row["verified"] != "1" or method in methods or not 0 < elapsed < float("inf"):
                raise ValueError(f"Invalid measurement: {row}")
            methods[method] = elapsed

    if trials.keys() != CASES:
        raise ValueError("Measurements do not cover the preregistered cases")

    print("| Keys | Workers | Seed | memcpy32 | stream32 | memcpy24 | stream24 | Pack | Unpack | Internal only | One interior | Two interior |")
    print("|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    primary = []
    for (keys, workers, seed), rounds in sorted(trials.items()):
        if rounds.keys() != set(range(8)) or any(values.keys() != METHODS for values in rounds.values()):
            raise ValueError(f"Incomplete rounds: {(keys, workers, seed)}")
        times = {method: median(rounds[i][method] for i in range(1, 8)) for method in METHODS}
        c32 = min(times["memcpy32"], times["stream32"])
        c24 = min(times["memcpy24"], times["stream24"])
        bookends = times["pack"] + times["unpack"]
        one = 3 * c32 / (bookends + c24)
        two = 4 * c32 / (bookends + 2 * c24)
        formatted = " | ".join(f"{times[method]:.3f}" for method in (
            "memcpy32", "stream32", "memcpy24", "stream24", "pack", "unpack"))
        print(f"| {keys:,} | {workers} | {seed} | {formatted} | {c32 / c24:.3f}x | {one:.3f}x | {two:.3f}x |")
        if workers == 8:
            primary.append(two)
    print(f"\nPrimary cases at or above 1.30x: {sum(ratio >= 1.30 for ratio in primary)}/{len(primary)}.")
    print(f"Primary two-interior range: {min(primary):.3f}-{max(primary):.3f}x.")
    print(f"Validated {len(CASES) * 7 * len(METHODS)} measured and {len(CASES) * len(METHODS)} warm-up outputs.")


if __name__ == "__main__":
    analyze(Path(sys.argv[1]))
