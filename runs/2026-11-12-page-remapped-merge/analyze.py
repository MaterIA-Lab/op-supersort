import argparse
import csv
from itertools import product
from pathlib import Path
from statistics import median


MIB = 1 << 20
VOLUME = 128 * MIB
EXTENTS = (4096, 64 << 10, 2 * MIB, 16 * MIB, 128 * MIB)
SIZES = (1 << 20, 1 << 22)
LAYOUTS = ("adjacent", "edge_overlap", "bursty", "interleaved")
SEEDS = (271, 1601)
CANDIDATE_SEEDS = (104729, 130363)
FRESH_REFERENCES = ("scalar", "bulk", "hybrid")
CANDIDATE_METHODS = (*FRESH_REFERENCES, "hybrid_reused", "remap")


def read(path, keys, expected):
    samples = {}
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            row = {name: int(value) if name not in ("method", "layout") else value for name, value in row.items()}
            key = tuple(row[name] for name in keys)
            if (key in samples or row["warmup"] != (row["repetition"] == 0) or
                    min(row["assembly_ns"], row["scan_ns"]) <= 0 or
                    row["total_ns"] != row["assembly_ns"] + row["scan_ns"]):
                raise ValueError(f"invalid or duplicate sample {key}")
            samples[key] = row
    if samples.keys() != set(expected):
        raise ValueError(f"unexpected sample matrix in {path.name}")
    return samples


def summarize(directory):
    repetitions = range(1, 6)
    calibration = read(directory / "calibration.csv", ("bytes", "extent_bytes", "repetition", "method"),
                       product((VOLUME,), EXTENTS, range(6), ("copy", "map")))
    merge = read(directory / "merge.csv", ("records", "layout", "seed", "repetition", "method"),
                 product(SIZES, LAYOUTS, SEEDS, range(6), ("scalar", "bulk")))

    print("## Mapping versus copying 128 MiB\n")
    print("| Bytes per extent | Copy assembly (ms) | Map assembly (ms) | Copy scan (ms) | Map scan (ms) | Paired saving (ms) |")
    print("|---:|---:|---:|---:|---:|---:|")
    savings = []
    for extent in EXTENTS:
        copy, alias = ([calibration[VOLUME, extent, rep, method] for rep in repetitions] for method in ("copy", "map"))
        saving = median(a["total_ns"] - b["total_ns"] for a, b in zip(copy, alias))
        savings.append(max(saving, 0))
        phases = [median(row[key] for row in method) / 1e6 for key in ("assembly_ns", "scan_ns") for method in (copy, alias)]
        print(f"| {extent:,} | " + " | ".join(f"{value:.2f}" for value in phases) + f" | {saving / 1e6:.2f} |")

    print("\n## Merge coverage and optimistic speedup\n")
    print("| Records | Layout | Seed | Source pages | Mappable bytes | Mappable extents | Fastest reference (ms) | Estimated speedup |")
    print("|---:|---|---:|---:|---:|---:|---:|---:|")
    eligible_keys = tuple(f"eligible_{size}" for size in EXTENTS)
    passing = []
    for count, layout in product(SIZES, LAYOUTS):
        ratios = []
        for seed in SEEDS:
            data = [merge[count, layout, seed, rep, method] for rep, method in product(range(6), ("scalar", "bulk"))]
            geometry = {tuple(row[key] for key in ("source_aligned_bytes", "extents", *eligible_keys)) for row in data}
            if len(geometry) != 1:
                raise ValueError("geometry changed across repetitions")
            source, extents, *buckets = geometry.pop()
            mappable = sum(buckets)
            if not 0 <= mappable <= source <= count * 128 or bool(mappable) != bool(extents):
                raise ValueError("invalid page geometry")
            reference = median(min(merge[count, layout, seed, rep, method]["total_ns"] for method in ("scalar", "bulk"))
                               for rep in repetitions)
            estimated = reference - sum(volume * saved / VOLUME for volume, saved in zip(buckets, savings))
            ratio = reference / estimated if estimated > 0 else None
            ratios.append(ratio)
            formatted = f"{ratio:.3f}×" if ratio is not None else "invalid"
            print(f"| {count:,} | {layout} | {seed} | {source / (count * 128):.2%} | {mappable / (count * 128):.2%} | "
                  f"{extents:,} | {reference / 1e6:.2f} | {formatted} |")
        if layout in ("edge_overlap", "bursty") and all(ratio is not None and ratio >= 1.3 for ratio in ratios):
            passing.append((count, layout))
    print(f"\nNon-control cases clearing 1.3× on both seeds ({len(passing)}/4)")
    for count, layout in passing:
        print(f"- {count:,} records, {layout}")


