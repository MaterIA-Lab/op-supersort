"""Measure and archive the E067 IPS2Ra block phases in Ubuntu WSL."""

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
from e056_binary import verified_count
from e066_inplace_blocks import (
    ARMS, CPU, DRIVER_SOURCES, FIELDS as BASE_FIELDS, GOAL, IPS_HEADER, MAX_BINS,
    N, PHASE_TOLERANCE_MS, REPEATS, ROOT, SEEDS, TARGETS, add_partition_only,
)


FIELDS = (*BASE_FIELDS, "class_ms", "permute_ms", "margins_ms")
PHASES = ("class_ms", "permute_ms", "margins_ms", "rest_ms")
PHASE_NAMES = dict(zip(PHASES, ("Clasificación", "Permutación", "Márgenes", "Resto")))
PARTITION_HEADER = "vendor/ips2ra/include/ips2ra/partitioning.hpp"
REFERENCE_CSV = "e066_reference_raw.csv"
PARTITION = b"""void Sorter<Cfg>::partition(const iterator begin, const iterator end, int level,
                            diff_t* const bucket_start, const int my_id,
                            const int num_threads) {"""
PARTITION_END = b"}\n\n}  // namespace detail"
PHASE_HOOKS = (
    (b"    // Set parameters for this partitioning step",
     b"    const auto e067_start = ::e067::Clock::now();\n\n"
     b"    // Set parameters for this partitioning step"),
    (b"        sequentialClassification();",
     b"        sequentialClassification();\n"
     b"    const auto e067_classified = ::e067::Clock::now();"),
    (b"    // Cleanup",
     b"    const auto e067_permuted = ::e067::Clock::now();\n\n"
     b"    // Cleanup"),
    (b"    local_.reset();",
     b"    local_.reset();\n"
     b"    ::e067::record(e067_start, e067_classified, e067_permuted, ::e067::Clock::now());"),
)


def add_phase_hooks(header):
    upstream = header.read_bytes()
    if (upstream.count(PARTITION) != 1 or upstream.count(PARTITION_END) != 1
            or b"::e067::" in upstream):
        raise RuntimeError("Unexpected IPS2Ra partition function for E067")
    start = upstream.index(PARTITION)
    stop = upstream.index(PARTITION_END)
    if start + len(PARTITION) >= stop:
        raise RuntimeError("Unexpected IPS2Ra partition boundaries")
    body = upstream[start:stop]
    if any(body.count(anchor) != 1 for anchor, _ in PHASE_HOOKS):
        raise RuntimeError("Unexpected IPS2Ra phase hooks")
    offsets = [body.index(anchor) for anchor, _ in PHASE_HOOKS]
    if offsets != sorted(offsets):
        raise RuntimeError("Unexpected IPS2Ra phase order")
    for anchor, replacement in PHASE_HOOKS:
        body = body.replace(anchor, replacement)
    header.write_bytes(upstream[:start] + body + upstream[stop:])


def build(out):
    names = ("e067_block_phases.py", "e066_inplace_blocks.py", *DRIVER_SOURCES,
             "e045_cells.py", "e046_windows.py", "e056_binary.py")
    for name in names:
        shutil.copyfile(ROOT / name, out / name)
    shutil.copyfile(ROOT / "notes/E067 - Prerregistro fases de bloques.md", out / "preregistration.md")
    shutil.copyfile(ROOT / "results/e066_inplace_blocks/raw.csv", out / REFERENCE_CSV)

    versions = {}
    for name in ("highway", "ips2ra"):
        revision, sources_dir, license_file = VENDORS[name]
        repo = Path("vendor") / name
        git = ["git", "-C", str(repo)]
        if command_output([*git, "rev-parse", "HEAD"]) != revision:
            raise RuntimeError(f"Unexpected {name} revision")
        if command_output([*git, "status", "--porcelain", "--untracked-files=all"]):
            raise RuntimeError(f"Modified {name} checkout")
        shutil.copytree(ROOT / repo / sources_dir, out / repo / sources_dir)
        shutil.copyfile(ROOT / repo / license_file, out / repo / license_file)
        versions[name] = revision
    upstream_hashes = {name: sha256(out / name) for name in (IPS_HEADER, PARTITION_HEADER)}
    add_partition_only(out / IPS_HEADER)
    add_phase_hooks(out / PARTITION_HEADER)
    sources = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}

    folder = out.relative_to(ROOT)
    vendor = folder / "vendor"
    exe = folder / "e067_block_phases"
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", "-DSUPERSORT_BLOCK_PHASES",
               f"-I{vendor / 'highway'}", f"-I{vendor / 'ips2ra/include'}",
               *(str(folder / source) for source in DRIVER_SOURCES), str(vendor / "highway/hwy/abort.cc"),
               "-ltbb", "-latomic", "-pthread", "-o", str(exe)]
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
        "upstream_headers_sha256": upstream_hashes,
        "executable_sha256": sha256(ROOT / exe),
        "dynamic_library_sha256": libraries,
        "vendor": versions,
        "tbb_headers_package": command_output(["dpkg-query", "-W", "libtbb-dev"]),
    }


