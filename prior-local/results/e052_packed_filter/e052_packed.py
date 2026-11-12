"""Archive and run the E052 prefix-packed leaf contrast in Ubuntu WSL."""

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
REGISTRATION = ROOT / "notes/E052 - Prerregistro hojas de 16 bits.md"
CPU = 2
MATRIX = {
    5_000_000: ("uniform", "external_mix", "external_low", "prefix_distinct", "bimodal"),
    10_000_000: ("uniform", "prefix_distinct", "dense16", "skew", "mixed", "bimodal", "few", "equal"),
}
SEEDS = (39607, 82723)
REPEATS = 7
ALGORITHMS = ("wide", "packed", "vq")
WORK_FIELDS = ("coarse", "leaves", "above128", "above256")
DRIVER_FIELDS = ("repeat", "algorithm", "ms", *WORK_FIELDS)
RAW_FIELDS = ("n", "distribution", "seed", *DRIVER_FIELDS)


def archive_sources(out):
    git = ["git", "-C", str(HIGHWAY)]
    commit = command_output([*git, "rev-parse", "HEAD"])
    if commit != HIGHWAY_COMMIT:
        raise RuntimeError(f"Unexpected Highway commit: {commit}")
    dirty = command_output([*git, "status", "--porcelain", "--untracked-files=all"])
    if dirty:
        raise RuntimeError(f"Highway sources differ from the pinned tree:\n{dirty}")

    for name in ("e052_packed.py", "e045_cells.py", "e046_windows.py", "e052_packed.cpp",
                 "e047_vq_bridge.cpp", "include/supersort/prefix_packed_u32.hpp"):
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
    executable = archive / "e052_packed"
    highway = archive / HIGHWAY
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", "-DSUPERSORT_PACKED_U16",
               f"-I{highway}", str(archive / "e052_packed.cpp"), str(archive / "e047_vq_bridge.cpp"),
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
        counts = tuple(int(row[field]) for field in WORK_FIELDS)
        if min(counts) < 0:
            raise RuntimeError(f"Negative histogram telemetry in {path}")
        telemetry.add(counts)
    actual = Counter((int(row["repeat"]), row["algorithm"]) for row in rows)
    expected = Counter((rep, alg) for rep in range(REPEATS) for alg in ALGORITHMS)
    if actual != expected or len(telemetry) != 1:
        raise RuntimeError(f"Unexpected measurement counts or changing histogram telemetry in {path}")
    coarse, leaves, above128, above256 = telemetry.pop()
    if not (1 <= coarse <= min(256, leaves) and leaves <= 65536 and 0 <= above256 <= above128 <= leaves):
        raise RuntimeError(f"Inconsistent histogram telemetry in {path}")
    return rows, (coarse, leaves, above128, above256)


def analyze(out, cases, verified):
    lines = ["# E052 — Filtro de hojas de 16 bits", "",
             "Cada cociente divide la mediana de la referencia por la de packed. "
             "Los ahorros en ms son la mediana de la referencia menos la de packed.", "",
             "| n | Familia | Semilla | Wide, ms | Packed, ms | Vqsort, ms | Wide / packed | "
             "Vqsort / packed | Wide − packed, ms | Vqsort − packed, ms | Grupos | Hojas | "
             "Hojas >128 | Hojas >256 | Puerta |",
             "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    failures = []
    losses = []
    samples = 0
    for (n, dist, seed), (rows, counts) in cases.items():
        samples += len(rows)
        wide, packed, vq = (statistics.median(float(row["ms"]) for row in rows
                                             if row["algorithm"] == alg) for alg in ALGORITHMS)
        wide_ratio, vq_ratio = wide / packed, vq / packed
        wide_delta, vq_delta = wide - packed, vq - packed
        checks = []
        if (n, dist) == (5_000_000, "external_mix"):
            checks = [("ahorro ante vqsort, ms", vq_delta, 4.0), ("wide/packed", wide_ratio, 1.10)]
        elif (n, dist) == (10_000_000, "uniform"):
            checks = [("vqsort/packed", vq_ratio, 1.25), ("wide/packed", wide_ratio, 1.10)]
        elif dist in ("prefix_distinct", "external_low"):
            checks = [("vqsort/packed", vq_ratio, 0.90)]
        misses = [(name, value, limit) for name, value, limit in checks if value < limit]
        label = f"{n}/{dist}/{seed}"
        failures.extend(f"{label} obtuvo {value:.6f} en {name}, por debajo de {limit:.2f}."
                        for name, value, limit in misses)
        below = [f"{name} ({ratio:.6f})" for name, ratio in (("wide", wide_ratio), ("vq", vq_ratio))
                 if ratio < 1.0]
        if below:
            losses.append(f"{label} perdió frente a {', '.join(below)}.")
        work = " | ".join(str(count) for count in counts)
        status = "Diagnóstico" if not checks else "Falla" if misses else "Pasa"
        lines.append(f"| {n} | {dist} | {seed} | {wide:.6f} | {packed:.6f} | {vq:.6f} | "
                     f"{wide_ratio:.6f} | {vq_ratio:.6f} | {wide_delta:+.6f} | {vq_delta:+.6f} | "
                     f"{work} | {status} |")
    gate = {"passed": not failures, "failures": failures}
    write_json(out / "gate.json", gate)
    lines += ["", f"**Filtro {'fallido' if failures else 'superado'}.**", "",
              *(f"- {failure}" for failure in failures)]
    if losses:
        lines += ["", "## Pérdidas de packed", "", *(f"- {loss}" for loss in losses)]
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
        "stage": "E052",
        "matrix": {"cases": MATRIX, "seeds": SEEDS, "algorithms": ALGORITHMS,
                   "repeats": REPEATS, "warmups": 1},
        "vq_pivot_state": "same initial state per arm and round, reset before timing",
        "timing": "Includes histogram, buffers, coarse scatter, leaves, expansion and deallocation. "
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
        for n, distributions in MATRIX.items():
            for dist in distributions:
                for seed in SEEDS:
                    path = run_logged(out, f"case-{n}-{dist}-{seed}",
                                      [str(executable), str(n), dist, str(seed), str(REPEATS)])
                    rows, counts = read_case(path)
                    cases[n, dist, seed] = rows, counts
                    writer.writerows(dict(row, n=n, distribution=dist, seed=seed) for row in rows)
                    stream.flush()
    check_hashes(out, build_metadata["source_files_sha256"])
    if sha256(ROOT / executable) != build_metadata["executable_sha256"]:
        raise RuntimeError("Executable changed during measurement")
    analyze(out, cases, int(count))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        parser.error("E052 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        parser.error("E052 requires taskset -c 2")
    out = ROOT / "results/e052_packed_filter"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
