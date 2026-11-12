"""Measure and archive the budget of sibling vqsort partitions in WSL."""

from collections import defaultdict
import csv
from datetime import datetime, timezone
import gzip
import os
from pathlib import Path
import platform
import random
import shutil
from statistics import median
import sys

from e045_cells import HIGHWAY_COMMIT, command_output, run_logged, sha256
from e046_windows import check_hashes, write_json, write_text


ROOT = Path(__file__).resolve().parent
N, CPU, REPEATS = 10_000_000, 2, 7
CASES = ("uniform", "prefix_distinct")
SEEDS = (42701, 91009)
ARMS = ("clean", "trace")
SOURCE = "e058_vq_pairs.cpp"
PARTITION = b"  const size_t bound = Partition(d, st, keys, num, pivot, buf);"
HOOK = b"""#ifdef SUPERSORT_TRACE
  const auto e058_start = ::e058::Clock::now();
#endif
""" + PARTITION + b"""
#ifdef SUPERSORT_TRACE
  const auto e058_stop = ::e058::Clock::now();
  ::e058::record(keys, num, bound, remaining_levels, GetLane(pivot),
                 e058_stop - e058_start);
#endif"""


def build(out):
    repo = Path("vendor/highway")
    git = ["git", "-C", str(repo)]
    if command_output([*git, "rev-parse", "HEAD"]) != HIGHWAY_COMMIT:
        raise RuntimeError("Unexpected Highway revision")
    if command_output([*git, "status", "--porcelain", "--untracked-files=all"]):
        raise RuntimeError("Modified Highway checkout")
    for name in (SOURCE, "e058_vq_pairs.py", "e045_cells.py", "e046_windows.py"):
        shutil.copyfile(ROOT / name, out / name)
    shutil.copyfile(ROOT / "notes/E058 - Prerregistro pares de vqsort.md", out / "preregistration.md")
    shutil.copytree(ROOT / repo / "hwy", out / repo / "hwy")
    shutil.copyfile(ROOT / repo / "LICENSE", out / repo / "LICENSE")
    header = out / repo / "hwy/contrib/sort/vqsort-inl.h"
    upstream = header.read_bytes()
    if upstream.count(PARTITION) != 1:
        raise RuntimeError("Partition hook is ambiguous")
    header.write_bytes(upstream.replace(PARTITION, HOOK))
    sources = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}
    folder = out.relative_to(ROOT)
    highway = folder / repo
    flags = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", f"-I{highway}",
             str(folder / SOURCE), str(highway / "hwy/abort.cc"), "-pthread"]
    binaries, commands, libraries = {}, {}, {}
    for arm in ARMS:
        exe = folder / f"e058_{arm}"
        binaries[arm] = str(exe)
        define = ["-DSUPERSORT_TRACE"] if arm == "trace" else []
        command = [*flags, *define, "-o", str(exe)]
        commands[arm] = command
        run_logged(out, f"build-{arm}", command)
        linkage = command_output(["ldd", str(exe)])
        write_text(out / f"ldd-{arm}.txt", linkage)
        for line in linkage.splitlines():
            if "=> not found" in line:
                raise RuntimeError(f"Unresolved dependency: {line.strip()}")
            path = line.split("=>", 1)[-1].strip().partition(" ")[0]
            if path.startswith("/"):
                libraries[path] = sha256(Path(path))
    check_hashes(out, sources)
    return binaries, {
        "flags": commands,
        "compiler": command_output(["g++", "--version"]),
        "compiler_target": command_output(["g++", "-dumpmachine"]),
        "source_files_sha256": sources,
        "upstream_header_sha256": sha256(ROOT / repo / "hwy/contrib/sort/vqsort-inl.h"),
        "executable_sha256": {arm: sha256(ROOT / exe) for arm, exe in binaries.items()},
        "dynamic_library_sha256": libraries,
        "vendor": {"highway": HIGHWAY_COMMIT},
    }


