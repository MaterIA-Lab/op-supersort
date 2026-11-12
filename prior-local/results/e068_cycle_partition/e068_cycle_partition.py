"""Run and archive E068's prepared cycle-partition filter in Ubuntu WSL."""

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
    CPU, FIELDS as BASE_FIELDS, GOAL, IPS_HEADER, MAX_BINS, N, PHASE_TOLERANCE_MS,
    REPEATS, ROOT, SEEDS, TARGETS, add_partition_only,
)


CASES = (*TARGETS, "dominant", "grouped")
ARMS = ("cycles", "blocks", "vq")
FIELDS = (*BASE_FIELDS, "writes", "misplaced")
DRIVER_SOURCES = ("e068_cycle_partition.cpp", "e066_ips_partition.cpp", "e056_vq_bridge.cpp")
KERNEL = "include/supersort/cycle_partition_u32.hpp"


def build(out):
    names = ("e068_cycle_partition.py", "e066_inplace_blocks.py", *DRIVER_SOURCES, KERNEL,
             "e045_cells.py", "e046_windows.py", "e056_binary.py")
    for name in names:
        dst = out / name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dst)
    shutil.copyfile(ROOT / "notes/E068 - Prerregistro reparto por ciclos.md", out / "preregistration.md")

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
    header = out / IPS_HEADER
    upstream_hash = sha256(header)
    add_partition_only(header)
    sources = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}

    folder = out.relative_to(ROOT)
    vendor = folder / "vendor"
    exe = folder / "e068_cycle_partition"
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17",
               f"-I{folder / 'include'}", f"-I{vendor / 'highway'}", f"-I{vendor / 'ips2ra/include'}",
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
        "upstream_ips2ra_header_sha256": upstream_hash,
        "executable_sha256": sha256(ROOT / exe),
        "dynamic_library_sha256": libraries,
        "vendor": versions,
        "tbb_headers_package": command_output(["dpkg-query", "-W", "libtbb-dev"]),
    }


def read_case(path, family):
    with path.open(newline="", encoding="ascii") as stream:
        rows = list(csv.DictReader(stream, fieldnames=FIELDS))
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise RuntimeError(f"Invalid driver columns in {path}")
    actual = Counter((int(row["round"]), row["algorithm"]) for row in rows)
    expected = Counter((round_, arm) for round_ in range(REPEATS) for arm in ARMS)
    if actual != expected:
        raise RuntimeError(f"Unexpected measurement counts in {path}")

    geometry = set()
    misplaced_counts = set()
    for row in rows:
        ms, split, finish = (float(row[field]) for field in ("ms", "split_ms", "finish_ms"))
        if (not all(map(math.isfinite, (ms, split, finish))) or ms <= 0 or split < 0 or finish <= 0
                or split + finish > ms + PHASE_TOLERANCE_MS):
            raise RuntimeError(f"Invalid phase timing in {path}: {row}")
        arm, route = row["algorithm"], row["route"]
        bins, largest, writes, misplaced = (int(row[field]) for field in ("bins", "largest", "writes", "misplaced"))
        if not 0 <= misplaced <= N:
            raise RuntimeError(f"Invalid misplaced count in {path}: {row}")
        misplaced_counts.add(misplaced)
        if arm == "vq":
            if route != "vq" or (split, bins, largest, writes) != (0, 0, 0, 0):
                raise RuntimeError(f"Unexpected vqsort telemetry in {path}: {row}")
        elif route == "reserve":
            if arm != "blocks" or (bins, largest, writes) != (0, 0, 0):
                raise RuntimeError(f"Invalid reserve fallback in {path}: {row}")
        elif (route != arm or not (1 <= bins <= MAX_BINS and 1 <= largest <= N and bins * largest >= N)
              or split <= 0 or writes != (misplaced if arm == "cycles" else 0)):
            raise RuntimeError(f"Invalid partition telemetry in {path}: {row}")
        else:
            geometry.add((bins, largest))
    if len(geometry) != 1 or len(misplaced_counts) != 1 or (family == "grouped" and misplaced_counts != {0}):
        raise RuntimeError(f"Inconsistent geometry or misplaced counts in {path}")
    return rows


