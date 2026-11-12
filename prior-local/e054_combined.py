"""Archive and run E054 against the pinned full-sort references in Ubuntu WSL."""

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import sys

from e045_cells import command_output, run_logged, sha256
from e046_windows import VENDORS, check_hashes, write_json, write_text


ROOT = Path(__file__).resolve().parent
REGISTRATION = ROOT / "notes/E054 - Prerregistro compuesto con diccionario.md"
CPU = 2
N = 10_000_000
SEEDS = (42701, 91009)
REPEATS = 7
REFERENCES = ("vq", "simd", "ips2ra")
ALGORITHMS = ("combined", "e047", "striped", *REFERENCES)
WORK_FIELDS = ("route", "examined", "proposals")
DRIVER_FIELDS = ("repeat", "algorithm", "ms", *WORK_FIELDS)
RAW_FIELDS = ("n", "distribution", "seed", *DRIVER_FIELDS)
PRIMARY = ("uniform", "prefix_distinct", "dense16", "skew", "mixed", "bimodal", "few",
           "few_permute", "few_dominant", "few_powers", "equal")
ADVERSARIES = ("early_unknown", "late_unknown", "late_reject")
SECONDARY = ("near_sorted",)
CASES = (*PRIMARY, *ADVERSARIES, *SECONDARY)
DICTIONARY_TARGETS = ("few", "few_permute")
GOAL = 1.25


def archive_sources(out):
    for name in ("e054_combined.py", "e045_cells.py", "e046_windows.py", "e053_dictionary.cpp",
                 "e047_vq_bridge.cpp", "ips_bridge.cpp", "include/supersort/dictionary_u32.hpp",
                 "include/supersort/combined_u32.hpp", "include/supersort/windows_e047_u32.hpp",
                 "include/supersort/windows_u32.hpp"):
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copyfile(REGISTRATION, out / "preregistration.md")
    for name, (commit, source_dir, license_name) in VENDORS.items():
        repo = Path("vendor") / name
        git = ["git", "-C", str(repo)]
        actual = command_output([*git, "rev-parse", "HEAD"])
        if actual != commit:
            raise RuntimeError(f"Unexpected commit for {name}: {actual}")
        dirty = command_output([*git, "status", "--porcelain", "--untracked-files=all"])
        if dirty:
            raise RuntimeError(f"Vendored sources differ from pinned {name}:\n{dirty}")
        shutil.copytree(ROOT / repo / source_dir, out / repo / source_dir)
        shutil.copyfile(ROOT / repo / license_name, out / repo / license_name)
    return {path.relative_to(out).as_posix(): sha256(path)
            for path in sorted(out.rglob("*")) if path.is_file()}


def build(out):
    source_hashes = archive_sources(out)
    archive = out.relative_to(ROOT)
    executable = archive / "e054_combined"
    vendor = archive / "vendor"
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", "-DSUPERSORT_E054",
               f"-I{vendor / 'highway'}", f"-I{vendor / 'ips2ra/include'}", f"-I{vendor / 'ips4o/include'}",
               str(archive / "e053_dictionary.cpp"), str(archive / "e047_vq_bridge.cpp"),
               str(archive / "ips_bridge.cpp"), str(vendor / "highway/hwy/abort.cc"),
               "-ltbb", "-latomic", "-pthread", "-o", str(executable)]
    run_logged(out, "build", command)
    check_hashes(out, source_hashes)
    linkage = command_output(["ldd", str(executable)])
    write_text(out / "ldd.txt", linkage)
    library_hashes = {}
    for line in linkage.splitlines():
        if "=> not found" in line:
            raise RuntimeError(f"Unresolved runtime dependency: {line.strip()}")
        library = line.split("=>", 1)[-1].strip().split(maxsplit=1)[0]
        if library.startswith("/"):
            library_hashes[library] = sha256(Path(library))
    return executable, {
        "flags": command,
        "compiler": command_output(["g++", "--version"]),
        "compiler_target": command_output(["g++", "-dumpmachine"]),
        "executable": executable.as_posix(),
        "executable_sha256": sha256(ROOT / executable),
        "source_files_sha256": source_hashes,
        "dynamic_library_sha256": library_hashes,
        "vendor": {name: spec[0] for name, spec in VENDORS.items()},
        "dispatch": "Highway VQSortStatic native, x86simdsortStatic native, ips2ra::sort sequential",
    }