def read_run(path, arm):
    totals, clocks, partitions = [], [], {}
    with path.open(newline="", encoding="ascii") as stream:
        for tag, *fields in csv.reader(stream):
            values = tuple(map(int, fields))
            if tag == "total" and len(values) == 1:
                totals.extend(values)
            elif tag == "clock" and len(values) == 1:
                clocks.extend(values)
            elif tag == "partition" and len(values) == 6:
                offset, size, bound, levels, pivot, ns = values
                key = (offset, size, levels)
                if (key in partitions or offset < 0 or offset + size > N
                        or not 0 < bound <= size or levels < 1 or not 0 <= pivot < 2**32 or ns < 0):
                    raise RuntimeError(f"Invalid partition {values} in {path}")
                partitions[key] = (bound, ns)
            else:
                raise RuntimeError(f"Invalid record {tag} in {path}")
    if len(totals) != 1 or totals[0] <= 0:
        raise RuntimeError(f"Invalid total in {path}")
    if arm == "clean":
        if clocks or partitions:
            raise RuntimeError(f"Unexpected trace in {path}")
        return {"total_ns": totals[0]}
    if len(clocks) != 2048 or min(clocks) < 0 or not partitions:
        raise RuntimeError(f"Incomplete trace in {path}")

    root = next(iter(partitions))
    if root[:2] != (0, N):
        raise RuntimeError(f"Missing root partition in {path}")
    if sum(ns for _, ns in partitions.values()) > totals[0]:
        raise RuntimeError(f"Partition clocks exceed sort time in {path}")
    clock = median(clocks)
    paired, ideal, corrected, large_ideal, count = 0, 0, 0, 0, 0
    children = set()
    for (offset, size, levels), (bound, _) in partitions.items():
        left = (offset, bound, levels - 1)
        right = (offset + bound, size - bound, levels - 1)
        if left in partitions:
            children.add(left)
        if right in partitions:
            children.add(right)
        if left in partitions and right in partitions:
            tleft, tright = partitions[left][1], partitions[right][1]
            shorter = min(tleft, tright)
            paired += tleft + tright
            ideal += shorter
            corrected += max(0, shorter - clock)
            if min(left[1], right[1]) >= 1024:
                large_ideal += shorter
            count += 1
    if children != partitions.keys() - {root}:
        raise RuntimeError(f"Disconnected partition trace in {path}")
    return {"total_ns": totals[0], "partition_ns": sum(ns for _, ns in partitions.values()),
            "pair_ns": paired, "ideal_ns": ideal, "corrected_ns": corrected,
            "large_ideal_ns": large_ideal, "clock_ns": clock, "pairs": count,
            "top_two_ns": sum(ns for (_, _, depth), (_, ns) in partitions.items() if depth >= root[2] - 1),
            "partitions": len(partitions)}