def summarize_candidate(directory):
    data = read(directory / "candidate.csv", ("records", "layout", "seed", "repetition", "method"),
                product(SIZES, LAYOUTS, CANDIDATE_SEEDS, range(6), CANDIDATE_METHODS))
    print("| Records | Layout | Seed | Bytes mapped | Map calls | Fresh best (ms) | Reused (ms) | Remap (ms) | Remap teardown (ms) | Speedup vs fresh | Speedup vs reused |")
    print("|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    passing = {1.3: [], 1.5: []}
    for count, layout in product(SIZES, LAYOUTS):
        ratios = []
        for seed in CANDIDATE_SEEDS:
            rows = [data[count, layout, seed, rep, method] for rep, method in product(range(6), CANDIDATE_METHODS)]
            if any(row["teardown_ns"] <= 0 or
                   (row["method"] != "remap" and (row["mapped_bytes"] or row["map_calls"])) for row in rows):
                raise ValueError("invalid teardown or mapping counters")
            mapped, calls = {(row["mapped_bytes"], row["map_calls"]) for row in rows if row["method"] == "remap"}.pop()
            for rep in range(6):
                row = data[count, layout, seed, rep, "remap"]
                eligible = sum(row[f"eligible_{size}"] for size in EXTENTS if size >= 64 << 10)
                if (row["mapped_bytes"] != mapped or row["map_calls"] != calls or
                        mapped != eligible or not 0 <= calls <= row["extents"] or bool(mapped) != bool(calls)):
                    raise ValueError("mapping counters do not match eligible ranges")

            fresh, reused, remapped, teardown = [], [], [], []
            for rep in range(1, 6):
                fresh.append(min(data[count, layout, seed, rep, method]["total_ns"] for method in FRESH_REFERENCES))
                reused.append(data[count, layout, seed, rep, "hybrid_reused"]["total_ns"])
                row = data[count, layout, seed, rep, "remap"]
                remapped.append(row["total_ns"])
                teardown.append(row["teardown_ns"])
            fresh_ratio = median(a / b for a, b in zip(fresh, remapped))
            reused_ratio = median(a / b for a, b in zip(reused, remapped))
            ratios.append(fresh_ratio)
            medians = " | ".join(f"{median(values) / 1e6:.2f}" for values in (fresh, reused, remapped, teardown))
            print(f"| {count:,} | {layout} | {seed} | {mapped / (count * 128):.2%} | {calls:,} | {medians} | "
                  f"{fresh_ratio:.3f}× | {reused_ratio:.3f}× |")
        if layout in ("edge_overlap", "bursty"):
            for threshold in passing:
                if min(ratios) >= threshold:
                    passing[threshold].append((count, layout))
    for threshold, cases in passing.items():
        print(f"\nNon-control cases reaching {threshold}× against fresh output on both seeds ({len(cases)}/4)")
        for count, layout in cases:
            print(f"- {count:,} records, {layout}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate and summarize the page-remapped merge pilot.")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--candidate", action="store_true")
    args = parser.parse_args()
    if args.candidate:
        summarize_candidate(args.directory)
    else:
        summarize(args.directory)