def summarize(out, cases, verified):
    lines = ["# E068 — Reparto por ciclos con límites preparados", "",
             "Medianas en ms. Tabla y límites preparados en el brazo por ciclos. "
             "La puerta se aplica a las dos semillas de uniforme y prefijos amplios.", "",
             "| Familia | Semilla | Cycles | Blocks | Vqsort | Blocks / cycles | Vqsort / cycles | Margen a la meta (ms) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    phases = ["## Fases y geometría", "",
              "Las escrituras lógicas del reparto se cuentan fuera del reloj solo para cycles. "
              "Las medianas de fases incluyen respaldos y la geometría solo resume rondas repartidas.", "",
              "| Familia | Semilla | Brazo | Reparto (ms) | Finalización (ms) | Rangos | Tramo mayor | Posiciones incorrectas | Escrituras | Rutas y rondas |",
              "|---|---:|---|---:|---:|---:|---:|---:|---:|---|"]
    failures = []
    for (family, seed), rows in cases.items():
        by_arm = {arm: [row for row in rows if row["algorithm"] == arm] for arm in ARMS}
        cycles, blocks, vq = (median(float(row["ms"]) for row in by_arm[arm]) for arm in ARMS)
        block_ratio, vq_ratio = blocks / cycles, vq / cycles
        if family in TARGETS:
            if vq_ratio < GOAL:
                failures.append(f"{family}/{seed} alcanzó {vq_ratio:.6f} frente a vqsort, por debajo de {GOAL}.")
            if block_ratio <= 1:
                failures.append(f"{family}/{seed} alcanzó {block_ratio:.6f} frente a blocks, sin mejora.")
        values = (cycles, blocks, vq, block_ratio, vq_ratio, vq / GOAL - cycles)
        lines.append("| " + " | ".join([family, str(seed), *(f"{value:.6f}" for value in values)]) + " |")
        for arm, group in by_arm.items():
            split, finish = (median(float(row[field]) for row in group) for field in ("split_ms", "finish_ms"))
            partitions = [row for row in group if row["route"] in ("cycles", "blocks")]
            geometry = [str(median(int(row[field]) for row in partitions)) if partitions else "—"
                        for field in ("bins", "largest")]
            misplaced = group[0]["misplaced"]
            writes = str(median(int(row["writes"]) for row in group)) if arm == "cycles" else "—"
            route_counts = Counter(row["route"] for row in group)
            routes = ", ".join(f"{route} {count}" for route, count in sorted(route_counts.items()))
            cells = [family, str(seed), arm, f"{split:.6f}", f"{finish:.6f}", *geometry, misplaced, writes, routes]
            phases.append("| " + " | ".join(cells) + " |")

    samples = sum(len(rows) for rows in cases.values())
    checked = samples + len(cases) * len(ARMS)
    verdict = ("Puerta superada para probar el candidato con elección e histograma cobrados."
               if not failures else "Puerta fallida. Se cierra el reparto por ciclos en este filtro preparado.")
    counts = (f"{samples} muestras y {checked} salidas exactas con calentamientos. "
              f"{verified} comprobaciones previas.")
    lines.extend(("", *phases, "", verdict, "", *(f"- {failure}" for failure in failures), "", counts))
    write_text(out / "summary.md", "\n".join(lines))
    write_json(out / "gate.json", {"passed": not failures, "failures": failures,
                                   "samples": samples, "checked": checked, "verified": verified})
    print(counts, flush=True)
    print(verdict, flush=True)


def execute(out):
    exe, evidence = build(out)
    write_text(out / "lscpu.txt", command_output(["lscpu"]))
    write_json(out / "metadata.json", {
        **evidence,
        "utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "affinity": sorted(os.sched_getaffinity(0)),
        "page_size": os.sysconf("SC_PAGE_SIZE"),
        "matrix": {"n": N, "cases": CASES, "seeds": SEEDS, "arms": ARMS, "repeats": REPEATS, "warmups": 1},
        "timing": "Full sort includes cursor or scratch setup, partition, finalization and fallback. "
                  "Common input copy, range choice, exact cycle histogram, telemetry and checks are outside timing.",
        "dispatch": "In-place cycles or sequential IPS2Ra partitionOnly with 512-byte blocks and the same range map, "
                    "both followed by Highway VQSortStatic native; the vq arm sorts the same input directly.",
    })
    verified = verified_count(run_logged(out, "verify", [str(exe), "--verify"]))
    write_text(out / "load-before.txt", command_output(["uptime"]) + "\n" +
               command_output(["ps", "-eo", "pid,psr,pcpu,stat,comm", "--sort=-pcpu"]))
    cases = {}
    with (out / "raw.csv").open("x", newline="", encoding="ascii") as stream:
        writer = csv.DictWriter(stream, fieldnames=("n", "family", "seed", *FIELDS))
        writer.writeheader()
        for family in CASES:
            for seed in SEEDS:
                path = run_logged(out, f"case-{N}-{family}-{seed}",
                                  [str(exe), str(N), family, str(seed), str(REPEATS)])
                rows = read_case(path, family)
                cases[family, seed] = rows
                writer.writerows(dict(row, n=N, family=family, seed=seed) for row in rows)
                stream.flush()

    check_hashes(out, evidence["source_files_sha256"])
    if sha256(ROOT / exe) != evidence["executable_sha256"]:
        raise RuntimeError("Executable changed during measurement")
    for path, digest in evidence["dynamic_library_sha256"].items():
        if sha256(Path(path)) != digest:
            raise RuntimeError(f"Dynamic dependency changed during measurement: {path}")
    summarize(out, cases, verified)


def main():
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        raise SystemExit("E068 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        raise SystemExit("E068 requires taskset -c 2")
    out = ROOT / "results/e068_cycle_partition"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
