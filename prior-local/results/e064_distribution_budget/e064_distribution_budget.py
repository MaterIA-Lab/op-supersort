"""Measure and archive E064's coarse-distribution budget in Ubuntu WSL."""

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
from e062_position_bitmap import AFTER_RECURSE, RECURSE_HEADER, RECURSE_SORT, RECURSE_TEMPLATE


ROOT = Path(__file__).resolve().parent
N, CPU, REPEATS = 10_000_000, 2, 7
CASES = ("uniform", "prefix_distinct")
SEEDS = (42701, 91009)
ARMS = ("vq", "live", "replay", "oracle")
FIELDS = ("round", "algorithm", "ms", "frontier_ms", "spans", "keys")
MAX_SPAN = 32768
SOURCE = "e064_distribution_budget.cpp"
HEADER = "hwy/contrib/sort/vqsort-inl.h"
CAPTURE = f"""
  if constexpr (Capture) {{
    if (num <= {MAX_SPAN}) {{
      ::e064::frontier(keys, num, state, remaining_levels, [&] {{
        Recurse<mode, false>(d, st, keys, num, buf, state, remaining_levels, k);
      }});
      return;
    }}
  }}""".encode("ascii")


def add_frontier(header):
    upstream = header.read_bytes()
    if (upstream.count(RECURSE_HEADER) != 1 or upstream.count(AFTER_RECURSE) != 1
            or b"::e064::frontier" in upstream):
        raise RuntimeError("Unexpected Highway anchors for E064 frontier")
    start = upstream.index(RECURSE_HEADER)
    stop = upstream.index(AFTER_RECURSE)
    if start + len(RECURSE_HEADER) >= stop:
        raise RuntimeError("Unexpected Highway Recurse boundaries")
    body = upstream[start:stop]
    if body.count(RECURSE_SORT) != 2:
        raise RuntimeError("Expected two recursive kSort calls in Recurse")
    patched_header = RECURSE_HEADER.replace(
        RECURSE_TEMPLATE, b"template <RecurseMode mode, bool Capture = false, class D, class Traits, typename T>")
    body = patched_header + CAPTURE + body[len(RECURSE_HEADER):]
    body = body.replace(RECURSE_SORT, b"Recurse<RecurseMode::kSort, Capture>")
    header.write_bytes(upstream[:start] + body + upstream[stop:])


def build(out):
    repo = Path("vendor/highway")
    git = ["git", "-C", str(repo)]
    if command_output([*git, "rev-parse", "HEAD"]) != HIGHWAY_COMMIT:
        raise RuntimeError("Unexpected Highway revision")
    if command_output([*git, "status", "--porcelain", "--untracked-files=all"]):
        raise RuntimeError("Modified Highway checkout")
    names = ("e064_distribution_budget.py", SOURCE, "e045_cells.py", "e046_windows.py",
             "e056_binary.py", "e062_position_bitmap.py")
    for name in names:
        shutil.copyfile(ROOT / name, out / name)
    shutil.copyfile(ROOT / "notes/E064 - Prerregistro presupuesto de reparto.md", out / "preregistration.md")
    shutil.copytree(ROOT / repo / "hwy", out / repo / "hwy")
    shutil.copyfile(ROOT / repo / "LICENSE", out / repo / "LICENSE")
    header = out / repo / HEADER
    upstream_hash = sha256(header)
    add_frontier(header)
    sources = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}

    folder = out.relative_to(ROOT)
    highway = folder / repo
    exe = folder / "e064_distribution_budget"
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
        if arm == "vq":
            if (spans, keys) != (0, 0):
                raise RuntimeError(f"Unexpected vqsort coverage in {path}: {row}")
        else:
            if keys != N or not 0 < spans <= keys <= spans * MAX_SPAN:
                raise RuntimeError(f"Invalid frontier coverage in {path}: {row}")
            coverage[int(row["round"]), arm] = spans, keys

    for round_ in range(REPEATS):
        if len({coverage[round_, arm] for arm in ("live", "replay", "oracle")}) != 1:
            raise RuntimeError(f"Different frontier coverage in {path}, round {round_}")
    return rows


def summarize(out, cases):
    lines = ["# E064 — Presupuesto de un reparto grueso antes de vqsort", "",
             "Medianas en ms. Oracle cobra una copia secuencial de la disposición preparada y los finalizadores. "
             "El presupuesto resta ese tiempo al 80% de vqsort completo.", "",
             "| Familia | Semilla | Vqsort | Live total | Frontera en live | Replay | Oracle | Objetivo | Presupuesto |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    context = ["## Cobertura y diferencias por ronda", "",
               "Las diferencias son medianas de pares. La diferencia entre oracle y replay incluye los efectos "
               "de caché de hacer la copia dentro del reloj.", "",
               "| Familia | Semilla | Tramos | Claves | Live total − frontera | Replay − frontera | Oracle − replay |",
               "|---|---:|---:|---:|---:|---:|---:|"]
    failures, budgets = [], []
    for (family, seed), rows in cases.items():
        times = {(int(row["round"]), row["algorithm"]): float(row["ms"]) for row in rows}
        live_rows = [row for row in rows if row["algorithm"] == "live"]
        frontier = {int(row["round"]): float(row["frontier_ms"]) for row in live_rows}
        vq, live, replay, oracle = (median(times[round_, arm] for round_ in range(REPEATS)) for arm in ARMS)
        target = 0.8 * vq
        budget = target - oracle
        budgets.append(budget)
        if budget <= 0:
            failures.append(f"{family}/{seed} dejó {budget:.6f} ms para el reparto real.")
        values = (vq, live, median(frontier.values()), replay, oracle, target, budget)
        lines.append("| " + " | ".join([family, str(seed), *(f"{value:.6f}" for value in values)]) + " |")

        spans = median(int(row["spans"]) for row in live_rows)
        deltas = (
            median(times[round_, "live"] - frontier[round_] for round_ in range(REPEATS)),
            median(times[round_, "replay"] - frontier[round_] for round_ in range(REPEATS)),
            median(times[round_, "oracle"] - times[round_, "replay"] for round_ in range(REPEATS)),
        )
        cells = [family, str(seed), str(spans), str(N), *(f"{value:.6f}" for value in deltas)]
        context.append("| " + " | ".join(cells) + " |")

    samples = sum(len(rows) for rows in cases.values())
    checked_arms = samples + len(cases) * len(ARMS)
    checked_captures = len(cases) * (REPEATS + 1)
    minimum = min(budgets)
    verdict = (f"Quedan al menos {minimum:.6f} ms para detección, reserva y reparto reales."
               if not failures else "Puerta fallida. Se cierra el esquema con esta frontera y materialización.")
    counts = (f"{samples} muestras, {checked_arms} salidas exactas de los brazos con calentamientos "
              f"y {checked_captures} capturas exactas.")
    lines.extend(("", *context, "", verdict, "", *(f"- {failure}" for failure in failures), "", counts))
    write_text(out / "summary.md", "\n".join(lines))
    write_json(out / "gate.json", {"passed": not failures, "failures": failures, "min_budget_ms": minimum,
                                   "samples": samples, "checked": checked_arms + checked_captures,
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
        "timing": "Vq and live sort the complete array. Replay runs captured subtrees. Oracle copies the prepared "
                  "layout inside timing and runs the same subtrees. Capture, common input copy and checks are outside.",
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
        raise SystemExit("E064 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        raise SystemExit("E064 requires taskset -c 2")
    out = ROOT / "results/e064_distribution_budget"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
