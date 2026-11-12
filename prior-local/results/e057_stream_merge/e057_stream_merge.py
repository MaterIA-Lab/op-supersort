"""Run and archive the E057 cache-resident merge filter in Ubuntu WSL."""

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


ROOT = Path(__file__).resolve().parent
N = 10_000_000
CPU = 2
REPEATS = 7
SEEDS = (42701, 91009)
TARGETS = ("uniform", "prefix_distinct")
CASES = (*TARGETS, "mixed", "dense16")
ARMS = ("bulk", "stream", "vq")
FIELDS = ("round", "algorithm", "ms", "route")
GOAL = 1.25


def archive_sources(out):
    names = ("e057_stream_merge.py", "e057_stream_merge.cpp", "e047_vq_bridge.cpp", "e045_cells.py",
             "e046_windows.py", "e056_binary.py", "include/supersort/stream_merge_u32.hpp")
    for name in names:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copyfile(ROOT / "notes/E057 - Prerregistro unión en caché.md", out / "preregistration.md")
    pinned, source, license_name = VENDORS["highway"]
    repo = Path("vendor/highway")
    git = ["git", "-C", str(repo)]
    if command_output([*git, "rev-parse", "HEAD"]) != pinned:
        raise RuntimeError("Unexpected Highway revision")
    if command_output([*git, "status", "--porcelain", "--untracked-files=all"]):
        raise RuntimeError("Modified Highway checkout")
    shutil.copytree(ROOT / repo / source, out / repo / source)
    shutil.copyfile(ROOT / repo / license_name, out / repo / license_name)
    return {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}


def build(out):
    sources = archive_sources(out)
    folder = out.relative_to(ROOT)
    highway = folder / "vendor/highway"
    exe = folder / "e057_stream_merge"
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", f"-I{highway}",
               str(folder / "e057_stream_merge.cpp"), str(folder / "e047_vq_bridge.cpp"),
               str(highway / "hwy/abort.cc"), "-pthread", "-o", str(exe)]
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
        "executable_sha256": sha256(ROOT / exe),
        "dynamic_library_sha256": libraries,
        "vendor": {"highway": VENDORS["highway"][0]},
    }


def read_case(path):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, fieldnames=FIELDS))
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise RuntimeError(f"Invalid driver columns in {path}")
    actual = Counter((int(row["round"]), row["algorithm"]) for row in rows)
    expected = Counter((round_, arm) for round_ in range(REPEATS) for arm in ARMS)
    if actual != expected:
        raise RuntimeError(f"Unexpected measurement counts in {path}")
    for row in rows:
        ms = float(row["ms"])
        route = row["route"]
        if not math.isfinite(ms) or ms <= 0 or route not in ("merge", "vq"):
            raise RuntimeError(f"Invalid measurement in {path}")
        if row["algorithm"] == "vq" and route != "vq":
            raise RuntimeError(f"Unexpected route for direct vqsort in {path}")
    return rows


def summarize(out, cases, verified):
    lines = ["# E057 — Unión encadenada con bloques en caché", "",
             "Medianas en ms. La puerta se aplica a las dos semillas de uniforme y prefijos amplios.", "",
             "| Familia | Semilla | Bulk | Stream | Vqsort | Bulk / stream | Vqsort / stream | Vqsort / bulk | Ruta bulk | Ruta stream |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---|---|"]
    failures = []
    for (family, seed), rows in cases.items():
        by_arm = {arm: [row for row in rows if row["algorithm"] == arm] for arm in ARMS}
        times = {arm: median(float(row["ms"]) for row in group) for arm, group in by_arm.items()}
        routes = {arm: {row["route"] for row in group} for arm, group in by_arm.items()}
        bulk_ratio = times["bulk"] / times["stream"]
        vq_ratio = times["vq"] / times["stream"]
        label = f"{family}/{seed}"
        if family in TARGETS:
            if routes["bulk"] != {"merge"} or routes["stream"] != {"merge"}:
                failures.append(f"{label} registró respaldo en al menos un brazo de unión.")
            if bulk_ratio <= 1:
                failures.append(f"{label} alcanzó {bulk_ratio:.6f} frente a bulk, sin mejora.")
            if vq_ratio < GOAL:
                failures.append(f"{label} alcanzó {vq_ratio:.6f} frente a vqsort, por debajo de {GOAL}.")
        cells = [family, str(seed), *(f"{times[arm]:.6f}" for arm in ARMS),
                 f"{bulk_ratio:.6f}", f"{vq_ratio:.6f}", f"{times['vq'] / times['bulk']:.6f}",
                 ", ".join(sorted(routes["bulk"])), ", ".join(sorted(routes["stream"]))]
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
        "timing": "Full sort including reservations, release, final output and fallback. "
                  "Common input copy and exact std::sort verification outside.",
        "vq_dispatch": "Highway VQSortStatic native with paired initial pivot state per round",
    })
    verified = verified_count(run_logged(out, "verify", [str(exe), "--verify"]))
    cases = {}
    with (out / "raw.csv").open("x", newline="", encoding="utf-8") as stream:
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
        raise SystemExit("E057 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        raise SystemExit("E057 requires taskset -c 2")
    out = ROOT / "results/e057_stream_merge"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
