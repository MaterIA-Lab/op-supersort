"""Verify the stable-sort measurements and compute the registered decision."""

import argparse
import csv
import json
from collections import defaultdict
from itertools import product
from pathlib import Path
from runpy import run_path
from statistics import median


HERE = Path(__file__).resolve().parent
DRIVER = run_path(str(HERE.parents[1] / "prototypes/agents/exception-mask-sort/run.py"))
METHODS = DRIVER["METHODS"]
REFERENCES = DRIVER["REFERENCES"]
CANDIDATES = DRIVER["CANDIDATES"]


def read_stage(directory, stage):
    path = directory / f"{stage}.csv"
    meta = json.loads((directory / f"{stage}-metadata.json").read_text(encoding="utf-8"))
    warmups, rounds = DRIVER["WARMUPS"], DRIVER["ROUNDS"]
    if (meta["stage"] != stage or meta["raw_sha256"] != DRIVER["digest"](path)
            or meta["source_sha256"] != DRIVER["source_hashes"]()
            or meta["highway_commit"] != DRIVER["HIGHWAY"]
            or (meta["warmups"], meta["measured_calls_per_method"]) != (warmups, rounds)):
        raise ValueError("sample or build metadata mismatch")
    if stage == "holdout":
        dev = json.loads((directory / "development-metadata.json").read_text(encoding="utf-8"))
        if (meta["binary_sha256"], meta["logical_cpu"]) != (dev["binary_sha256"], dev["logical_cpu"]):
            raise ValueError("holdout build or affinity did not match")

    cases = [(n, shape, seed) for (n, shape), seed in DRIVER["cases"](stage)]
    pending = set(product(cases, METHODS, range(warmups + rounds)))
    grouped = defaultdict(list)
    geometry, tag_counts = {}, {}
    with path.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for row in rows:
        n, seed, round_id = (int(row[key]) for key in ("rows", "seed", "round"))
        case = n, row["shape"], seed
        method = row["method"]
        pending.remove((case, method, round_id))
        tags, copies, adjacent = (int(row[key]) for key in ("tags", "copy_spans", "same_neighbors"))
        ns, prepare, sort, write = (int(row[key]) for key in ("total_ns", "prepare_ns", "sort_ns", "output_ns"))
        kind = method.split("_")[0]
        geometry.setdefault(case, (copies, adjacent))
        tag_counts.setdefault((case, kind), tags)
        if (row["verified"] != "true" or not 0 <= prepare + sort + write <= ns or ns <= 0
                or not 0 < copies <= n or not 0 <= adjacent < n or not 0 < tags <= n
                or (kind == "row" and tags != n) or (kind == "rle" and tags != n - adjacent)
                or (kind == "mask" and tags < (n + 63) // 64) or int(row["scratch_bytes"]) < 8 * tags
                or geometry[case] != (copies, adjacent) or tag_counts[case, kind] != tags):
            raise ValueError(f"invalid recorded sample {case} {method} round {round_id}")
        if round_id >= warmups:
            grouped[case, method].append(row)
    if pending or meta["verified_calls"] != len(rows):
        raise ValueError("incomplete measurement schedule")

    results = []
    for case in cases:
        stats = {
            method: {key: median(int(row[key]) for row in grouped[case, method])
                     for key in ("total_ns", "prepare_ns", "sort_ns", "output_ns", "tags", "scratch_bytes")}
            for method in METHODS
        }
        best = min(REFERENCES, key=lambda m: stats[m]["total_ns"])
        results.append((case, stats, best, geometry[case]))
    return results, len(rows)


def gate(results):
    primary = [row for row in results if row[0][:2] in DRIVER["PRIMARY"]]
    counts = {
        m: sum(100 * s[m]["total_ns"] <= 77 * s[b]["total_ns"] for _, s, b, _ in primary)
        for m in CANDIDATES
    }
    eligible = [m for m in CANDIDATES if counts[m] == len(primary)]
    selected = max(eligible, default=None,
                   key=lambda m: min(s[b]["total_ns"] / s[m]["total_ns"] for _, s, b, _ in primary))
    return counts, len(primary), selected


def report(directory, stage):
    results, count = read_stage(directory, stage)
    print(f"{stage}: {count} verified calls including warm-ups")
    print("MiB | shape | seed | " + " | ".join(METHODS) + " | best reference | mask_vq | mask_radix")
    for (n, shape, seed), stats, best, (copies, adjacent) in results:
        times = " | ".join(f'{stats[m]["total_ns"] / 1e6:.3f}' for m in METHODS)
        reference = stats[best]["total_ns"]
        ratios = " | ".join(f'{reference / stats[m]["total_ns"]:.4f}x' for m in CANDIDATES)
        print(f"{n * 64 // 2**20} | {shape} | {seed} | {times} | {best} | {ratios}")
        print(f"  {copies:,d} copy spans, {adjacent / (n - 1):.4%} adjacent equal keys")
        for method in METHODS:
            m = stats[method]
            phases = " / ".join(f"{m[key] / 1e6:.3f}" for key in ("prepare_ns", "sort_ns", "output_ns"))
            print(f'  {method:12s} {m["tags"]:,d} tags; {phases} ms (prepare / sort / output);'
                  f' {m["scratch_bytes"]:,d} bytes of requested heap capacity')
    counts, n_cases, selected = gate(results)
    if stage == "holdout":
        development, _ = read_stage(directory, "development")
        frozen = gate(development)[2]
        if frozen is None:
            raise ValueError("development did not qualify for holdout")
        print(f"Frozen {frozen} passed {counts[frozen]}/{n_cases} holdout cases")
    else:
        for method in CANDIDATES:
            print(f"{method} passed {counts[method]}/{n_cases} primary cases")
        print(f"Select for holdout: {selected or 'none'}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=DRIVER["SEEDS"], default="development", nargs="?")
    parser.add_argument("--work", type=Path, default=HERE)
    args = parser.parse_args()
    report(args.work, args.stage)
