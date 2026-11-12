"""Archive and run the E048 classification contrast in Ubuntu WSL."""

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
REGISTRATION = ROOT / "notes/E048 - Prerregistro compactación AVX2.md"
CPU = 2
N = 10_000_000
SEEDS = (23143, 58427)
REPEATS = 7
ALGORITHMS = ("scalar", "compact")
DRIVER_FIELDS = ("repeat", "algorithm", "ms", "inside", "outside")
RAW_FIELDS = ("n", "distribution", "seed", *DRIVER_FIELDS)
# Exact residual size and preregistered lower bound for scalar/compact.
CASES = {
    "half_grouped": (N // 2, 0.90),
    "half_periodic": (N // 2, 0.90),
    "half_random": (N // 2, 1.20),
    "skew_grouped": (N // 20, 0.90),
    "skew_periodic": (N // 20, 0.90),
    "skew_random": (N // 20, 0.95),
    "two_half_random": (N // 2, 1.20),
    "two_skew_random": (N // 20, 0.95),
    "inside": (0, None),
}


def archive_sources(out):
    git = ["git", "-C", str(HIGHWAY)]
    commit = command_output([*git, "rev-parse", "HEAD"])
    if commit != HIGHWAY_COMMIT:
        raise RuntimeError(f"Unexpected Highway commit: {commit}")
    dirty = command_output([*git, "status", "--porcelain", "--untracked-files=all"])
    if dirty:
        raise RuntimeError(f"Highway sources differ from the pinned tree:\n{dirty}")

    for name in ("e048_compact.py", "e045_cells.py", "e046_windows.py", "e048_compact.cpp",
                 "vq_bridge.cpp", "include/supersort/windows_u32.hpp",
                 "include/supersort/windows_compact_u32.hpp"):
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
    executable = archive / "e048_compact"
    highway = archive / HIGHWAY
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", f"-I{highway}",
               str(archive / "e048_compact.cpp"), str(archive / "vq_bridge.cpp"),
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


def read_case(path, expected_outside):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, fieldnames=DRIVER_FIELDS))
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise RuntimeError(f"Invalid driver columns in {path}")
        ms = float(row["ms"])
        if not math.isfinite(ms) or ms <= 0:
            raise RuntimeError(f"Invalid measured time in {path}")
        if (int(row["inside"]), int(row["outside"])) != (N - expected_outside, expected_outside):
            raise RuntimeError(f"Unexpected partition cardinality in {path}")
    actual = Counter((int(row["repeat"]), row["algorithm"]) for row in rows)
    expected = Counter((rep, alg) for rep in range(REPEATS) for alg in ALGORITHMS)
    if actual != expected:
        raise RuntimeError(f"Unexpected measurement counts in {path}")
    return rows


def analyze(out, cases, verified):
    lines = ["# E048 — Filtro de compactación AVX2", "",
             "Diagnóstico con ventana y cobertura conocidas. Cada cociente divide la "
             "mediana de scalar por la de compact.", "",
             "| Familia | Semilla | Internos | Externos | Scalar, ms | Compact, ms | "
             "Scalar / compact | Mínimo | Puerta |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    failures = []
    for (dist, seed), rows in cases.items():
        outside, minimum = CASES[dist]
        scalar, compact = (statistics.median(float(row["ms"]) for row in rows
                                             if row["algorithm"] == alg) for alg in ALGORITHMS)
        ratio = scalar / compact
        if minimum is None:
            threshold, status = "—", "Control"
        else:
            threshold = f"{minimum:.2f}"
            status = "Pasa" if ratio >= minimum else "Falla"
            if ratio < minimum:
                failures.append(f"{dist}/{seed} obtuvo {ratio:.6f}, por debajo de {threshold}.")
        lines.append(f"| {dist} | {seed} | {N - outside} | {outside} | {scalar:.6f} | "
                     f"{compact:.6f} | {ratio:.6f} | {threshold} | {status} |")
    gate = {"passed": not failures, "failures": failures}
    write_json(out / "gate.json", gate)
    samples = sum(map(len, cases.values()))
    checked = samples + len(cases) * len(ALGORITHMS)
    lines += ["", f"**Filtro {'fallido' if failures else 'superado'}.**", "",
              *(f"- {failure}" for failure in failures), "",
              f"{samples} muestras y {checked} salidas exactas con calentamientos. "
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
        "stage": "E048",
        "matrix": {"n": N, "cases": CASES, "seeds": SEEDS, "algorithms": ALGORITHMS,
                   "repeats": REPEATS, "warmups": 1},
        "timing": "Prepared classification with allocation and histogram zeroing; verification, "
                  "residual sorting, reconstruction and buffer deallocation outside timing.",
    })
    verification = run_logged(out, "verify", [str(executable), "--verify"])
    marker, _, count = verification.read_text(encoding="utf-8").strip().partition(",")
    if marker != "verified" or not count.isascii() or not count.isdecimal() or int(count) <= 0:
        raise RuntimeError("Invalid correctness verification marker")

    cases = {}
    with (out / "raw.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RAW_FIELDS)
        writer.writeheader()
        for dist, (outside, _) in CASES.items():
            for seed in SEEDS:
                path = run_logged(out, f"case-{N}-{dist}-{seed}",
                                  [str(executable), str(N), dist, str(seed), str(REPEATS)])
                rows = read_case(path, outside)
                cases[dist, seed] = rows
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
        parser.error("E048 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        parser.error("E048 requires taskset -c 2")
    out = ROOT / "results/e048_compact_filter"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
