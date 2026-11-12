"""Run the E046 or E047 filter and its conditional comparison with the same WSL binary."""

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import platform
import shutil
import statistics
import sys

from e045_cells import command_output, run_logged, sha256


ROOT = Path(__file__).resolve().parent
VENDORS = {
    "highway": ("a3f6f68fcc368e5e3025ca25805eabda9d8a456f", "hwy", "LICENSE"),
    "x86-simd-sort": ("6e059b14975df2e3c74260ec905167a1be5a34ca", "src", "LICENSE.md"),
    "ips2ra": ("83f6b76ca308b277b2acc3a36426a3baa3c9cb73", "include", "LICENSE"),
    "ips4o": ("08a5b926ee65cef19139057c6bde02bb5542c1cb", "include", "LICENSE"),
}
CPU = 2
REPEATS = 7
PRIMARY = ("uniform", "dense16", "skew", "bimodal", "mixed",
           "prefix_distinct", "few", "equal")
TARGETS = ("dense16", "skew", "bimodal")
FILTER_DISTS = (*PRIMARY, "late_reject", "near_sorted")
FULL_DISTS = (*FILTER_DISTS, "window_pair_shuffled", "window_pair_grouped")
FILTER_ALGS = ("window", "cert_vq", "vq")
FULL_ALGS = ("window", "vq", "simd", "ips2ra")
DRIVER_FIELDS = ("repeat", "algorithm", "ms", "route", "examined", "residual")
RAW_FIELDS = ("n", "distribution", "seed", *DRIVER_FIELDS)


@dataclass(frozen=True)
class Experiment:
    stage: str
    registration: Path
    vq_bridge: str
    filter_seeds: tuple[int, int]

    @property
    def binary(self):
        return f"{self.stage.lower()}_windows"

    def directory(self, mode):
        return ROOT / "results" / f"{self.binary}_{mode}"


E046 = Experiment("E046", ROOT / "notes/E046 - Prerregistro ventanas.md",
                  "vq_bridge.cpp", (15083, 62039))
E047 = Experiment("E047", ROOT / "notes/E047 - Prerregistro certificado por bloques.md",
                  "e047_vq_bridge.cpp", (19141, 70913))


def write_text(path, contents):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(contents + "\n")


def write_json(path, data):
    write_text(path, json.dumps(data, indent=2, ensure_ascii=False))


def archive_registration(out, experiment):
    shutil.copyfile(experiment.registration, out / "preregistration.md")
    if experiment == E047:
        shutil.copyfile(E046.registration, out / "base-preregistration.md")


def archive_sources(out, experiment):
    files = ["e046_windows.py", "e045_cells.py", "e046_windows.cpp",
             "include/supersort/windows_u32.hpp", experiment.vq_bridge, "ips_bridge.cpp"]
    if experiment == E047:
        files.append("include/supersort/windows_e047_u32.hpp")
    for name in files:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    archive_registration(out, experiment)
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
    return {p.relative_to(out).as_posix(): sha256(p)
            for p in sorted(out.rglob("*")) if p.is_file()}


def check_hashes(folder, hashes):
    for name, expected in hashes.items():
        if sha256(folder / name) != expected:
            raise RuntimeError(f"Archived source has changed: {name}")


def build(out, experiment):
    source_hashes = archive_sources(out, experiment)
    archive = out.relative_to(ROOT)
    exe = archive / experiment.binary
    vendor = archive / "vendor"
    defines = ["-DSUPERSORT_E047"] if experiment == E047 else []
    flags = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17",
             *defines,
             f"-I{vendor / 'highway'}", f"-I{vendor / 'ips2ra/include'}",
             f"-I{vendor / 'ips4o/include'}", str(archive / "e046_windows.cpp"),
             str(archive / experiment.vq_bridge), str(archive / "ips_bridge.cpp"),
             str(vendor / "highway/hwy/abort.cc"), "-ltbb", "-latomic", "-pthread",
             "-o", str(exe)]
    run_logged(out, "build", flags)
    check_hashes(out, source_hashes)
    linkage = command_output(["ldd", str(exe)])
    write_text(out / "ldd.txt", linkage)
    library_hashes = {}
    for line in linkage.splitlines():
        library = line.partition("=>")[2].strip().split(" ", 1)[0]
        if library.startswith("/"):
            library_hashes[library] = sha256(Path(library))
    return exe, {
        "flags": flags,
        "compiler": command_output(["g++", "--version"]),
        "compiler_target": command_output(["g++", "-dumpmachine"]),
        "source_files_sha256": source_hashes,
        "vendor": {name: spec[0] for name, spec in VENDORS.items()},
        "executable": exe.as_posix(),
        "executable_sha256": sha256(ROOT / exe),
        "dynamic_library_sha256": library_hashes,
        "dispatch": "Highway VQSortStatic native, x86simdsortStatic native, ips2ra::sort sequential",
    }


