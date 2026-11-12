"""Measure and archive E065's two-materialization budget in Ubuntu WSL."""

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
from e064_distribution_budget import ARMS as E064_ARMS
from e064_distribution_budget import (
    CASES, CPU, FIELDS, HEADER, MAX_SPAN, N, REPEATS, ROOT, SEEDS, SOURCE, add_frontier,
)


ARMS = (*E064_ARMS, "staged")


def build(out):
    repo = Path("vendor/highway")
    git = ["git", "-C", str(repo)]
    if command_output([*git, "rev-parse", "HEAD"]) != HIGHWAY_COMMIT:
        raise RuntimeError("Unexpected Highway revision")
    if command_output([*git, "status", "--porcelain", "--untracked-files=all"]):
        raise RuntimeError("Modified Highway checkout")
    names = ("e065_staging_budget.py", SOURCE, "e064_distribution_budget.py", "e062_position_bitmap.py",
             "e056_binary.py", "e046_windows.py", "e045_cells.py")
    for name in names:
        shutil.copyfile(ROOT / name, out / name)
    shutil.copyfile(ROOT / "notes/E065 - Prerregistro doble materialización.md", out / "preregistration.md")
    shutil.copytree(ROOT / repo / "hwy", out / repo / "hwy")
    shutil.copyfile(ROOT / repo / "LICENSE", out / repo / "LICENSE")
    header = out / repo / HEADER
    upstream_hash = sha256(header)
    add_frontier(header)
    sources = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}

    folder = out.relative_to(ROOT)
    highway = folder / repo
    exe = folder / "e065_staging_budget"
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", "-DSUPERSORT_STAGING_BUDGET",
               f"-I{highway}", str(folder / SOURCE), str(highway / "hwy/abort.cc"),
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


def read_case(path):
    with path.open(newline="", encoding="ascii") as stream:
        rows = list(csv.DictReader(stream, fieldnames=FIELDS))
    if any(None in row or any(value is None for value in row.values()) for row in rows):
        raise RuntimeError(f"Invalid driver columns in {path}")
    actual = Counter((int(row["round"]), row["algorithm"]) for row in rows)
    expected = Counter((round_, arm) for round_ in range(REPEATS) for arm in ARMS)
    if actual != expected:
        raise RuntimeError(f"Unexpected measurement counts in {path}")

    coverage = {}
    for row in rows:
        ms, frontier = float(row["ms"]), float(row["frontier_ms"])
        arm = row["algorithm"]
        spans, keys = int(row["spans"]), int(row["keys"])
        if not math.isfinite(ms) or ms <= 0 or not math.isfinite(frontier):
            raise RuntimeError(f"Invalid time in {path}: {row}")
        if arm == "live":
            if not 0 < frontier <= ms:
                raise RuntimeError(f"Invalid live frontier time in {path}: {row}")
        elif frontier != 0:
            raise RuntimeError(f"Unexpected frontier time in {path}: {row}")
        if arm == "vq" or (arm == "staged" and (spans, keys) == (0, 0)):
            if (spans, keys) != (0, 0):
                raise RuntimeError(f"Unexpected vqsort coverage in {path}: {row}")
            continue
        if keys != N or not 0 < spans <= keys <= spans * MAX_SPAN:
            raise RuntimeError(f"Invalid frontier coverage in {path}: {row}")
        coverage[int(row["round"]), arm] = spans, keys

    for round_ in range(REPEATS):
        same_round = {coverage[round_, arm] for arm in ("live", "replay", "oracle")}
        staged = coverage.get((round_, "staged"))
        if staged is not None:
            same_round.add(staged)
        if len(same_round) != 1:
            raise RuntimeError(f"Different frontier coverage in {path}, round {round_}")
    return rows


def summarize(out, cases):
    lines = ["# E065 — Coste de materializar el reparto en un auxiliar nuevo", "",
             "Medianas en ms. Staged cobra reserva, dos copias y liberación, además de los mismos finalizadores. "
             "La diferencia con oracle se calcula por pares y recoge también el contexto de caché.", "",
             "| Familia | Semilla | Vqsort | Oracle | Staged | Staged − oracle pareado | Objetivo | Presupuesto | Respaldos |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    context = ["## Cobertura y tiempos de control", "",
               "| Familia | Semilla | Tramos | Claves | Live total | Frontera en live | Replay |",
               "|---|---:|---:|---:|---:|---:|---:|"]
    failures, budgets = [], []
    fallback_total = 0
    for (family, seed), rows in cases.items():
        times = {(int(row["round"]), row["algorithm"]): float(row["ms"]) for row in rows}
        vq, live, replay, oracle, staged = (
            median(times[round_, arm] for round_ in range(REPEATS)) for arm in ARMS
        )
        live_rows = [row for row in rows if row["algorithm"] == "live"]
        frontier = median(float(row["frontier_ms"]) for row in live_rows)
        spans = median(int(row["spans"]) for row in live_rows)
        delta = median(times[round_, "staged"] - times[round_, "oracle"] for round_ in range(REPEATS))
        fallbacks = sum(row["algorithm"] == "staged" and int(row["spans"]) == 0 for row in rows)
        fallback_total += fallbacks
        target = 0.8 * vq
        budget = target - staged
        budgets.append(budget)
        if budget <= 0:
            failures.append(f"{family}/{seed} dejó {budget:.6f} ms para la clasificación y el directorio.")
        if fallbacks:
            failures.append(f"{family}/{seed} activó el respaldo por reserva en {fallbacks} rondas medidas.")
        values = (vq, oracle, staged, delta, target, budget)
        lines.append("| " + " | ".join([family, str(seed), *(f"{value:.6f}" for value in values),
                                       str(fallbacks)]) + " |")
        cells = [family, str(seed), str(spans), str(N), *(f"{value:.6f}" for value in (live, frontier, replay))]
        context.append("| " + " | ".join(cells) + " |")

    samples = sum(len(rows) for rows in cases.values())
    checked_arms = samples + len(cases) * len(ARMS)
    checked_captures = len(cases) * (REPEATS + 1)
    minimum = min(budgets)
    verdict = (f"Quedan al menos {minimum:.6f} ms para la clasificación y el directorio."
               if not failures else "Puerta fallida. Se cierra la secuencia de dos materializaciones separadas.")
    counts = (f"{samples} muestras, {checked_arms} salidas exactas de los brazos con calentamientos "
              f"y {checked_captures} capturas exactas.")
    lines.extend(("", *context, "", verdict, "", *(f"- {failure}" for failure in failures), "", counts))
    write_text(out / "summary.md", "\n".join(lines))
    write_json(out / "gate.json", {"passed": not failures, "failures": failures, "min_budget_ms": minimum,
                                   "fallbacks": fallback_total, "samples": samples,
                                   "checked": checked_arms + checked_captures,
                                   "checked_arms": checked_arms, "checked_captures": checked_captures})
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
        "max_subtree_keys": MAX_SPAN,
        "timing": "E064 controls with staged allocating a fresh buffer, copying the layout through it to the array, "
                  "finishing the captured subtrees and freeing the buffer. On allocation failure staged runs vqsort. "
                  "Capture, common input copy and checks are outside timing.",
        "frontier": "Maximal subtrees captured in explicit Recurse<kSort, true> and finalized by Recurse<kSort, false>.",
    })
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
    summarize(out, cases)


def main():
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        raise SystemExit("E065 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        raise SystemExit("E065 requires taskset -c 2")
    out = ROOT / "results/e065_staging_budget"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