def summarize(out, samples):
    grouped = defaultdict(list)
    for row in samples:
        if row["round"] >= 0:
            grouped[row["family"], row["seed"], row["arm"]].append(row)
    lines = ["# E058 — Presupuesto de pares de particiones de vqsort", "",
             "Medianas en ms, salvo la calibración en ns y el número de pares. `Ideal` suma la menor duración de cada par. "
             "`≥1024` restringe esa suma a pares con ambos hijos de al menos 1.024 claves.", "",
             "| Familia | Semilla | Vqsort | Traza | Partición total | Tiempo en pares | Ideal bruto | Ideal corregido | ≥1024 | Dos niveles superiores | Requerido | Reloj (ns) | Pares |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    failed, uncertain = [], []
    for family in CASES:
        for seed in SEEDS:
            base, trace = (grouped[family, seed, arm] for arm in ARMS)
            if len(base) != REPEATS or len(trace) != REPEATS:
                raise RuntimeError("Wrong number of measured rounds")
            clean_ns = median(row["total_ns"] for row in base)
            p = {field: median(row[field] for row in trace) for field in trace[0]
                 if field not in ("family", "seed", "round", "arm")}
            target = clean_ns / 5
            cells = [clean_ns, p["total_ns"], p["partition_ns"], p["pair_ns"], p["ideal_ns"],
                     p["corrected_ns"], p["large_ideal_ns"], p["top_two_ns"], target]
            lines.append("| " + " | ".join([family, str(seed), *(f"{ns / 1e6:.3f}" for ns in cells),
                                           str(p["clock_ns"]), str(p["pairs"])]) + " |")
            label = f"{family}/{seed}"
            if p["ideal_ns"] < target:
                failed.append(label)
            elif p["corrected_ns"] < target or (p["total_ns"] > 1.15 * clean_ns
                                                and p["corrected_ns"] - target < 2e6):
                uncertain.append(label)
    decision = "descartar" if failed else "recalibrar" if uncertain else "contrastar alternancia"
    n = len(samples)
    measured = n - len(CASES) * len(SEEDS) * len(ARMS)
    lines.extend(("", f"**Decisión: {decision}.**", "",
                  "Por debajo incluso en el modelo bruto: " + (", ".join(failed) or "ninguna") + ".",
                  "Margen incierto: " + (", ".join(uncertain) or "ninguna") + ".", "",
                  f"{measured} tiempos completos y {n} salidas exactas con calentamientos. Los logs de cada brazo conservan la traza sin resumir."))
    write_text(out / "summary.md", "\n".join(lines))
    write_json(out / "gate.json", {"decision": decision, "failed": failed, "uncertain": uncertain,
                                   "samples": measured, "checked": n})
    print(f"{measured} measured, {n} verified, decision: {decision}", flush=True)


def main():
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        raise SystemExit("E058 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        raise SystemExit("E058 requires taskset -c 2")
    out = ROOT / "results/e058_vq_pairs"
    out.mkdir(exist_ok=False)
    try:
        binaries, evidence = build(out)
        write_text(out / "lscpu.txt", command_output(["lscpu"]))
        write_text(out / "load-before.txt", command_output(["uptime"]) + "\n" +
                   command_output(["ps", "-eo", "pid,psr,pcpu,stat,comm", "--sort=-pcpu"]))
        write_json(out / "metadata.json", {
            **evidence, "utc": datetime.now(timezone.utc).isoformat(), "platform": platform.platform(),
            "python": sys.version, "affinity": sorted(os.sched_getaffinity(0)),
            "page_size": os.sysconf("SC_PAGE_SIZE"), "n": N, "cases": CASES,
            "seeds": SEEDS, "repeats": REPEATS, "warmups": 1, "arms": ARMS,
            "order": "Separate processes, shuffled arms per round, paired pivot states",
            "raw_format": "total,ns | clock,ns | partition,offset,size,bound,remaining_levels,pivot,ns",
        })
        samples = []
        for family in CASES:
            for seed in SEEDS:
                order = random.Random(seed ^ 0x09BCAC24CE2FA4A1)
                for round_ in range(-1, REPEATS):
                    for arm in order.sample(ARMS, len(ARMS)):
                        label = f"{family}-{seed}-{round_}-{arm}"
                        path = run_logged(out, label, [binaries[arm], str(N), family, str(seed), str(round_)])
                        sample = read_run(path, arm)
                        samples.append(dict(family=family, seed=seed, round=round_, arm=arm, **sample))
                        if arm == "trace":
                            with path.open("rb") as src, gzip.open(f"{path}.gz", "xb", compresslevel=3) as dst:
                                shutil.copyfileobj(src, dst)
                            path.unlink()

        with (out / "raw.csv").open("x", newline="", encoding="ascii") as stream:
            fields = list(dict.fromkeys(field for row in samples for field in row))
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(samples)
        check_hashes(out, evidence["source_files_sha256"])
        for arm, exe in binaries.items():
            if sha256(ROOT / exe) != evidence["executable_sha256"][arm]:
                raise RuntimeError(f"Executable changed during measurement: {exe}")
        for path, digest in evidence["dynamic_library_sha256"].items():
            if sha256(Path(path)) != digest:
                raise RuntimeError(f"Dynamic dependency changed during measurement: {path}")
        summarize(out, samples)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