def read_case(path):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, fieldnames=DRIVER_FIELDS))
    work = {alg: set() for alg in ALGORITHMS}
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise RuntimeError(f"Invalid driver columns in {path}")
        ms = float(row["ms"])
        if not math.isfinite(ms) or ms <= 0:
            raise RuntimeError(f"Invalid measured time in {path}")
        route = row["route"]
        examined, proposals = (int(row[key]) for key in WORK_FIELDS[1:])
        if not route or not 0 <= examined <= N or not 0 <= proposals <= 256:
            raise RuntimeError(f"Invalid route or counters in {path}")
        algorithm = row["algorithm"]
        if algorithm not in work:
            raise RuntimeError(f"Unexpected algorithm in {path}")
        if algorithm in REFERENCES and (route, examined, proposals) != ("bypass", 0, 0):
            raise RuntimeError(f"Unexpected route for a direct external reference in {path}")
        work[algorithm].add((route, examined, proposals))
    actual = Counter((int(row["repeat"]), row["algorithm"]) for row in rows)
    expected = Counter((rep, alg) for rep in range(REPEATS) for alg in ALGORITHMS)
    if actual != expected or any(len(values) != 1 for values in work.values()):
        raise RuntimeError(f"Unexpected measurement counts or changing route telemetry in {path}")
    return rows, {alg: values.pop() for alg, values in work.items()}


def analyze(out, cases, verified):
    headings = ["| Familia | Semilla | Compuesto, ms | E047, ms | Striped, ms | Vqsort, ms | "
                "SIMD, ms | IPS2Ra, ms | Mejor externa | Mejor / compuesto | E047 / compuesto | "
                "Striped / compuesto | Ruta (examinadas, propuestas) | Meta |",
                "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---|---|"]
    rows_by_case = {}
    target_failures = []
    goal_failures = []
    losses = []
    wins = Counter()
    sample_count = 0
    for (dist, seed), (rows, work) in cases.items():
        sample_count += len(rows)
        medians = {alg: statistics.median(float(row["ms"]) for row in rows
                                         if row["algorithm"] == alg) for alg in ALGORITHMS}
        ratios = {alg: medians[alg] / medians["combined"] for alg in ALGORITHMS[1:]}
        best = min(REFERENCES, key=medians.__getitem__)
        best_ratio = ratios[best]
        route, examined, proposals = work["combined"]
        label = f"{dist}/{seed}"
        passed = best_ratio >= GOAL
        if dist in PRIMARY and not passed:
            goal_failures.append(f"{label} obtuvo {best_ratio:.6f} frente a {best}, por debajo de 1,25.")
        if dist in DICTIONARY_TARGETS and (route != "dict_counted" or not passed):
            target_failures.append(f"{label} registró ruta {route} y razón {best_ratio:.6f} frente a {best}.")
        below = [f"{alg} ({ratio:.6f})" for alg, ratio in ratios.items() if ratio < 1.0]
        if below:
            losses.append(f"{label} perdió frente a {', '.join(below)}.")
        wins.update(alg for alg, ratio in ratios.items() if ratio > 1.0)
        wins["best_external"] += best_ratio > 1.0
        values = " | ".join(f"{medians[alg]:.6f}" for alg in ALGORITHMS)
        status = ("Pasa" if passed else "Falla") if dist in PRIMARY else "Control"
        rows_by_case[dist, seed] = (f"| {dist} | {seed} | {values} | {best} | {best_ratio:.6f} | "
                                   f"{ratios['e047']:.6f} | {ratios['striped']:.6f} | "
                                   f"{route} ({examined}, {proposals}) | {status} |")

    gate = {"passed": not (target_failures or goal_failures),
            "dictionary_coverage_passed": not target_failures, "general_goal_passed": not goal_failures,
            "dictionary_coverage_failures": target_failures, "general_goal_failures": goal_failures,
            "wins": dict(wins)}
    write_json(out / "gate.json", gate)
    lines = ["# E054 — Comparación completa del compuesto", "",
             "Las razones dividen la mediana de la referencia por la del compuesto. "
             "La mejor externa se elige entre vqsort, x86-simd-sort e IPS2Ra.", ""]
    for title, dists in (("Matriz principal", PRIMARY), ("Adversarios de rechazo", ADVERSARIES),
                         ("Control casi ordenado", SECONDARY)):
        lines.extend((f"## {title}", "", *headings,
                      *(rows_by_case[dist, seed] for dist in dists for seed in SEEDS), ""))
    main_count = len(PRIMARY) * len(SEEDS)
    lines.extend((f"Meta de 1,25× en {main_count - len(goal_failures)}/{main_count} casos principales.",
                  f"Cobertura del diccionario {'superada' if not target_failures else 'fallida'}.",
                  f"Menor mediana que la mejor externa en {wins['best_external']}/{len(cases)} casos totales."))
    if target_failures:
        lines.extend(("", "## Incumplimientos de cobertura del diccionario", "",
                      *(f"- {failure}" for failure in target_failures)))
    if goal_failures:
        lines.extend(("", "## Incumplimientos de la meta general", "",
                      *(f"- {failure}" for failure in goal_failures)))
    if losses:
        lines.extend(("", "## Pérdidas del compuesto", "", *(f"- {loss}" for loss in losses)))
    checked = sample_count + len(cases) * len(ALGORITHMS)
    lines.extend(("", f"{sample_count} muestras y {checked} salidas exactas con calentamientos. "
                  f"{verified} comprobaciones previas de correctitud."))
    write_text(out / "summary.md", "\n".join(lines))
    print(lines[-1], flush=True)
    print((out / "gate.json").read_text(encoding="utf-8"), flush=True)


