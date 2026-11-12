"""Build, run and archive the E056 binary-partition experiments in Ubuntu WSL."""

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import platform
import shutil
from statistics import median
import sys

from e045_cells import command_output, run_logged, sha256
from e046_windows import VENDORS, check_hashes, write_json, write_text


ROOT = Path(__file__).resolve().parent
N = 10_000_000
CPU = 2
REPEATS = 7
SEEDS = (42701, 91009)
HOLDOUT_SEEDS = (53309, 78041)
CASES = ("mixed", "uniform", "prefix_distinct", "dense16", "late_miss")
ARMS = ("binary", "split", "vq")
FULL_ARMS = (*ARMS, "simd", "ips2ra")
FIELDS = ("round", "algorithm", "ms", "route", "lower", "middle")
GOAL = 1.25


def archive_sources(out, full):
    sources = ("e056_binary.py", "e045_cells.py", "e046_windows.py", "e056_binary.cpp",
               "e056_vq_bridge.cpp", "include/supersort/windows_split_u32.hpp",
               "include/supersort/windows_compact_u32.hpp", "include/supersort/windows_u32.hpp")
    if full:
        sources = (*sources, "ips_bridge.cpp")
        shutil.copyfile(ROOT / "notes/E056 - Adenda confirmación.md", out / "confirmation.md")
    for name in sources:
        dest = out / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    shutil.copyfile(ROOT / "notes/E056 - Prerregistro dos particiones.md", out / "preregistration.md")
    vendor_names = tuple(VENDORS) if full else ("highway",)
    vendor_hashes = {}
    for name in vendor_names:
        pinned, source, license_name = VENDORS[name]
        repo = Path("vendor") / name
        git = ["git", "-C", str(repo)]
        if command_output([*git, "rev-parse", "HEAD"]) != pinned:
            raise RuntimeError(f"Unexpected {name} revision")
        if command_output([*git, "status", "--porcelain", "--untracked-files=all"]):
            raise RuntimeError(f"Modified {name} checkout")
        shutil.copytree(ROOT / repo / source, out / repo / source)
        shutil.copyfile(ROOT / repo / license_name, out / repo / license_name)
        vendor_hashes[name] = pinned
    hashes = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}
    return hashes, vendor_hashes


def build(out, full):
    sources, vendor_hashes = archive_sources(out, full)
    folder = out.relative_to(ROOT)
    vendor = folder / "vendor"
    highway = vendor / "highway"
    exe = folder / "e056_binary"
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", f"-I{highway}"]
    if full:
        command.extend(("-DSUPERSORT_E056_FULL", f"-I{vendor / 'ips2ra/include'}", f"-I{vendor / 'ips4o/include'}"))
    command.extend((str(folder / "e056_binary.cpp"), str(folder / "e056_vq_bridge.cpp"), str(highway / "hwy/abort.cc")))
    if full:
        command.extend((str(folder / "ips_bridge.cpp"), "-ltbb", "-latomic"))
    command.extend(("-pthread", "-o", str(exe)))
    run_logged(out, "build", command)
    check_hashes(out, sources)
    linkage = command_output(["ldd", str(exe)])
    write_text(out / "ldd.txt", linkage)
    libraries = {}
    for line in linkage.splitlines():
        if "=> not found" in line:
            raise RuntimeError(f"Unresolved dependency: {line.strip()}")
        path = line.split("=>", 1)[-1].strip().partition(" ")[0]
        if path.startswith("/"):
            libraries[path] = sha256(Path(path))
    return exe, {
        "flags": command,
        "compiler": command_output(["g++", "--version"]),
        "compiler_target": command_output(["g++", "-dumpmachine"]),
        "source_files_sha256": sources,
        "executable_sha256": sha256(ROOT / exe),
        "dynamic_library_sha256": libraries,
        "vendor": vendor_hashes,
    }


def verified_count(path):
    marker, _, count = path.read_text(encoding="utf-8").strip().partition(",")
    if marker != "verified" or not count.isdecimal() or int(count) <= 0:
        raise RuntimeError(f"Invalid verification marker in {path}")
    return int(count)


def read_case(path, arms=ARMS):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, fieldnames=FIELDS))
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise RuntimeError(f"Invalid driver columns in {path}")
    actual = Counter((int(row["round"]), row["algorithm"]) for row in rows)
    expected = Counter((round_, arm) for round_ in range(REPEATS) for arm in arms)
    if actual != expected:
        raise RuntimeError(f"Unexpected measurement counts in {path}")
    for row in rows:
        ms, lower, middle = float(row["ms"]), int(row["lower"]), int(row["middle"])
        route = row["route"]
        if not math.isfinite(ms) or ms <= 0 or min(lower, middle) < 0 or lower + middle > N:
            raise RuntimeError(f"Invalid measurement in {path}")
        if route not in ("vq", "window") or (route == "vq" and (lower or middle)):
            raise RuntimeError(f"Invalid route data in {path}")
        if row["algorithm"] in arms[2:] and route != "vq":
            raise RuntimeError(f"Unexpected route for a direct reference in {path}")
    return rows