def open_exact_filter(experiment):
    origin = experiment.directory("filter")
    gate = json.loads((origin / "gate.json").read_text(encoding="utf-8"))
    if not gate["passed"] or not (origin / "summary.md").is_file():
        raise RuntimeError(f"{experiment.stage} full requires a completed filter that passed its gate")
    metadata = json.loads((origin / "metadata.json").read_text(encoding="utf-8"))
    executable = Path(metadata["executable"])
    if sha256(ROOT / executable) != metadata["executable_sha256"]:
        raise RuntimeError("Filter executable differs from its recorded hash")
    check_hashes(origin, metadata["source_files_sha256"])
    if experiment == E047:
        check_hashes(ROOT, {name: metadata["source_files_sha256"][name]
                            for name in ("e046_windows.py", "e045_cells.py")})
    for name, expected in metadata["dynamic_library_sha256"].items():
        if sha256(Path(name)) != expected:
            raise RuntimeError(f"Dynamic dependency differs from the filter: {name}")
    return executable, metadata


def read_case(path, algs):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, fieldnames=DRIVER_FIELDS))
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise RuntimeError(f"Invalid driver columns in {path}")
        ms = float(row["ms"])
        if not math.isfinite(ms) or ms <= 0:
            raise RuntimeError(f"Invalid time in {path}")
        if row["route"] not in ("bypass", "reject", "constant", "one", "two"):
            raise RuntimeError(f"Unknown route in {path}: {row['route']}")
        if min(int(row["examined"]), int(row["residual"])) < 0:
            raise RuntimeError(f"Negative work count in {path}")
    actual = Counter((int(row["repeat"]), row["algorithm"]) for row in rows)
    if actual != Counter((rep, alg) for rep in range(REPEATS) for alg in algs):
        raise RuntimeError(f"Unexpected measurement counts in {path}")
    return rows


def summarize_cases(cases, algs):
    for (n, dist, seed), rows in cases.items():
        medians = {}
        work = {}
        for alg in algs:
            arm = [row for row in rows if row["algorithm"] == alg]
            medians[alg] = statistics.median(float(row["ms"]) for row in arm)
            counts = {(row["route"], int(row["examined"]), int(row["residual"])) for row in arm}
            if len(counts) != 1:
                raise RuntimeError(f"Non-repeatable route or work for {n}/{dist}/{seed}/{alg}")
            work[alg] = counts.pop()
        yield n, dist, seed, medians, work


def analyze_filter(out, cases, stage):
    lines = [f"# {stage} — Filtro de ventanas", "",
             "| n | Familia | Semilla | Ventanas, ms | Certificado + vqsort, ms | vqsort, ms | "
             "Certificado / ventanas | vqsort / ventanas | Ventanas − vqsort, ms | "
             "Ruta | Examinadas | Residuo |",
             "|---:|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|"]
    failed = []
    for n, dist, seed, t, work in summarize_cases(cases, FILTER_ALGS):
        window, cert, vq = (t[alg] for alg in FILTER_ALGS)
        route, examined, residual = work["window"]
        if work["window"] != work["cert_vq"]:
            raise RuntimeError(f"Different certificates in the two arms for {dist}/{seed}")
        relative_cert = cert / window
        relative_vq = vq / window
        extra_ms = window - vq
        lines.append(f"| {n} | {dist} | {seed} | {window:.6f} | {cert:.6f} | {vq:.6f} | "
                     f"{relative_cert:.6f} | {relative_vq:.6f} | {extra_ms:+.6f} | "
                     f"{route} | {examined} | {residual} |")
        if dist in TARGETS and min(relative_cert, relative_vq) < 1.10:
            failed.append(f"{dist}/{seed} quedó por debajo de 1,10 en al menos un cociente.")
        elif dist in PRIMARY and dist not in TARGETS and relative_vq < 0.90:
            failed.append(f"{dist}/{seed} quedó por debajo de 0,90 frente a vqsort.")
        elif dist == "late_reject" and (route != "reject" or examined > n or extra_ms > 7):
            failed.append(f"{dist}/{seed} incumplió la ruta, el límite de lectura o el de 7 ms.")
    gate = {"passed": not failed, "failures": failed}
    write_json(out / "gate.json", gate)
    lines += ["", f"**Filtro {'fallido' if failed else 'superado'}.**", ""]
    lines.extend(f"- {reason}" for reason in failed)
    return lines


