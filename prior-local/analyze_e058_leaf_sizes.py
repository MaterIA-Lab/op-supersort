"""Count small terminal spans from the archived E058 partition traces."""

import csv
import gzip
from pathlib import Path
from statistics import median
import sys


ROOT = Path(__file__).resolve().parent / "results/e058_vq_pairs"
LIMITS = (8, 16, 32, 64, 128)


def count(path):
    spans = dict.fromkeys(LIMITS, 0)
    keys = dict.fromkeys(LIMITS, 0)
    pairs32 = 0
    with gzip.open(path, "rt", encoding="ascii", newline="") as stream:
        for tag, *fields in csv.reader(stream):
            if tag != "partition":
                continue
            _, size, bound, *_ = map(int, fields)
            children = (bound, size - bound)
            if all(0 < child <= 32 for child in children):
                pairs32 += 1
            for child in children:
                for limit in LIMITS:
                    if 0 < child <= limit:
                        spans[limit] += 1
                        keys[limit] += child
    return [*spans.values(), *keys.values(), pairs32]


def main():
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["family", "seed", *(f"spans_le_{n}" for n in LIMITS),
                     *(f"keys_le_{n}" for n in LIMITS), "pairs_le_32"])
    for family in ("uniform", "prefix_distinct"):
        for seed in (42701, 91009):
            rows = [count(ROOT / f"{family}-{seed}-{round_}-trace.stdout.txt.gz") for round_ in range(7)]
            writer.writerow([family, seed, *(median(col) for col in zip(*rows))])


if __name__ == "__main__":
    main()
