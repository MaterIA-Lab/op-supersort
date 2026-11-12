"""Run and archive the E063 exchange-partition filter in Ubuntu WSL."""

import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import platform
import shutil
from statistics import median
import sys

from e045_cells import HIGHWAY_COMMIT, command_output, run_logged, sha256
from e046_windows import check_hashes, write_json, write_text
from e056_binary import verified_count
from e062_position_bitmap import AFTER_RECURSE, RECURSE_HEADER, RECURSE_SORT, RECURSE_TEMPLATE


ROOT = Path(__file__).resolve().parent
N, CPU, REPEATS = 10_000_000, 2, 7
SEEDS = (42701, 91009)
TARGETS = ("uniform", "prefix_distinct")
CASES = (*TARGETS, "skew95", "separated")
ARMS = ("partition", "exchange")
FIELDS = ("round", "algorithm", "band", "ms", "population_keys", "sampled_keys", "spans", "written_keys")
ROOT_BAND = N.bit_length() - 1
SOURCE = "e063_exchange_partition.cpp"
HEADER = "hwy/contrib/sort/vqsort-inl.h"
PARTITION = b"  const size_t bound = Partition(d, st, keys, num, pivot, buf);"
CAPTURE = b"""  if constexpr (Capture) {
    ::e063::capture(keys, num, GetLane(pivot));
  }
"""


def add_capture(header):
    upstream = header.read_bytes()
    if (any(upstream.count(anchor) != 1 for anchor in (RECURSE_HEADER, AFTER_RECURSE, PARTITION))
            or b"::e063::capture" in upstream):
        raise RuntimeError("Unexpected Highway anchors for E063 capture")
    start = upstream.index(RECURSE_HEADER)
    stop = upstream.index(AFTER_RECURSE)
    if not start < upstream.index(PARTITION) < stop:
        raise RuntimeError("Unexpected Highway Recurse boundaries")
    body = upstream[start:stop]
    if body.count(RECURSE_SORT) != 2:
        raise RuntimeError("Expected two recursive kSort calls in Recurse")
    body = body.replace(
        RECURSE_TEMPLATE, b"template <RecurseMode mode, bool Capture = false, class D, class Traits, typename T>", 1)
    body = body.replace(PARTITION, CAPTURE + PARTITION)
    body = body.replace(RECURSE_SORT, b"Recurse<RecurseMode::kSort, Capture>")
    header.write_bytes(upstream[:start] + body + upstream[stop:])


def build(out):
    repo = Path("vendor/highway")
    git = ["git", "-C", str(repo)]
    if command_output([*git, "rev-parse", "HEAD"]) != HIGHWAY_COMMIT:
        raise RuntimeError("Unexpected Highway revision")
    if command_output([*git, "status", "--porcelain", "--untracked-files=all"]):
        raise RuntimeError("Modified Highway checkout")
    names = ("e063_exchange_partition.py", SOURCE, "include/supersort/exchange_partition_u32.hpp",
             "e045_cells.py", "e046_windows.py", "e056_binary.py", "e062_position_bitmap.py")
    for name in names:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copyfile(ROOT / "notes/E063 - Prerregistro intercambio de bloques.md", out / "preregistration.md")
    shutil.copytree(ROOT / repo / "hwy", out / repo / "hwy")
    shutil.copyfile(ROOT / repo / "LICENSE", out / repo / "LICENSE")
    header = out / repo / HEADER
    upstream_hash = sha256(header)
    add_capture(header)
    sources = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}

    folder = out.relative_to(ROOT)
    highway = folder / repo
    exe = folder / "e063_exchange_partition"
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", f"-I{highway}",
               f"-I{folder / 'include'}", str(folder / SOURCE), str(highway / "hwy/abort.cc"),
               "-pthread", "-o", str(exe)]
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
        "upstream_header_sha256": upstream_hash,
        "executable_sha256": sha256(ROOT / exe),
        "dynamic_library_sha256": libraries,
        "vendor": {"highway": HIGHWAY_COMMIT},
    }