def analyze_full(cases, stage):
    refs = FULL_ALGS[1:]
    lines = [f"# {stage} — Comparación completa", "",
             "Cada cociente divide la mediana de la referencia por la del candidato. "
             "Un cociente inferior a 1 indica una pérdida.", "",
             "| n | Familia | Semilla | Ventanas, ms | vqsort, ms | x86-simd-sort, ms | IPS2Ra, ms | "
             "vq / ventanas | SIMD / ventanas | IPS2Ra / ventanas | Mejor referencia | "
             "Mejor / ventanas | Ruta | Examinadas | Residuo |",
             "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---:|---:|"]
    wins = Counter()
    totals = Counter()
    losses = []
    for n, dist, seed, t, work in summarize_cases(cases, FULL_ALGS):
        medians = " | ".join(f"{t[alg]:.6f}" for alg in FULL_ALGS)
        ratios = {ref: t[ref] / t["window"] for ref in refs}
        values = " | ".join(f"{ratios[ref]:.6f}" for ref in refs)
        best = min(refs, key=ratios.__getitem__)
        route, examined, residual = work["window"]
        lines.append(f"| {n} | {dist} | {seed} | {medians} | {values} | {best} | "
                     f"{ratios[best]:.6f} | {route} | {examined} | {residual} |")
        totals[n, dist] += 1
        for ref in (*refs, "best"):
            wins[n, dist, ref] += ratios[best if ref == "best" else ref] > 1
        below = [f"{ref} {ratios[ref]:.6f}" for ref in refs if ratios[ref] < 1]
        if below:
            losses.append(f"- {n}/{dist}/{seed} perdió ante {', '.join(below)}.")
    lines += ["", "| n | Familia | Entradas | Victorias vqsort | Victorias SIMD | "
              "Victorias IPS2Ra | Victorias mejor referencia |",
              "|---:|---|---:|---:|---:|---:|---:|"]
    for (n, dist), total in totals.items():
        counts = " | ".join(str(wins[n, dist, ref]) for ref in (*refs, "best"))
        lines.append(f"| {n} | {dist} | {total} | {counts} |")
    if losses:
        lines += ["", "### Pérdidas por entrada", "", *losses]
    return lines


def execute(out, mode, experiment):
    if mode == "filter":
        exe, metadata = build(out, experiment)
        sizes, dists, seeds, algs = (10_000_000,), FILTER_DISTS, experiment.filter_seeds, FILTER_ALGS
    else:
        exe, metadata = open_exact_filter(experiment)
        sizes, dists, seeds, algs = (1_000_000, 10_000_000), FULL_DISTS, (28229, 78691), FULL_ALGS
        origin = experiment.directory("filter")
        metadata["origin"] = str(origin.relative_to(ROOT))
        shutil.copyfile(origin / "preregistration.md", out / "preregistration.md")
        if experiment == E047:
            shutil.copyfile(origin / "base-preregistration.md", out / "base-preregistration.md")
        shutil.copyfile(Path(__file__), out / "e046_windows.py")
        shutil.copyfile(ROOT / "e045_cells.py", out / "e045_cells.py")
        shutil.copyfile(origin / "gate.json", out / "filter-gate.json")
    write_text(out / "lscpu.txt", command_output(["lscpu"]))
    write_json(out / "metadata.json", {
        **metadata,
        "utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "logical_cpu": CPU,
        "mode": mode,
        "stage": experiment.stage,
        "vq_pivot_state": ("same initial state per arm and round, reset before timing"
                           if experiment == E047 and mode == "filter" else "library default"),
        "matrix": {"sizes": sizes, "distributions": dists, "seeds": seeds,
                   "algorithms": algs, "repeats": REPEATS, "warmups": 1},
        "timing": "Full single-thread sort with reserves, copyback and fallback included; "
                  "shared input copy and exact std::sort check outside timing.",
    })
    if mode == "filter":
        path = run_logged(out, "verify", [str(exe), "--verify"])
        marker, separator, count = path.read_text(encoding="utf-8").strip().partition(",")
        if marker != "verified" or not separator or int(count) <= 0:
            raise RuntimeError("Invalid count from exact guard and correctness validation")
    cases = {}
    with (out / "raw.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RAW_FIELDS)
        writer.writeheader()
        for n in sizes:
            for dist in dists:
                for seed in seeds:
                    label = f"case-{n}-{dist}-{seed}"
                    path = run_logged(out, label, [str(exe), mode, str(n), dist,
                                                   str(seed), str(REPEATS)])
                    rows = read_case(path, algs)
                    cases[n, dist, seed] = rows
                    writer.writerows(dict(row, n=n, distribution=dist, seed=seed) for row in rows)
                    stream.flush()
    if sha256(ROOT / exe) != metadata["executable_sha256"]:
        raise RuntimeError("Executable changed during measurement")
    lines = (analyze_filter(out, cases, experiment.stage) if mode == "filter"
             else analyze_full(cases, experiment.stage))
    samples = sum(map(len, cases.values()))
    exact = samples + len(cases) * len(algs)
    lines += ["", f"{samples} muestras y {exact} salidas exactas con calentamientos."]
    write_text(out / "summary.md", "\n".join(lines))
    print(lines[-1], flush=True)
    if mode == "filter":
        print((out / "gate.json").read_text(encoding="utf-8"), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("filter", "full"))
    parser.add_argument("--e047", action="store_true", help="Run the preregistered E047 variant")
    args = parser.parse_args()
    experiment = E047 if args.e047 else E046
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        parser.error(f"{experiment.stage} requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        parser.error(f"{experiment.stage} requires taskset -c 2")
    out = experiment.directory(args.mode)
    out.mkdir(exist_ok=False)
    try:
        execute(out, args.mode, experiment)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
