"""Archive and run the E053 sparse dictionary contrast in Ubuntu WSL."""

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
REGISTRATION = ROOT / "notes/E053 - Prerregistro diccionario por bits.md"
CPU = 2
N = 10_000_000
SEEDS = (40559, 89119)
REPEATS = 7
ALGORITHMS = ("single", "striped", "vq")
DRIVER_FIELDS = ("repeat", "algorithm", "ms", "route", "examined", "proposals")
RAW_FIELDS = ("n", "distribution", "seed", *DRIVER_FIELDS)
CASES = ("few", "few_permute", "few_dominant", "few_powers", "uniform", "mixed", "equal",
         "early_unknown", "late_unknown")
EXPECTED_WORK = {
    "few": ("counted", N, 16),
    "few_permute": ("counted", N, 16),
    "few_dominant": ("counted", N, 16),
    "few_powers": ("collision", 0, 16),
    "uniform": ("bypass", 0, 17),
    "mixed": ("bypass", 0, 17),
    "equal": ("bypass", 0, 1),
    "early_unknown": ("reject", 4, 16),
    "late_unknown": ("reject", N, 16),
}


def archive_sources(out):
    git = ["git", "-C", str(HIGHWAY)]
    commit = command_output([*git, "rev-parse", "HEAD"])
    if commit != HIGHWAY_COMMIT:
        raise RuntimeError(f"Unexpected Highway commit: {commit}")
    dirty = command_output([*git, "status", "--porcelain", "--untracked-files=all"])
    if dirty:
        raise RuntimeError(f"Highway sources differ from the pinned tree:\n{dirty}")

    for name in ("e053_dictionary.py", "e045_cells.py", "e046_windows.py", "e053_dictionary.cpp",
                 "e047_vq_bridge.cpp", "include/supersort/dictionary_u32.hpp"):
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
    executable = archive / "e053_dictionary"
    highway = archive / HIGHWAY
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", f"-I{highway}",
               str(archive / "e053_dictionary.cpp"), str(archive / "e047_vq_bridge.cpp"),
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


def read_case(path):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, fieldnames=DRIVER_FIELDS))
    telemetry = set()
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise RuntimeError(f"Invalid driver columns in {path}")
        ms = float(row["ms"])
        if not math.isfinite(ms) or ms <= 0:
            raise RuntimeError(f"Invalid measured time in {path}")
        route = row["route"]
        examined = int(row["examined"])
        proposals = int(row["proposals"])
        if (route not in ("bypass", "collision", "reject", "counted")
                or not 0 <= examined <= N or not 0 <= proposals <= 17):
            raise RuntimeError(f"Invalid dictionary telemetry in {path}")
        if row["algorithm"] in ("single", "striped"):
            telemetry.add((route, examined, proposals))
        elif (route, examined, proposals) != ("bypass", 0, 0):
            raise RuntimeError(f"Unexpected telemetry for direct vqsort in {path}")
    actual = Counter((int(row["repeat"]), row["algorithm"]) for row in rows)
    expected = Counter((rep, alg) for rep in range(REPEATS) for alg in ALGORITHMS)
    if actual != expected or len(telemetry) != 1:
        raise RuntimeError(f"Unexpected measurement counts or changing dictionary telemetry in {path}")
    return rows, telemetry.pop()


def analyze(out, cases, verified):
    lines = ["# E053 — Filtro del diccionario exacto", "",
             "Cada cociente divide la mediana de la referencia por la de striped. "
             "El sobrecoste es la mediana de striped menos la de vqsort.", "",
             "| Familia | Semilla | Single, ms | Striped, ms | Vqsort, ms | Single / striped | "
             "Vqsort / striped | Striped − vqsort, ms | Ruta | Examinadas | Propuestas | Puerta |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---|"]
    failures = []
    losses = []
    samples = 0
    for (dist, seed), (rows, (route, examined, proposals)) in cases.items():
        samples += len(rows)
        single, striped, vq = (statistics.median(float(row["ms"]) for row in rows
                                                 if row["algorithm"] == alg) for alg in ALGORITHMS)
        single_ratio, vq_ratio = single / striped, vq / striped
        extra_ms = striped - vq
        failed = []
        if dist in ("few", "few_permute") and vq_ratio < 1.25:
            failed.append(f"vq/striped {vq_ratio:.6f} < 1,25")
        elif dist == "few_dominant" and single_ratio < 1.00:
            failed.append(f"single/striped {single_ratio:.6f} < 1,00")
        elif dist == "late_unknown" and extra_ms > 7.0:
            failed.append(f"sobrecoste {extra_ms:.6f} ms > 7 ms")
        elif dist not in ("few", "few_permute", "few_dominant", "late_unknown") and vq_ratio < 0.90:
            failed.append(f"vq/striped {vq_ratio:.6f} < 0,90")
        work = (route, examined, proposals)
        if work != EXPECTED_WORK[dist]:
            failed.append(f"ruta y contadores {work} distintos de {EXPECTED_WORK[dist]}")
        label = f"{dist}/{seed}"
        failures.extend(f"{label} incumplió {reason}." for reason in failed)
        below = [f"{name} ({ratio:.6f})" for name, ratio in (("single", single_ratio), ("vq", vq_ratio))
                 if ratio < 1.0]
        if below:
            losses.append(f"{label} perdió frente a {', '.join(below)}.")
        status = "Falla" if failed else "Pasa"
        lines.append(f"| {dist} | {seed} | {single:.6f} | {striped:.6f} | {vq:.6f} | "
                     f"{single_ratio:.6f} | {vq_ratio:.6f} | {extra_ms:+.6f} | {route} | "
                     f"{examined} | {proposals} | {status} |")
    gate = {"passed": not failures, "failures": failures}
    write_json(out / "gate.json", gate)
    lines += ["", f"**Filtro {'fallido' if failures else 'superado'}.**", "",
              *(f"- {failure}" for failure in failures)]
    if losses:
        lines += ["", "## Pérdidas de striped", "", *(f"- {loss}" for loss in losses)]
    checked = samples + len(cases) * len(ALGORITHMS)
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
        "stage": "E053",
        "matrix": {"n": N, "cases": CASES, "seeds": SEEDS, "algorithms": ALGORITHMS,
                   "repeats": REPEATS, "warmups": 1},
        "vq_pivot_state": "same initial state per arm and round, reset before timing",
        "timing": "Includes proposal, initialization, counting, emission and fallback. "
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
    analyze(out, cases, int(count))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        parser.error("E053 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        parser.error("E053 requires taskset -c 2")
    out = ROOT / "results/e053_dictionary_filter"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