def execute(out):
    executable, build_metadata = build(out)
    write_text(out / "lscpu.txt", command_output(["lscpu"]))
    write_json(out / "metadata.json", {
        **build_metadata,
        "utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "logical_cpu": CPU,
        "affinity": sorted(os.sched_getaffinity(0)),
        "stage": "E054",
        "matrix": {"n": N, "cases": CASES, "seeds": SEEDS, "algorithms": ALGORITHMS,
                   "repeats": REPEATS, "warmups": 1},
        "vq_pivot_state": "library default",
        "timing": "Full sort, including detection, buffers, copies, reconstruction and fallback. "
                  "Common input copy and exact std::sort verification outside.",
    })
    verification = run_logged(out, "verify", [str(executable), "--verify"])
    marker, _, count = verification.read_text(encoding="utf-8").strip().partition(",")
    if marker != "verified" or not count.isascii() or not count.isdecimal() or int(count) <= 0:
        raise RuntimeError("Invalid correctness verification marker")

    cases = {}
    with (out / "raw.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RAW_FIELDS)
        writer.writeheader()
        for dist in CASES:
            for seed in SEEDS:
                path = run_logged(out, f"case-{N}-{dist}-{seed}",
                                  [str(executable), str(N), dist, str(seed), str(REPEATS)])
                rows, work = read_case(path)
                cases[dist, seed] = rows, work
                writer.writerows(dict(row, n=N, distribution=dist, seed=seed) for row in rows)
                stream.flush()
    check_hashes(out, build_metadata["source_files_sha256"])
    if sha256(ROOT / executable) != build_metadata["executable_sha256"]:
        raise RuntimeError("Executable changed during measurement")
    for name, digest in build_metadata["dynamic_library_sha256"].items():
        if sha256(Path(name)) != digest:
            raise RuntimeError(f"Dynamic dependency changed during measurement: {name}")
    analyze(out, cases, int(count))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        parser.error("E054 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        parser.error("E054 requires taskset -c 2")
    out = ROOT / "results/e054_combined_full"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
