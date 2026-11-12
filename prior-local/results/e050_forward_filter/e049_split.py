"""Archive and run the prepared in-place window contrasts in Ubuntu WSL."""

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
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
CPU = 2
N = 10_000_000
REPEATS = 7
DRIVER_FIELDS = ("repeat", "algorithm", "ms", "low", "inside", "high")
RAW_FIELDS = ("n", "distribution", "seed", *DRIVER_FIELDS)
PHASE_FIELDS = ("repeat", "algorithm", "classify_ms", "sort_ms", "rebuild_ms")
# Exterior cardinality, gate reference and minimum reference/candidate ratio.
CASES = {
    "half_grouped": (N // 2, "vq", 0.90),
    "half_periodic": (N // 2, "vq", 0.90),
    "half_random": (N // 2, "vq", 1.10),
    "skew_random": (N // 20, "scalar_scratch", 0.90),
    "half_low": (N // 2, "vq", 0.90),
    "half_high": (N // 2, "vq", 0.90),
}


@dataclass(frozen=True)
class Protocol:
    stage: str
    stem: str
    registration: str
    seeds: tuple
    algorithms: tuple
    candidate: str
    phases: tuple = ()


E049 = Protocol("E049", "e049_split", "E049 - Prerregistro separación in situ.md",
                (28729, 80149), ("scalar_scratch", "compact_scratch", "split", "vq"), "split")
E050 = Protocol("E050", "e050_forward", "E050 - Prerregistro cursor y fases.md",
                (32653, 77347), ("scalar_scratch", "split", "forward", "vq"), "forward",
                ("half_grouped", "half_periodic", "half_random", "half_high", "skew_random"))


def archive_sources(out, protocol):
    git = ["git", "-C", str(HIGHWAY)]
    commit = command_output([*git, "rev-parse", "HEAD"])
    if commit != HIGHWAY_COMMIT:
        raise RuntimeError(f"Unexpected Highway commit: {commit}")
    dirty = command_output([*git, "status", "--porcelain", "--untracked-files=all"])
    if dirty:
        raise RuntimeError(f"Highway sources differ from the pinned tree:\n{dirty}")

    sources = ["e049_split.py", "e045_cells.py", "e046_windows.py", "e049_split.cpp",
               "e047_vq_bridge.cpp", "include/supersort/windows_u32.hpp",
               "include/supersort/windows_compact_u32.hpp", "include/supersort/windows_split_u32.hpp"]
    if protocol == E050:
        sources.append("include/supersort/windows_forward_u32.hpp")
    for name in sources:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copyfile(ROOT / "notes" / protocol.registration, out / "preregistration.md")
    shutil.copytree(ROOT / HIGHWAY / "hwy", out / HIGHWAY / "hwy")
    shutil.copyfile(ROOT / HIGHWAY / "LICENSE", out / HIGHWAY / "LICENSE")
    return {path.relative_to(out).as_posix(): sha256(path)
            for path in sorted(out.rglob("*")) if path.is_file()}


def build(out, protocol):
    source_hashes = archive_sources(out, protocol)
    archive = out.relative_to(ROOT)
    executable = archive / protocol.stem
    highway = archive / HIGHWAY
    definitions = ["-DSUPERSORT_E050"] if protocol == E050 else []
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", f"-I{highway}",
               *definitions,
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


def read_case(path, distribution, algorithms):
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
    expected = Counter((rep, alg) for rep in range(REPEATS) for alg in algorithms)
    if actual != expected or len(counts) != 1:
        raise RuntimeError(f"Unexpected measurement counts or changing cardinality in {path}")
    low, inside, high = counts.pop()
    outside = CASES[distribution][0]
    if min(low, inside, high) < 0 or inside != N - outside or low + high != outside:
        raise RuntimeError(f"Unexpected partition cardinality in {path}")
    if (distribution == "half_low" and high) or (distribution == "half_high" and low):
        raise RuntimeError(f"Wrong exterior side in {path}")
    return rows, (low, inside, high)


def analyze(out, cases, verified, protocol):
    candidate = protocol.candidate
    timings = " | ".join(f"{alg}, ms" for alg in protocol.algorithms)
    comparisons = " | ".join(f"{alg} / {candidate}" for alg in protocol.algorithms if alg != candidate)
    lines = [f"# {protocol.stage} — Separación in situ con ventana preparada", "",
             f"Cada cociente divide la mediana de la referencia por la de {candidate}. "
             "La puerta usa vq para el 50/50 y scalar_scratch para el 95/5.", "",
             f"| Familia | Semilla | Inferiores | Internos | Superiores | {timings} | {comparisons} | Puerta |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    failures = []
    losses = []
    samples = 0
    for (dist, seed), (rows, counts) in cases.items():
        samples += len(rows)
        medians = {alg: statistics.median(float(row["ms"]) for row in rows
                                         if row["algorithm"] == alg) for alg in protocol.algorithms}
        ratios = {alg: medians[alg] / medians[candidate] for alg in protocol.algorithms if alg != candidate}
        _, reference, minimum = CASES[dist]
        ratio = ratios[reference]
        if ratio < minimum:
            failures.append(f"{dist}/{seed} obtuvo {ratio:.6f} frente a {reference}, "
                            f"por debajo de {minimum:.2f}.")
        below = [f"{alg} ({value:.6f})" for alg, value in ratios.items() if value < 1.0]
        if below:
            losses.append(f"{dist}/{seed} perdió frente a {', '.join(below)}.")
        values = " | ".join(f"{medians[alg]:.6f}" for alg in protocol.algorithms)
        comparisons = " | ".join(f"{value:.6f}" for value in ratios.values())
        low, inside, high = counts
        status = "Pasa" if ratio >= minimum else "Falla"
        lines.append(f"| {dist} | {seed} | {low} | {inside} | {high} | {values} | "
                     f"{comparisons} | {status} ({reference} ≥ {minimum:.2f}) |")
    gate = {"passed": not failures, "failures": failures}
    write_json(out / "gate.json", gate)
    checked = samples + len(cases) * len(protocol.algorithms)
    lines += ["", f"**Filtro {'fallido' if failures else 'superado'}.**", "",
              *(f"- {failure}" for failure in failures)]
    if losses:
        lines += ["", f"## Pérdidas de {candidate}", "", *(f"- {loss}" for loss in losses)]
    lines += ["", f"{samples} muestras y {checked} salidas exactas con calentamientos. "
              f"{verified} comprobaciones previas de correctitud."]
    if protocol.phases:
        lines += ["", "[Diagnóstico separado de fases](phases.md)."]
    write_text(out / "summary.md", "\n".join(lines))
    print(f"{samples} muestras y {checked} salidas exactas con calentamientos.", flush=True)
    print((out / "gate.json").read_text(encoding="utf-8"), flush=True)


def run_phases(out, executable, protocol):
    algorithms = ("split", "forward")
    seed = protocol.seeds[0]
    expected = Counter((rep, alg) for rep in range(REPEATS) for alg in algorithms)
    lines = ["# E050 — Diagnóstico separado de fases", "",
             "Medianas por fase en ms. Los relojes internos pertenecen a otro modo de prueba.", "",
             "| Familia | Semilla | Brazo | Clasificación | Sort residual | Reconstrucción |",
             "|---|---:|---|---:|---:|---:|"]
    with (out / "phases.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("n", "distribution", "seed", *PHASE_FIELDS))
        writer.writeheader()
        for dist in protocol.phases:
            path = run_logged(out, f"phases-{dist}-{seed}",
                              [str(executable), "--phases", str(N), dist, str(seed), str(REPEATS)])
            with path.open(newline="", encoding="utf-8") as raw:
                rows = list(csv.DictReader(raw, fieldnames=PHASE_FIELDS))
            for row in rows:
                if None in row or any(value is None for value in row.values()):
                    raise RuntimeError(f"Invalid phase columns in {path}")
                for field in PHASE_FIELDS[2:]:
                    ms = float(row[field])
                    if not math.isfinite(ms) or ms <= 0:
                        raise RuntimeError(f"Invalid phase measurement in {path}")
            if Counter((int(row["repeat"]), row["algorithm"]) for row in rows) != expected:
                raise RuntimeError(f"Unexpected phase measurement counts in {path}")
            writer.writerows(dict(row, n=N, distribution=dist, seed=seed) for row in rows)
            stream.flush()
            for arm in algorithms:
                medians = [statistics.median(float(row[field]) for row in rows if row["algorithm"] == arm)
                           for field in PHASE_FIELDS[2:]]
                values = " | ".join(f"{ms:.6f}" for ms in medians)
                lines.append(f"| {dist} | {seed} | {arm} | {values} |")
    invocations = len(protocol.phases) * len(algorithms)
    lines += ["", f"{invocations * REPEATS} llamadas medidas y "
                  f"{invocations * (REPEATS + 1)} salidas exactas con calentamientos."]
    write_text(out / "phases.md", "\n".join(lines))


def execute(out, protocol):
    executable, build_metadata = build(out, protocol)
    write_text(out / "lscpu.txt", command_output(["lscpu"]))
    write_json(out / "metadata.json", {
        **build_metadata,
        "utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "logical_cpu": CPU,
        "affinity": sorted(os.sched_getaffinity(0)),
        "stage": protocol.stage,
        "matrix": {"n": N, "cases": CASES, "seeds": protocol.seeds, "algorithms": protocol.algorithms,
                   "repeats": REPEATS, "warmups": 1},
        "diagnostic_phase_cases": protocol.phases,
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
            for seed in protocol.seeds:
                path = run_logged(out, f"case-{N}-{dist}-{seed}",
                                  [str(executable), str(N), dist, str(seed), str(REPEATS)])
                rows, counts = read_case(path, dist, protocol.algorithms)
                cases[dist, seed] = rows, counts
                writer.writerows(dict(row, n=N, distribution=dist, seed=seed) for row in rows)
                stream.flush()
    for seed in protocol.seeds:
        counts = {cases[dist, seed][1] for dist in ("half_grouped", "half_periodic", "half_random")}
        if len(counts) != 1:
            raise RuntimeError(f"Unexpected cardinality changes across the paired orderings for {seed}")
    if protocol.phases:
        run_phases(out, executable, protocol)
    check_hashes(out, build_metadata["source_files_sha256"])
    if sha256(ROOT / executable) != build_metadata["executable_sha256"]:
        raise RuntimeError("Executable changed during measurement")
    for path, digest in build_metadata["dynamic_library_sha256"].items():
        if sha256(Path(path)) != digest:
            raise RuntimeError(f"Dynamic dependency changed during measurement: {path}")
    analyze(out, cases, int(count), protocol)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--e050", action="store_true", help="Run the forward-cursor experiment.")
    protocol = E050 if parser.parse_args().e050 else E049
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        parser.error(f"{protocol.stage} requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        parser.error(f"{protocol.stage} requires taskset -c 2")
    out = ROOT / "results" / f"{protocol.stem}_filter"
    out.mkdir(exist_ok=False)
    try:
        execute(out, protocol)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
