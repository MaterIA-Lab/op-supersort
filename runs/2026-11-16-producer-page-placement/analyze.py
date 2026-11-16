"""Validate the registered matrix and summarize median end-to-end times."""

import argparse
from collections import defaultdict
import csv
from pathlib import Path
from statistics import median


REFERENCES = ("split_bulk", "fused_cached", "fused_stream")
MAPPINGS = ("fixed_remap", "shifted_remap")
PHASES = ("batches_ns", "assembly_ns", "read_ns", "total_ns", "teardown_ns")
ROW_BYTES = 128


def registered_cases():
    return {
        (layout, half + a, half + b, seed)
        for layout in ("edge_2pct", "disjoint", "interleaved")
        for half in ((2 ** 19, 2 ** 20) if layout == "edge_2pct" else (2 ** 19,))
        for a, b, seed in ((13, -1, 4_316_079), (19, 4, 99_237_281))
    }


def load(path, expected_cases=None, mapping_methods=MAPPINGS):
    cases = defaultdict(lambda: defaultdict(dict))
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            case = (row["layout"], int(row["left_rows"]), int(row["right_rows"]), int(row["seed"]))
            method = row["method"]
            round_number = int(row["round"])
            rounds = cases[case][method]
            if round_number in rounds:
                raise ValueError(f"duplicate sample for {case}, {method}, {round_number}")
            record = {name: int(row[name]) for name in (*PHASES, "mapped_bytes", "overlap_rows")}
            if any(value < 0 for value in record.values()):
                raise ValueError(f"negative measurement for {case}, {method}")
            if sum(record[phase] for phase in PHASES[:3]) != record["total_ns"]:
                raise ValueError(f"timing phases do not add up for {case}, {method}")
            if record["mapped_bytes"] % 4096 or record["mapped_bytes"] > sum(case[1:3]) * ROW_BYTES:
                raise ValueError(f"invalid mapped byte count for {case}, {method}")
            if method in REFERENCES and record["mapped_bytes"]:
                raise ValueError(f"direct writer reported a mapping for {case}, {method}")
            if record["overlap_rows"] > sum(case[1:3]):
                raise ValueError(f"invalid overlap count for {case}, {method}")
            rounds[round_number] = record

    if expected_cases is None:
        expected_cases = registered_cases()
    if cases.keys() != expected_cases:
        raise ValueError("the input does not match the registered workload")
    expected_methods = set(REFERENCES + mapping_methods)
    for case, methods in cases.items():
        if methods.keys() != expected_methods:
            raise ValueError(f"missing method in {case}")
        for method, rounds in methods.items():
            if rounds.keys() != set(range(6)):
                raise ValueError(f"incomplete rounds for {case}, {method}")
            if len({record["mapped_bytes"] for record in rounds.values()}) != 1:
                raise ValueError(f"inconsistent mapping for {case}, {method}")
        for method in mapping_methods[1:]:
            if methods["fixed_remap"][0]["mapped_bytes"] > methods[method][0]["mapped_bytes"]:
                raise ValueError(f"adjusted placement reduced coverage in {case}, {method}")
        overlap_counts = {
            record["overlap_rows"] for rounds in methods.values() for record in rounds.values()
        }
        if len(overlap_counts) != 1:
            raise ValueError(f"inconsistent overlap in {case}")
    return cases


def measured_medians(methods):
    return {
        method: {
            **{phase: median(rounds[i][phase] for i in range(1, 6)) for phase in PHASES},
            "with_teardown": median(
                rounds[i]["total_ns"] + rounds[i]["teardown_ns"] for i in range(1, 6)
            ),
            "mapped_bytes": rounds[0]["mapped_bytes"],
            "overlap_rows": rounds[0]["overlap_rows"],
        }
        for method, rounds in methods.items()
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    args = parser.parse_args()
    cases = load(args.csv)
    passed = 0
    print("Case, seed, method, batch ms, assembly ms, first read ms, total ms, "
          "total + teardown ms, mapped %, overlap %, fastest direct / method")
    for (layout, left, right, seed), methods in cases.items():
        result = measured_medians(methods)
        fastest = min(REFERENCES, key=lambda method: result[method]["total_ns"])
        reference = result[fastest]["total_ns"]
        shifted_time = result["shifted_remap"]["total_ns"]
        if layout == "edge_2pct":
            passed += 100 * shifted_time <= 77 * reference
        for method in (*REFERENCES, *MAPPINGS):
            med = result[method]
            timing = ", ".join(f"{med[key] / 1e6:.3f}" for key in (*PHASES[:4], "with_teardown"))
            coverage = 100 * med["mapped_bytes"] / ((left + right) * ROW_BYTES)
            overlap = 100 * med["overlap_rows"] / (left + right)
            print(f"{layout} {left + right:,}, {seed}, {method}, {timing}, "
                  f"{coverage:.3f}, {overlap:.3f}, {reference / med['total_ns']:.3f}")
    print(f"Advanced primary cases: {passed}/4. Verified 200 measured samples and 40 warm-ups.")


if __name__ == "__main__":
    main()
