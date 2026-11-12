"""Run and archive the E059 sibling-partition schedule filter in Ubuntu WSL."""

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

from e045_cells import HIGHWAY_COMMIT, command_output, run_logged, sha256
from e046_windows import check_hashes, write_json, write_text
from e056_binary import verified_count


ROOT = Path(__file__).resolve().parent
N, CPU, REPEATS = 10_000_000, 2, 7
SEEDS = (42701, 91009)
TARGETS = ("uniform", "prefix_distinct")
CASES = (*TARGETS, "equal")
ARMS = ("serial", "alternate", "vq")
FIELDS = ("round", "algorithm", "ms")
GOAL = 1.25
SOURCE = "e059_pair_schedule.cpp"
HEADER = "hwy/contrib/sort/vqsort-inl.h"

RECURSE = b"""template <RecurseMode mode, class D, class Traits, typename T>
HWY_NOINLINE void Recurse(D d, Traits st, T* HWY_RESTRICT keys,
                          const size_t num, T* HWY_RESTRICT buf,
                          uint64_t* HWY_RESTRICT state,
                          const size_t remaining_levels, const size_t k = 0) {
  HWY_DASSERT(num != 0);"""
PARTITION = b"  const size_t bound = Partition(d, st, keys, num, pivot, buf);"
INSERT_BEFORE = b"""}

// Returns true if sorting is finished.
template <class D, class Traits, typename T>
HWY_INLINE bool HandleSpecialCases"""
PREPARE = b"""// E059: true means a pivot is ready; false means this range is sorted.
// Preparation follows the sorting path in Recurse above.
template <class D, class Traits, typename T>
HWY_NOINLINE bool PreparePairPivot(D d, Traits st, T* HWY_RESTRICT keys,
                                   const size_t num, T* HWY_RESTRICT buf,
                                   uint64_t* HWY_RESTRICT state,
                                   const size_t remaining_levels,
                                   Vec<D>& pivot, PivotResult& result) {
"""


def add_pivot_preparation(header):
    upstream = header.read_bytes()
    if (any(upstream.count(anchor) != 1 for anchor in (RECURSE, PARTITION, INSERT_BEFORE))
            or b"PreparePairPivot" in upstream):
        raise RuntimeError("Unexpected Highway anchors for E059 pivot preparation")
    start = upstream.index(RECURSE) + RECURSE.index(b"  HWY_DASSERT(num != 0);")
    stop = upstream.index(PARTITION)
    insert = upstream.index(INSERT_BEFORE) + len(b"}\n\n")
    if not start < stop < insert:
        raise RuntimeError("Unexpected Highway Recurse boundaries")
    body = upstream[start:stop]
    edits = (
        (b"  Vec<D> pivot;\n  PivotResult result =", b"  result =", 1),
        (b"mode == RecurseMode::kSort ? ~size_t{0} : k", b"~size_t{0}", 1),
        (b"=== Recurse depth=%zu len=%zu k=%zu", b"=== PreparePairPivot depth=%zu len=%zu", 1),
        (b"remaining_levels, num, k);", b"remaining_levels, num);", 1),
        (b"return;", b"return false;", 6),
    )
    for before, after, count in edits:
        if body.count(before) != count:
            raise RuntimeError(f"Unexpected Highway pivot preparation code near {before!r}")
        body = body.replace(before, after)
    addition = PREPARE + body + b"  return true;\n}\n\n"
    header.write_bytes(upstream[:insert] + addition + upstream[insert:])


def build(out):
    repo = Path("vendor/highway")
    git = ["git", "-C", str(repo)]
    if command_output([*git, "rev-parse", "HEAD"]) != HIGHWAY_COMMIT:
        raise RuntimeError("Unexpected Highway revision")
    if command_output([*git, "status", "--porcelain", "--untracked-files=all"]):
        raise RuntimeError("Modified Highway checkout")
    names = ("e059_pair_schedule.py", SOURCE, "include/supersort/partition_pair_u32.hpp",
             "e045_cells.py", "e046_windows.py", "e056_binary.py")
    for name in names:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copyfile(ROOT / "notes/E059 - Prerregistro alternancia de bloques.md", out / "preregistration.md")
    shutil.copytree(ROOT / repo / "hwy", out / repo / "hwy")
    shutil.copyfile(ROOT / repo / "LICENSE", out / repo / "LICENSE")
    header = out / repo / HEADER
    upstream_digest = sha256(header)
    add_pivot_preparation(header)
    sources = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}

    folder = out.relative_to(ROOT)
    highway = folder / repo
    exe = folder / "e059_pair_schedule"
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", f"-I{highway}",
               str(folder / SOURCE), str(highway / "hwy/abort.cc"), "-pthread", "-o", str(exe)]
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
        "upstream_header_sha256": upstream_digest,
        "executable_sha256": sha256(ROOT / exe),
        "dynamic_library_sha256": libraries,
        "vendor": {"highway": HIGHWAY_COMMIT},
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
        ms = float(row["ms"])
        if not math.isfinite(ms) or ms <= 0:
            raise RuntimeError(f"Invalid measurement in {path}")
    return rows


def summarize(out, cases, verified):
    lines = ["# E059 — Alternar bloques de particiones hermanas", "",
             "Medianas en ms. La puerta se aplica a las dos semillas de uniforme y prefijos amplios.", "",
             "| Familia | Semilla | Serial | Alternado | Vqsort | Serial − alternado (ms) | Serial / alternado | Vqsort / alternado |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    failures = []
    for (family, seed), rows in cases.items():
        serial, alternate, vq = (median(float(row["ms"]) for row in rows if row["algorithm"] == arm)
                                 for arm in ARMS)
        serial_ratio, vq_ratio = serial / alternate, vq / alternate
        label = f"{family}/{seed}"
        if family in TARGETS:
            if serial_ratio <= 1:
                failures.append(f"{label} alcanzó {serial_ratio:.6f} frente al control serial, sin mejora.")
            if vq_ratio < GOAL:
                failures.append(f"{label} alcanzó {vq_ratio:.6f} frente a vqsort, por debajo de {GOAL}.")
        values = (serial, alternate, vq, serial - alternate, serial_ratio, vq_ratio)
        cells = [family, str(seed), *(f"{value:.6f}" for value in values)]
        lines.append("| " + " | ".join(cells) + " |")

    samples = sum(len(rows) for rows in cases.values())
    checked = samples + len(cases) * len(ARMS)
    verdict = "Puerta del filtro superada." if not failures else "Puerta del filtro fallida."
    counts = (f"{samples} muestras y {checked} salidas exactas con calentamientos. "
              f"{verified} comprobaciones previas.")
    lines.extend(("", verdict, "", *(f"- {failure}" for failure in failures), "", counts))
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
        "timing": "Full sort including pivot preparation, partition setup, fallback and final output. "
                  "Common input copy and exact std::sort verification outside.",
        "vq_dispatch": "Highway VQSortStatic native with paired initial pivot state per round",
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
    summarize(out, cases, verified)


def main():
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        raise SystemExit("E059 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        raise SystemExit("E059 requires taskset -c 2")
    out = ROOT / "results/e059_pair_schedule"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
