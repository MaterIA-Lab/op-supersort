"""Measure best possible tag counts within the registered 64-row blocks."""

import argparse
from collections import Counter
from itertools import islice
from pathlib import Path
from runpy import run_path


HERE = Path(__file__).resolve().parent
ANALYSIS = run_path(str(HERE / "analyze.py"))
MASK64 = (1 << 64) - 1


def splitmix64(seed):
    while True:
        seed = (seed + 0x9E3779B97F4A7C15) & MASK64
        value = ((seed ^ (seed >> 30)) * 0xBF58476D1CE4E5B9) & MASK64
        value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & MASK64
        yield value ^ (value >> 31)


def burst_keys(rows, seed):
    bursts = splitmix64(seed)
    noise = splitmix64(seed ^ 0xD1342543DE82EF95)
    while rows:
        length = min(rows, 96 + next(bursts) % 192)
        base = next(bursts) & ((1 << 32) - 1)
        for draw in islice(noise, length):
            yield draw >> 32 if draw & 7 == 0 else base
        rows -= length


def sample_key(block):
    middle = block[len(block) // 2]
    return middle if middle == block[-1] else block[0]


def geometry(rows, seed):
    keys = burst_keys(rows, seed)
    totals = Counter()
    for start in range(0, rows, 64):
        block = list(islice(keys, 64))
        freq = Counter(block)
        midpoint = len(block) // 2
        sampled = {sample_key(part) for part in (block[:midpoint], block[midpoint:]) if part}
        best = freq.most_common(2)
        totals["sampled_one"] += len(block) - freq[sample_key(block)] + 1
        totals["best_one"] += len(block) - best[0][1] + 1
        totals["sampled_two"] += len(block) - sum(freq[key] - 1 for key in sampled)
        totals["best_two"] += len(block) - sum(count - 1 for _, count in best)
    return totals


def report(work):
    results, _ = ANALYSIS["read_stage"](work, "development")
    print("MiB | seed | run tags | sampled one | best one | sampled two | best two | "
          "prepare + sort budget, ms | measured, ms")
    for (rows, shape, seed), stats, reference, _ in results:
        if shape != "burst_eighth":
            continue
        counts = geometry(rows, seed)
        variant = stats["mask_vq"]
        if counts["sampled_one"] != variant["tags"]:
            raise ValueError("geometry did not reproduce the measured tag count")
        budget = 0.77 * stats[reference]["total_ns"] - variant["output_ns"]
        plan = variant["prepare_ns"] + variant["sort_ns"]
        values = " | ".join(f"{counts[key]:,d}"
                            for key in ("sampled_one", "best_one", "sampled_two", "best_two"))
        print(f'{rows * 64 // 2**20} | {seed} | {stats["rle_vq"]["tags"]:,d} | {values} | '
              f"{budget / 1e6:.3f} | {plan / 1e6:.3f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, default=HERE)
    report(parser.parse_args().work)