def read_case(path):
    with path.open(newline="", encoding="ascii") as stream:
        rows = list(csv.DictReader(stream, fieldnames=FIELDS))
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise RuntimeError(f"Invalid driver columns in {path}")
    actual = Counter((int(row["round"]), row["algorithm"]) for row in rows)
    expected = Counter((round_, arm) for round_ in range(REPEATS) for arm in ARMS)
    if actual != expected:
        raise RuntimeError(f"Unexpected measurement counts in {path}")

    for row in rows:
        ms, split, finish, classified, permuted, margins = (
            float(row[field]) for field in ("ms", "split_ms", "finish_ms", *PHASES[:3])
        )
        phases = (classified, permuted, margins)
        if (not all(map(math.isfinite, (ms, split, finish, *phases))) or ms <= 0 or split < 0 or finish <= 0
                or split + finish > ms + PHASE_TOLERANCE_MS or min(phases) < 0
                or math.fsum(phases) > split + PHASE_TOLERANCE_MS):
            raise RuntimeError(f"Invalid phase timing in {path}: {row}")
        arm, route = row["algorithm"], row["route"]
        bins, largest = int(row["bins"]), int(row["largest"])
        if arm == "vq":
            if route != "vq" or (split, bins, largest, *phases) != (0, 0, 0, 0, 0, 0):
                raise RuntimeError(f"Unexpected vqsort telemetry in {path}: {row}")
        elif route == "blocks":
            if not (1 <= bins <= MAX_BINS and 1 <= largest <= N and bins * largest >= N and classified > 0):
                raise RuntimeError(f"Invalid block distribution in {path}: {row}")
        elif route not in ("bypass", "reserve") or (bins, largest, *phases) != (0, 0, 0, 0, 0):
            raise RuntimeError(f"Invalid fallback telemetry in {path}: {row}")
    return rows


def reference_medians(path):
    with path.open(newline="", encoding="ascii") as stream:
        rows = list(csv.DictReader(stream))
    expected = {(family, seed, arm, round_) for family in TARGETS for seed in SEEDS
                for arm in ARMS for round_ in range(REPEATS)}
    times = {}
    for row in rows:
        family, seed = row["family"], int(row["seed"])
        if family not in TARGETS or seed not in SEEDS or int(row["n"]) != N:
            continue
        key = family, seed, row["algorithm"], int(row["round"])
        ms = float(row["ms"])
        if key in times or not math.isfinite(ms) or ms <= 0:
            raise RuntimeError(f"Invalid E066 reference in {path}: {row}")
        times[key] = ms
    if times.keys() != expected:
        raise RuntimeError(f"Incomplete E066 reference in {path}")
    return {(family, seed, arm): median(times[family, seed, arm, round_] for round_ in range(REPEATS))
            for family in TARGETS for seed in SEEDS for arm in ARMS}