def summarize(out, cases, verified, arms=ARMS):
    references = arms[2:]
    full = arms == FULL_ARMS
    labels = {"binary": "Binaria", "split": "E049", "vq": "Vqsort", "simd": "x86-simd-sort", "ips2ra": "IPS2Ra"}
    extra_titles = ["Mejor externa", "Mejor / binaria"] if full else []
    titles = ["Familia", "Semilla", *(labels[arm] for arm in arms),
              *(f"{labels[arm]} / binaria" for arm in arms[1:]), "Vqsort / E049", *extra_titles,
              "Ruta binaria", "Ruta E049"]
    lines = ["# E056 — Dos particiones binarias para la ventana", "",
             "Medianas en ms. La puerta se aplica a la mezcla 50/50 en cada semilla.", "",
             "| " + " | ".join(titles) + " |", "|" + "|".join(["---"] * len(titles)) + "|"]
    failures = []
    for (family, seed), rows in cases.items():
        by_arm = {arm: [row for row in rows if row["algorithm"] == arm] for arm in arms}
        times = {arm: median(float(row["ms"]) for row in group) for arm, group in by_arm.items()}
        ratios = {arm: times[arm] / times["binary"] for arm in arms[1:]}
        best = min(references, key=times.__getitem__)
        routes = {arm: {row["route"] for row in group} for arm, group in by_arm.items()}
        label = f"{family}/{seed}"
        if family == "mixed":
            if routes["binary"] != {"window"} or routes["split"] != {"window"}:
                failures.append(f"{label} registró respaldo en al menos un brazo con propuesta.")
            if ratios[best] < GOAL:
                failures.append(f"{label} alcanzó {ratios[best]:.6f} frente a {labels[best]}, por debajo de {GOAL}.")
            if ratios["split"] <= 1:
                failures.append(f"{label} alcanzó {ratios['split']:.6f} frente a E049, sin mejora.")
        medians = [f"{times[arm]:.6f}" for arm in arms]
        binary_ratios = [f"{ratios[arm]:.6f}" for arm in arms[1:]]
        extra = [labels[best], f"{ratios[best]:.6f}"] if full else []
        binary_routes = ", ".join(sorted(routes["binary"]))
        split_routes = ", ".join(sorted(routes["split"]))
        cells = [family, str(seed), *medians, *binary_ratios, f"{times['vq'] / times['split']:.6f}",
                 *extra, binary_routes, split_routes]
        lines.append("| " + " | ".join(cells) + " |")

    samples = sum(len(rows) for rows in cases.values())
    checked = samples + len(cases) * len(arms)
    verdict = "Puerta del filtro superada." if not failures else "Puerta del filtro fallida."
    counts = (f"{samples} muestras y {checked} salidas exactas con calentamientos. "
              f"{verified} comprobaciones previas.")
    lines.extend(("", verdict, ""))
    lines.extend(f"- {failure}" for failure in failures)
    lines.extend(("", counts))
    write_text(out / "summary.md", "\n".join(lines))
    write_json(out / "gate.json", {"passed": not failures, "failures": failures,
                                   "samples": samples, "checked": checked, "verified": verified})
    print(counts, flush=True)
    print(verdict, flush=True)


def execute(out, full):
    exe, evidence = build(out, full)
    arms = FULL_ARMS if full else ARMS
    matrix = [(family, seed) for family in CASES for seed in SEEDS]
    if full:
        matrix.extend(("mixed", seed) for seed in HOLDOUT_SEEDS)
    write_text(out / "lscpu.txt", command_output(["lscpu"]))
    write_json(out / "metadata.json", {
        **evidence,
        "utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "affinity": sorted(os.sched_getaffinity(0)),
        "page_size": os.sysconf("SC_PAGE_SIZE"),
        "matrix": {"n": N, "cases": matrix, "arms": arms, "repeats": REPEATS, "warmups": 1,
                   "holdout_seeds_mixed": HOLDOUT_SEEDS if full else ()},
        "timing": "Full sort including probe, reservations, release, final output and fallback. "
                  "Common input copy and exact std::sort verification outside.",
        "vq_dispatch": "Highway VQSortStatic native with paired initial pivot state per round",
        "other_reference_dispatch": ["x86simdsortStatic native", "ips2ra::sort sequential"] if full else [],
    })
    verified = verified_count(run_logged(out, "verify", [str(exe), "--verify"]))
    cases = {}
    with (out / "raw.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("n", "family", "seed", *FIELDS))
        writer.writeheader()
        for family, seed in matrix:
            path = run_logged(out, f"case-{N}-{family}-{seed}",
                              [str(exe), str(N), family, str(seed), str(REPEATS)])
            rows = read_case(path, arms)
            cases[family, seed] = rows
            writer.writerows(dict(row, n=N, family=family, seed=seed) for row in rows)
            stream.flush()

    check_hashes(out, evidence["source_files_sha256"])
    if sha256(ROOT / exe) != evidence["executable_sha256"]:
        raise RuntimeError("Executable changed during measurement")
    for path, digest in evidence["dynamic_library_sha256"].items():
        if sha256(Path(path)) != digest:
            raise RuntimeError(f"Dynamic dependency changed during measurement: {path}")
    summarize(out, cases, verified, arms)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="compare with all references and include mixed holdouts")
    args = parser.parse_args()
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        raise SystemExit("E056 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        raise SystemExit("E056 requires taskset -c 2")
    out = ROOT / "results" / ("e056_binary_full" if args.full else "e056_binary_filter")
    out.mkdir(exist_ok=False)
    try:
        execute(out, args.full)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
