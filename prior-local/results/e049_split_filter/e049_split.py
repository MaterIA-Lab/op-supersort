"""Archive and run the E049 in-place split contrast in Ubuntu WSL."""

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

from e045_cells import HIGHWAY, HIGHWAY_COMMIT, command_output, run_logged, sha256
from e046_windows import check_hashes, write_json, write_text


ROOT = Path(__file__).resolve().parent
REGISTRATION = ROOT / "notes/E049 - Prerregistro separación in situ.md"
CPU = 2
N = 10_000_000
SEEDS = (28729, 80149)
REPEATS = 7
ALGORITHMS = ("scalar_scratch", "compact_scratch", "split", "vq")
DRIVER_FIELDS = ("repeat", "algorithm", "ms", "low", "inside", "high")
RAW_FIELDS = ("n", "distribution", "seed", *DRIVER_FIELDS)
# Exterior cardinality, gate reference and minimum reference/split ratio.
CASES = {
    "half_grouped": (N // 2, "vq", 0.90),
    "half_periodic": (N // 2, "vq", 0.90),
    "half_random": (N // 2, "vq", 1.10),
    "skew_random": (N // 20, "scalar_scratch", 0.90),
    "half_low": (N // 2, "vq", 0.90),
    "half_high": (N // 2, "vq", 0.90),
}


def archive_sources(out):
    git = ["git", "-C", str(HIGHWAY)]
    commit = command_output([*git, "rev-parse", "HEAD"])
    if commit != HIGHWAY_COMMIT:
        raise RuntimeError(f"Unexpected Highway commit: {commit}")
    dirty = command_output([*git, "status", "--porcelain", "--untracked-files=all"])
    if dirty:
        raise RuntimeError(f"Highway sources differ from the pinned tree:\n{dirty}")

    for name in ("e049_split.py", "e045_cells.py", "e046_windows.py", "e049_split.cpp",
                 "e047_vq_bridge.cpp", "include/supersort/windows_u32.hpp",
                 "include/supersort/windows_compact_u32.hpp",
                 "include/supersort/windows_split_u32.hpp"):
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copyfile(REGISTRATION, out / "preregistration.md")
    shutil.copytree(ROOT / HIGHWAY / "hwy", out / HIGHWAY / "hwy")
    shutil.copyfile(ROOT / HIGHWAY / "LICENSE", out / HIGHWAY / "LICENSE")
    return {path.relative_to(out).as_posix(): sha256(path)
            for path in sorted(out.rglob("*")) if path.is_file()}


def build(out):
    source_hashes = archive_sources(out)
    archive = out.relative_to(ROOT)
    executable = archive / "e049_split"
    highway = archive / HIGHWAY
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", f"-I{highway}",
               str(archive / "e049_split.cpp"), str(archive / "e047_vq_bridge.cpp"),
               str(highway / "hwy/abort.cc"), "-o", str(executable)]
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
        "vendor": {"highway": {"commit": HIGHWAY_COMMIT,
                                "dispatch": "VQSORT_ONLY_STATIC + HWY_COMPILE_ONLY_STATIC"}},
    }


def read_case(path, distribution):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, fieldnames=DRIVER_FIELDS))
    counts = set()
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise RuntimeError(f"Invalid driver columns in {path}")
        ms = float(row["ms"])
        if not math.isfinite(ms) or ms <= 0:
            raise RuntimeError(f"Invalid measured time in {path}")
        counts.add(tuple(int(row[field]) for field in ("low", "inside", "high")))
    actual = Counter((int(row["repeat"]), row["algorithm"]) for row in rows)
    expected = Counter((rep, alg) for rep in range(REPEATS) for alg in ALGORITHMS)
    if actual != expected or len(counts) != 1:
        raise RuntimeError(f"Unexpected measurement counts or changing cardinality in {path}")
    low, inside, high = counts.pop()
    outside = CASES[distribution][0]
    if min(low, inside, high) < 0 or inside != N - outside or low + high != outside:
        raise RuntimeError(f"Unexpected partition cardinality in {path}")
    if (distribution == "half_low" and high) or (distribution == "half_high" and low):
        raise RuntimeError(f"Wrong exterior side in {path}")
    return rows, (low, inside, high)


def analyze(out, cases, verified):
    lines = ["# E049 — Separación in situ con ventana preparada", "",
             "Cada cociente divide la mediana de la referencia por la de split. "
             "La puerta usa vq para el 50/50 y scalar_scratch para el 95/5.", "",
             "| Familia | Semilla | Inferiores | Internos | Superiores | Scalar scratch, ms | "
             "Compact scratch, ms | Split, ms | Vqsort, ms | Scalar / split | Compact / split | "
             "Vqsort / split | Puerta |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    failures = []
    losses = []
    samples = 0
    for (dist, seed), (rows, counts) in cases.items():
        samples += len(rows)
        medians = {alg: statistics.median(float(row["ms"]) for row in rows
                                         if row["algorithm"] == alg) for alg in ALGORITHMS}
        ratios = {alg: medians[alg] / medians["split"] for alg in ALGORITHMS if alg != "split"}
        _, reference, minimum = CASES[dist]
        ratio = ratios[reference]
        if ratio < minimum:
            failures.append(f"{dist}/{seed} obtuvo {ratio:.6f} frente a {reference}, "
                            f"por debajo de {minimum:.2f}.")
        below = [f"{alg} ({value:.6f})" for alg, value in ratios.items() if value < 1.0]
        if below:
            losses.append(f"{dist}/{seed} perdió frente a {', '.join(below)}.")
        values = " | ".join(f"{medians[alg]:.6f}" for alg in ALGORITHMS)
        comparisons = " | ".join(f"{value:.6f}" for value in ratios.values())
        low, inside, high = counts
        status = "Pasa" if ratio >= minimum else "Falla"
        lines.append(f"| {dist} | {seed} | {low} | {inside} | {high} | {values} | "
                     f"{comparisons} | {status} ({reference} ≥ {minimum:.2f}) |")
    gate = {"passed": not failures, "failures": failures}
    write_json(out / "gate.json", gate)
    checked = samples + len(cases) * len(ALGORITHMS)
    lines += ["", f"**Filtro {'fallido' if failures else 'superado'}.**", "",
              *(f"- {failure}" for failure in failures)]
    if losses:
        lines += ["", "## Pérdidas de split", "", *(f"- {loss}" for loss in losses)]
    lines += ["", f"{samples} muestras y {checked} salidas exactas con calentamientos. "
              f"{verified} comprobaciones previas de correctitud."]
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
        "stage": "E049",
        "matrix": {"n": N, "cases": CASES, "seeds": SEEDS, "algorithms": ALGORITHMS,
                   "repeats": REPEATS, "warmups": 1},
        "vq_pivot_state": "same initial state per arm and round, reset before timing",
        "timing": "Full sorting with a prepared window, including allocation, sorting, "
                  "reconstruction and deallocation; common input copy and verification outside.",
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
                rows, counts = read_case(path, dist)
                cases[dist, seed] = rows, counts
                writer.writerows(dict(row, n=N, distribution=dist, seed=seed) for row in rows)
                stream.flush()
    for seed in SEEDS:
        counts = {cases[dist, seed][1] for dist in ("half_grouped", "half_periodic", "half_random")}
        if len(counts) != 1:
            raise RuntimeError(f"Unexpected cardinality changes across the paired orderings for {seed}")
    check_hashes(out, build_metadata["source_files_sha256"])
    if sha256(ROOT / executable) != build_metadata["executable_sha256"]:
        raise RuntimeError("Executable changed during measurement")
    analyze(out, cases, int(count))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        parser.error("E049 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        parser.error("E049 requires taskset -c 2")
    out = ROOT / "results/e049_split_filter"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