def summarize(out, cases, reference, verified):
    lines = ["# E067 — Presupuesto por fase del reparto de E066", "",
             "Medianas en ms. El resto se calcula por ronda como elección y reparto menos las tres fases medidas.", "",
             "| Familia | Semilla | Brazo | Total | Reparto | Clasificación | Permutación | Márgenes | Resto | Finalización | Rangos | Tramo mayor | Rutas |",
             "|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    optimistic = ["## Presupuesto al suprimir una fase", "",
                  "Tiempo hipotético como mediana de total menos fase por ronda. "
                  "El margen resta ese tiempo al 80% de la mediana de vqsort de la misma tanda.", "",
                  "| Familia | Semilla | Brazo | Fase | Fase medida | Tiempo hipotético | Objetivo | Margen |",
                  "|---|---:|---|---|---:|---:|---:|---:|"]
    prior = ["## Comparación con E066", "",
             "Medianas de tandas distintas. La diferencia da contexto sobre la instrumentación y la variación entre tandas.", "",
             "| Familia | Semilla | Brazo | E066 | E067 | E067 − E066 | Diferencia relativa |",
             "|---|---:|---|---:|---:|---:|---:|"]
    failed = {phase: [] for phase in PHASES}
    minimums = {phase: math.inf for phase in PHASES}
    for (family, seed), rows in cases.items():
        by_arm = {arm: [row for row in rows if row["algorithm"] == arm] for arm in ARMS}
        target = median(float(row["ms"]) for row in by_arm["vq"]) / GOAL
        for arm, group in by_arm.items():
            totals = [float(row["ms"]) for row in group]
            split = [float(row["split_ms"]) for row in group]
            finish = [float(row["finish_ms"]) for row in group]
            measured = {phase: [float(row[phase]) for row in group] for phase in PHASES[:3]}
            measured["rest_ms"] = [
                max(0.0, time - math.fsum(parts)) for time, *parts in zip(split, *measured.values())
            ]
            phase_medians = {phase: median(values) for phase, values in measured.items()}
            total = median(totals)
            values = (total, median(split), *phase_medians.values(), median(finish))
            blocks = [row for row in group if row["route"] == "blocks"]
            geometry = [str(median(int(row[field]) for row in blocks)) if blocks else "—"
                        for field in ("bins", "largest")]
            routes = ", ".join(f"{route} {count}" for route, count in
                               sorted(Counter(row["route"] for row in group).items()))
            cells = [family, str(seed), arm, *(f"{value:.6f}" for value in values), *geometry, routes]
            lines.append("| " + " | ".join(cells) + " |")

            baseline = reference[family, seed, arm]
            cells = [family, str(seed), arm, f"{baseline:.6f}", f"{total:.6f}",
                     f"{total - baseline:.6f}", f"{total / baseline - 1:+.2%}"]
            prior.append("| " + " | ".join(cells) + " |")
            if arm == "vq":
                continue

            for phase, durations in measured.items():
                hypothetical = median(time - duration for time, duration in zip(totals, durations))
                margin = target - hypothetical
                if arm == "adaptive":
                    minimums[phase] = min(minimums[phase], margin)
                    if margin <= 0:
                        failed[phase].append(f"{family}/{seed}")
                values = (phase_medians[phase], hypothetical, target, margin)
                cells = [family, str(seed), arm, PHASE_NAMES[phase], *(f"{value:.6f}" for value in values)]
                optimistic.append("| " + " | ".join(cells) + " |")

    eligible = [phase for phase in PHASES if not failed[phase]]
    verdict = ("Fases con margen en las cuatro entradas: " + ", ".join(PHASE_NAMES[phase] for phase in eligible) + "."
               if eligible else "Suprimir una sola fase deja al adaptativo fuera de la meta en alguna entrada.")
    samples = sum(len(rows) for rows in cases.values())
    checked = samples + len(cases) * len(ARMS)
    counts = (f"{samples} muestras y {checked} salidas exactas con calentamientos. "
              f"{verified} comprobaciones previas.")
    lines.extend(("", *optimistic, "", *prior, "", verdict, "", counts))
    write_text(out / "summary.md", "\n".join(lines))
    write_json(out / "gate.json", {"passed": bool(eligible), "eligible_phases": eligible,
                                   "failed_cases_by_phase": failed, "min_adaptive_budget_ms": minimums,
                                   "samples": samples, "checked": checked, "verified": verified})
    print(counts, flush=True)
    print(verdict, flush=True)


def execute(out):
    exe, evidence = build(out)
    reference = reference_medians(out / REFERENCE_CSV)
    write_text(out / "lscpu.txt", command_output(["lscpu"]))
    write_json(out / "metadata.json", {
        **evidence,
        "utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "affinity": sorted(os.sched_getaffinity(0)),
        "page_size": os.sysconf("SC_PAGE_SIZE"),
        "matrix": {"n": N, "cases": TARGETS, "seeds": SEEDS, "arms": ARMS, "repeats": REPEATS, "warmups": 1},
        "timing": "E066 full-sort timing with nested IPS2Ra classification, permutation and margins clocks. "
                  "The phase remainder includes sample, table, allocation, release and call overhead.",
        "comparison": "E066 raw samples are archived for context across runs.",
    })
    verified = verified_count(run_logged(out, "verify", [str(exe), "--verify"]))
    write_text(out / "load-before.txt", command_output(["uptime"]) + "\n" +
               command_output(["ps", "-eo", "pid,psr,pcpu,stat,comm", "--sort=-pcpu"]))
    cases = {}
    with (out / "raw.csv").open("x", newline="", encoding="ascii") as stream:
        writer = csv.DictWriter(stream, fieldnames=("n", "family", "seed", *FIELDS))
        writer.writeheader()
        for family in TARGETS:
            for seed in SEEDS:
                path = run_logged(out, f"case-{N}-{family}-{seed}",
                                  [str(exe), str(N), family, str(seed), str(REPEATS)])
                rows = read_case(path)
                cases[family, seed] = rows
                writer.writerows(dict(row, n=N, family=family, seed=seed) for row in rows)
                stream.flush()

    check_hashes(out, evidence["source_files_sha256"])
    if sha256(ROOT / exe) != evidence["executable_sha256"]:
        raise RuntimeError("Executable changed during measurement")
    for path, digest in evidence["dynamic_library_sha256"].items():
        if sha256(Path(path)) != digest:
            raise RuntimeError(f"Dynamic dependency changed during measurement: {path}")
    summarize(out, cases, reference, verified)


def main():
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        raise SystemExit("E067 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        raise SystemExit("E067 requires taskset -c 2")
    out = ROOT / "results/e067_block_phases"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