@dataclass(frozen=True)
class Measurement:
    ms: float
    population: int
    sampled: int
    spans: int
    written: int

    @property
    def coverage(self):
        return self.population, self.sampled, self.spans


def read_case(path, primary):
    with path.open(newline="", encoding="ascii") as stream:
        rows = list(csv.DictReader(stream, fieldnames=FIELDS))
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise RuntimeError(f"Invalid driver columns in {path}")

    measurements = {}
    for row in rows:
        round_, arm, band = int(row["round"]), row["algorithm"], int(row["band"])
        reading = Measurement(float(row["ms"]), *(int(row[field]) for field in FIELDS[4:]))
        if not math.isfinite(reading.ms) or reading.ms <= 0 or reading.written < 0:
            raise RuntimeError(f"Invalid measurement in {path}: {row}")
        if arm == "vq":
            if band != -1 or (*reading.coverage, reading.written) != (0, 0, 0, 0):
                raise RuntimeError(f"Unexpected vqsort telemetry in {path}: {row}")
        else:
            if arm not in ARMS or not 7 <= band <= ROOT_BAND:
                raise RuntimeError(f"Unexpected partition arm or size band in {path}: {row}")
            min_size, max_size = 1 << band, min(N, (1 << (band + 1)) - 1)
            max_spans = 64 if band < 14 else 1
            if not (1 <= reading.spans <= max_spans
                    and reading.spans * min_size <= reading.sampled <= reading.spans * max_size
                    and reading.sampled <= reading.population):
                raise RuntimeError(f"Invalid partition coverage in {path}: {row}")
            if not primary and (band != ROOT_BAND or reading.coverage != (N, N, 1)):
                raise RuntimeError(f"Unexpected control geometry in {path}: {row}")
        key = round_, arm, band
        if key in measurements:
            raise RuntimeError(f"Duplicate measurement in {path}: {row}")
        measurements[key] = reading

    bands = sorted({band for _, arm, band in measurements if arm == "partition"})
    expected = {(round_, arm, band) for round_ in range(REPEATS) for arm in ARMS for band in bands}
    if primary:
        expected.update((round_, "vq", -1) for round_ in range(REPEATS))
    if ROOT_BAND not in bands or measurements.keys() != expected:
        raise RuntimeError(f"Unexpected measurement counts in {path}")

    for band in bands:
        coverage = measurements[0, "partition", band].coverage
        for arm in ARMS:
            written = measurements[0, arm, band].written
            for round_ in range(REPEATS):
                reading = measurements[round_, arm, band]
                if reading.coverage != coverage or reading.written != written:
                    raise RuntimeError(f"Inconsistent replay telemetry in {path}, round {round_}, band {band}")
    return rows, measurements, bands


def round_totals(measurements, bands, round_):
    partition_ms, exchange_ms, projected = [], [], []
    partition_writes, exchange_writes = [], []
    for band in bands:
        control = measurements[round_, "partition", band]
        candidate = measurements[round_, "exchange", band]
        weight = control.population / control.sampled
        partition_ms.append(control.ms)
        exchange_ms.append(candidate.ms)
        projected.append((control.ms - candidate.ms) * weight)
        partition_writes.append(control.written * weight)
        exchange_writes.append(candidate.written * weight)
    return tuple(math.fsum(values) for values in
                 (partition_ms, exchange_ms, projected, partition_writes, exchange_writes))


