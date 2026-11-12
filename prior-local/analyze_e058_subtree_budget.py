"""Sum normal partition times below candidate subtree cutoffs in E058."""

import csv
import gzip
from pathlib import Path
from statistics import median
import sys


ROOT = Path(__file__).resolve().parent / "results/e058_vq_pairs"
LIMITS = (256, 512, 1024, 2048)


def run_totals(path):
    clocks, partitions = [], []
    with gzip.open(path, "rt", encoding="ascii", newline="") as stream:
        for tag, *fields in csv.reader(stream):
            if tag == "clock":
                clocks.append(int(fields[0]))
            elif tag == "partition":
                partitions.append((int(fields[1]), int(fields[-1])))
    clock = median(clocks)
    return [sum(max(0, ns - clock) for size, ns in partitions if size <= limit) / 1e6
            for limit in LIMITS]


def main():
    writer = csv.writer(sys.stdout, lineterminator="\n")
    writer.writerow(["family", "seed", *(f"partition_ms_le_{limit}" for limit in LIMITS)])
    for family in ("uniform", "prefix_distinct"):
        for seed in (42701, 91009):
            totals = [run_totals(ROOT / f"{family}-{seed}-{round_}-trace.stdout.txt.gz")
                      for round_ in range(7)]
            writer.writerow([family, seed, *(f"{median(col):.3f}" for col in zip(*totals))])


if __name__ == "__main__":
    main()
