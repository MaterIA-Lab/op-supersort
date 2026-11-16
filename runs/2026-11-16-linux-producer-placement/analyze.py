"""Check raw Linux samples and compare the four preregistered holdout pairs."""

import argparse
from pathlib import Path
from runpy import run_path


COMMON = run_path(
    str(Path(__file__).resolve().parents[1] / "2026-11-16-producer-page-placement" / "analyze.py")
)
REFERENCES = COMMON["REFERENCES"]
MAPPING_METHODS = (*COMMON["MAPPINGS"], "shifted_populated")
HOLDOUT = {
    ("edge_2pct", half + left, half + right, seed)
    for half in (2 ** 19, 2 ** 20)
    for left, right, seed in ((7, 11, 1_907_348_639), (27, -4, 185_028_962))
}


def compare(path):
    cases = COMMON["load"](path, COMMON["registered_cases"]() | HOLDOUT, MAPPING_METHODS)
    passed = dict.fromkeys(MAPPING_METHODS, 0)
    print(f"Input {path.name}")
    print("Layout, rows, seed, cohort, best direct, mapping method, reference ms, "
          "create ms, map-and-copy ms, first read ms, total ms, release ms, reuse %, speedup")
    for case, methods in cases.items():
        layout, left, right, seed = case
        median = COMMON["measured_medians"](methods)
        reference = min(REFERENCES, key=lambda method: median[method]["total_ns"])
        direct = median[reference]["total_ns"]
        cohort = "holdout" if case in HOLDOUT else "control"
        if median["shifted_remap"]["mapped_bytes"] != median["shifted_populated"]["mapped_bytes"]:
            raise ValueError(f"the population flag changed page coverage in {case}")
        for method in MAPPING_METHODS:
            m = median[method]
            if case in HOLDOUT and m["total_ns"] * 100 <= direct * 77:
                passed[method] += 1
            phases = ", ".join(f"{m[phase] / 1e6:.3f}" for phase in COMMON["PHASES"])
            reused = 100 * m["mapped_bytes"] / ((left + right) * COMMON["ROW_BYTES"])
            print(f"{layout}, {left + right}, {seed}, {cohort}, {reference}, {method}, "
                  f"{direct / 1e6:.3f}, {phases}, {reused:.3f}, {direct / m['total_ns']:.3f}")
    print("Verified 360 timed trials and 72 warm-ups.")
    print("Passing holdout cases:", ", ".join(f"{name} {count}/4" for name, count in passed.items()))
    return passed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path, nargs="+")
    args = parser.parse_args()
    hosts = [compare(path) for path in args.csv]
    if len(hosts) == 2:
        keep = [method for method in MAPPING_METHODS[1:] if all(m[method] == 4 for m in hosts)]
        print("Shifted methods clearing the complete two-host gate:", ", ".join(keep) or "none")


if __name__ == "__main__":
    main()
