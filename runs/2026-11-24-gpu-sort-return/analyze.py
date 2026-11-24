"""Validate the raw GPU sort measurements and report the registered decision."""

import argparse
import csv
import json
from collections import defaultdict
from itertools import product
from pathlib import Path
from runpy import run_path
from statistics import median


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROBE = ROOT / "prototypes/agents/gpu-sort-return"
DRIVER = run_path(str(PROBE / "run.py"))
METHODS = ("raw", "raw_tiles", "prefix_serial", "prefix_overlap", "frame_serial", "frame_overlap")
CANDIDATE = "prefix_overlap"


def read_stage(directory, stage):
    path = directory / f"{stage}.csv"
    metadata = json.loads((directory / f"{stage}-metadata.json").read_text(encoding="utf-8"))
    digest = DRIVER["digest"]
    sources = (HERE / "protocol.md", PROBE / "bench.cu", PROBE / "run.py")
    source_hashes = {p.relative_to(ROOT).as_posix(): digest(p) for p in sources}
    if (metadata["stage"] != stage or digest(path) != metadata["raw_sha256"]
            or source_hashes != metadata["source_sha256"]):
        raise ValueError("measurement or source hashes do not match metadata")
    if stage == "holdout":
        development = json.loads((directory / "development-metadata.json").read_text(encoding="utf-8"))
        if metadata["binary_sha256"] != development["binary_sha256"]:
            raise ValueError("holdout used a different binary")

    with path.open(encoding="utf-8", newline="") as handle:
        records = list(csv.DictReader(handle))
    cases = DRIVER["PRIMARY"]
    if stage == "development":
        cases = (*cases, DRIVER["CONTROL"])
    expected = {(n, shape, seed, method, round_index)
                for (n, shape), seed, method, round_index
                in product(cases, DRIVER["SEEDS"][stage], METHODS, range(9))}
    groups = defaultdict(list)
    observed = set()
    for record in records:
        n, seed, round_index = (int(record[key]) for key in ("rows", "seed", "round"))
        shape, method = (record[key] for key in ("distribution", "method"))
        key = n, shape, seed, method, round_index
        observed.add(key)
        prefix_bytes = 2 * n + 65536 * 4
        frame_bytes = 2 * n + ((n + 127) // 128 + 4) * 4
        escape = int(record["escape_bytes"])
        planned = {"raw": 4 * n, "prefix": prefix_bytes, "frame": frame_bytes}
        expected_bytes = planned[method.split("_")[0]] + escape
        if (record["verified"] != "true" or int(record["total_ns"]) <= 0
                or int(record["return_bytes"]) != expected_bytes
                or int(record["prefix_scratch_each"]) != prefix_bytes
                or int(record["frame_scratch_each"]) != frame_bytes
                or not 0 <= escape <= 4 * n or escape % n
                or (escape > 0 and not method.startswith("frame"))):
            raise ValueError(f"invalid record {key}")
        if round_index >= 2:
            groups[n, shape, seed, method].append(record)
    if observed != expected or len(records) != len(expected) or len(records) != metadata["verified_calls"]:
        raise ValueError("incomplete or duplicate measurement schedule")
    return cases, groups, metadata


def report(directory, stage):
    cases, groups, metadata = read_stage(directory, stage)
    count = metadata["verified_calls"]
    print(f"{stage}: {count} verified calls ({sum(map(len, groups.values()))} measured after warm-up)")
    print("MiB input | shape | seed | " + " | ".join(METHODS) + " | best reference | ratio | raw ratio")
    results = []
    for (n, shape), seed in product(cases, DRIVER["SEEDS"][stage]):
        samples = {method: groups[n, shape, seed, method] for method in METHODS}
        times = {method: median(int(s["total_ns"]) for s in records)
                 for method, records in samples.items()}
        reference = min((m for m in METHODS if m != CANDIDATE), key=times.__getitem__)
        raw = min(("raw", "raw_tiles"), key=times.__getitem__)
        ratio = times[reference] / times[CANDIDATE]
        raw_ratio = times[raw] / times[CANDIDATE]
        if (n, shape) in DRIVER["PRIMARY"]:
            results.append(100 * times[CANDIDATE] <= 77 * times[reference])
        medians = " | ".join(f"{times[method] / 1e6:.3f}" for method in METHODS)
        print(f"{4 * n // 2**20} | {shape} | {seed} | {medians} | {reference} | {ratio:.4f} | {raw_ratio:.4f}")
        common_ms = median(float(s["upload_ms"]) + float(s["sort_ms"]) for s in samples[raw])
        bound = times[raw] / 1e6 / common_ms
        print(f"  Zero-return estimate for {raw}: {bound:.4f}x; common upload and sort: {common_ms:.3f} ms")
        packed_ms = median(float(s["encode_ms"]) + float(s["queued_return_ms"])
                           for s in samples["prefix_serial"])
        ideal_decode = times[raw] / 1e6 / (common_ms + packed_ms)
        print(f"  Free-decode estimate: {ideal_decode:.4f}x; prefix encode and serial return: {packed_ms:.3f} ms")
        for method, records in samples.items():
            phase = [median(float(s[key]) for s in records)
                     for key in ("upload_ms", "sort_ms", "encode_ms", "queued_return_ms")]
            decode = median(int(s["cpu_expand_ns"]) for s in records) / 1e6
            returned = median(int(s["return_bytes"]) for s in records)
            escaped = median(int(s["escape_bytes"]) for s in records)
            print(f"  {method:14s} {' / '.join(f'{ms:.3f}' for ms in (*phase, decode))} ms"
                  f" (upload / sort / encode / queued return / CPU expansion),"
                  f" {returned:,d} return bytes, {escaped:,d} escaped")
    print(f"Registered 77% gate: {sum(results)}/{len(results)} primary cases passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=DRIVER["SEEDS"], default="development", nargs="?")
    parser.add_argument("--work", type=Path, default=HERE)
    args = parser.parse_args()
    report(args.work, args.stage)