def summarize(out, cases, verified):
    lines = ["# E063 — Partición binaria por intercambio de posiciones", "",
             "Medianas en ms. Los tiempos de partición suman los lotes medidos de cada ronda. "
             "El ahorro proyectado pondera la diferencia pareada de cada clase por población sobre muestra.", "",
             "| Familia | Semilla | Partition | Exchange | Ahorro en muestra | Ahorro proyectado | Vqsort | Ahorro requerido |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    work = ["## Cobertura y escrituras ponderadas", "",
            "Se cuentan posiciones de 32 bits solicitadas al array. Partition incluye los stores anchos del bucle "
            "y de sus vectores guardados. Exchange incluye también los intercambios de cola. "
            "Las escrituras proyectadas usan los mismos pesos por clase que el tiempo.", "",
            "| Familia | Semilla | Tramos por brazo | Claves muestreadas | Claves de población | Partition (M posiciones) | Exchange (M posiciones) |",
            "|---|---:|---:|---:|---:|---:|---:|"]
    failures = []
    checked_partitions = checked_telemetry = checked_captures = checked_vq = 0
    for (family, seed), (rows, measurements, bands) in cases.items():
        totals = [round_totals(measurements, bands, round_) for round_ in range(REPEATS)]
        partition, exchange, projected, partition_writes, exchange_writes = map(median, zip(*totals))
        raw_saving = median(control - candidate for control, candidate, *_ in totals)
        values = [f"{value:.6f}" for value in (partition, exchange, raw_saving, projected)]
        if family in TARGETS:
            vq = median(measurements[round_, "vq", -1].ms for round_ in range(REPEATS))
            required = 0.2 * vq
            values.extend((f"{vq:.6f}", f"{required:.6f}"))
            if projected < required:
                failures.append(f"{family}/{seed} proyectó {projected:.6f} ms frente a {required:.6f} ms requeridos.")
            checked_captures += 1
            checked_vq += REPEATS + 1
        else:
            values.extend(("—", "—"))
        lines.append("| " + " | ".join([family, str(seed), *values]) + " |")

        first_round = [measurements[0, "partition", band] for band in bands]
        spans = sum(reading.spans for reading in first_round)
        sampled = sum(reading.sampled for reading in first_round)
        population = sum(reading.population for reading in first_round)
        cells = [family, str(seed), str(spans), str(sampled), str(population),
                 f"{partition_writes / 1e6:.3f}", f"{exchange_writes / 1e6:.3f}"]
        work.append("| " + " | ".join(cells) + " |")
        checked_partitions += spans * len(ARMS) * (REPEATS + 1)
        checked_telemetry += spans

    samples = sum(len(rows) for rows, _, _ in cases.values())
    verdict = ("Puerta superada para probar la integración."
               if not failures else "Puerta fallida. Se cierra esta implementación.")
    counts = (f"{samples} muestras, {checked_partitions} particiones verificadas y {checked_vq} salidas de vqsort "
              f"con calentamientos. Además, {checked_telemetry} particiones en la pasada de telemetría, "
              f"{checked_captures} capturas exactas y {verified} comprobaciones previas.")
    lines.extend(("", *work, "", verdict, "", *(f"- {failure}" for failure in failures), "", counts))
    write_text(out / "summary.md", "\n".join(lines))
    write_json(out / "gate.json", {"passed": not failures, "failures": failures, "samples": samples,
                                   "checked": checked_partitions + checked_telemetry + checked_vq + checked_captures,
                                   "checked_partitions": checked_partitions, "checked_vq": checked_vq,
                                   "checked_telemetry": checked_telemetry,
                                   "checked_captures": checked_captures, "verified": verified})
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
        "matrix": {"n": N, "cases": CASES, "seeds": SEEDS, "arms": ARMS,
                   "repeats": REPEATS, "warmups": 1, "vq_cases": TARGETS},
        "timing": "Partition and exchange run sampled spans in bands, with scratch and tails included. "
                  "Vqsort sorts the full array. Capture, common input copy and checks are outside.",
        "sampling": "One capture per primary case, up to 64 spans per band below 16384 and one otherwise.",
        "write_metric": "Requested uint32 array slots, measured outside timing. Highway counts StoreLeftRight stores. "
                        "Exchange counts all its stores, including the tail.",
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
                case = read_case(path, family in TARGETS)
                cases[family, seed] = case
                writer.writerows(dict(row, n=N, family=family, seed=seed) for row in case[0])
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
        raise SystemExit("E063 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        raise SystemExit("E063 requires taskset -c 2")
    out = ROOT / "results/e063_exchange_partition"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
