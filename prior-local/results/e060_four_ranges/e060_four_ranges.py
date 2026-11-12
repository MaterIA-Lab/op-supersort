"""Run and archive the E060 four-range partition filter in Ubuntu WSL."""

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
CASES = (*TARGETS, "center", "equal")
ARMS = ("binary", "four", "vq")
TELEMETRY = ("classified", "copied", "fallbacks")
FIELDS = ("round", "algorithm", "ms", *TELEMETRY)
MAX_DIGITS = 6
MAX_FALLBACKS = sum(4**level for level in range(MAX_DIGITS))
GOAL = 1.25
SOURCE = "e060_four_ranges.cpp"
BRIDGE = "e056_vq_bridge.cpp"


def build(out):
    repo = Path("vendor/highway")
    git = ["git", "-C", str(repo)]
    if command_output([*git, "rev-parse", "HEAD"]) != HIGHWAY_COMMIT:
        raise RuntimeError("Unexpected Highway revision")
    if command_output([*git, "status", "--porcelain", "--untracked-files=all"]):
        raise RuntimeError("Modified Highway checkout")
    names = ("e060_four_ranges.py", SOURCE, BRIDGE, "e045_cells.py", "e046_windows.py", "e056_binary.py",
             "include/supersort/four_split_u32.hpp", "include/supersort/windows_split_u32.hpp",
             "include/supersort/windows_compact_u32.hpp", "include/supersort/windows_u32.hpp")
    for name in names:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copyfile(ROOT / "notes/E060 - Prerregistro cuatro rangos.md", out / "preregistration.md")
    shutil.copytree(ROOT / repo / "hwy", out / repo / "hwy")
    shutil.copyfile(ROOT / repo / "LICENSE", out / repo / "LICENSE")
    sources = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}

    folder = out.relative_to(ROOT)
    highway = folder / repo
    exe = folder / "e060_four_ranges"
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", f"-I{highway}",
               f"-I{folder / 'include'}", str(folder / SOURCE), str(folder / BRIDGE),
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

    telemetry = {}
    for row in rows:
        ms = float(row["ms"])
        arm = row["algorithm"]
        classified, copied, fallbacks = (int(row[field]) for field in TELEMETRY)
        if not math.isfinite(ms) or ms <= 0:
            raise RuntimeError(f"Invalid time in {path}: {row}")
        if not (0 <= copied <= classified and 0 <= fallbacks <= MAX_FALLBACKS):
            raise RuntimeError(f"Invalid telemetry in {path}: {row}")
        if arm == "vq" and (classified, copied, fallbacks) != (0, 0, 0):
            raise RuntimeError(f"Unexpected vqsort telemetry in {path}: {row}")
        if arm == "binary" and (classified % 2 or not 2 * N <= classified <= 2 * MAX_DIGITS * N or copied):
            raise RuntimeError(f"Invalid binary work in {path}: {row}")
        if arm == "four" and not (N <= classified <= MAX_DIGITS * N or (classified == 0 and fallbacks == 1)):
            raise RuntimeError(f"Invalid four-range work in {path}: {row}")
        telemetry[int(row["round"]), arm] = classified, copied, fallbacks

    for round_ in range(REPEATS):
        binary_classified, _, binary_fallbacks = telemetry[round_, "binary"]
        four_classified, _, four_fallbacks = telemetry[round_, "four"]
        if four_classified and (binary_classified != 2 * four_classified or binary_fallbacks != four_fallbacks):
            raise RuntimeError(f"Different split trees in {path}, round {round_}")
    return rows


def summarize(out, cases, verified):
    lines = ["# E060 — Cuatro rangos en una pasada", "",
             "Medianas en ms. La puerta se aplica a las dos semillas de uniforme y prefijos amplios.", "",
             "| Familia | Semilla | Binario | Cuatro | Vqsort | Binario − cuatro (ms) | Binario / cuatro | Vqsort / cuatro |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    work = ["## Trabajo lógico", "",
            "Medianas en número de claves clasificadas y copiadas, y de tramos que activan el respaldo. "
            "El vqsort directo registra cero en los tres contadores. El ancho de los stores no se mide.", "",
            "| Familia | Semilla | Binario clasificadas | Cuatro clasificadas | Cuatro copiadas | Binario respaldos | Cuatro respaldos |",
            "|---|---:|---:|---:|---:|---:|---:|"]
    failures = []
    for (family, seed), rows in cases.items():
        by_arm = {arm: [row for row in rows if row["algorithm"] == arm] for arm in ARMS}
        binary, four, vq = (median(float(row["ms"]) for row in by_arm[arm]) for arm in ARMS)
        binary_ratio, vq_ratio = binary / four, vq / four
        label = f"{family}/{seed}"
        if family in TARGETS:
            if binary_ratio <= 1:
                failures.append(f"{label} alcanzó {binary_ratio:.6f} frente al control binario, sin mejora.")
            if vq_ratio < GOAL:
                failures.append(f"{label} alcanzó {vq_ratio:.6f} frente a vqsort, por debajo de {GOAL}.")
        values = (binary, four, vq, binary - four, binary_ratio, vq_ratio)
        lines.append("| " + " | ".join([family, str(seed), *(f"{value:.6f}" for value in values)]) + " |")
        counts = {(arm, field): median(int(row[field]) for row in by_arm[arm])
                  for arm in ("binary", "four") for field in TELEMETRY}
        values = (counts["binary", "classified"], counts["four", "classified"], counts["four", "copied"],
                  counts["binary", "fallbacks"], counts["four", "fallbacks"])
        work.append("| " + " | ".join([family, str(seed), *(str(value) for value in values)]) + " |")

    samples = sum(len(rows) for rows in cases.values())
    checked = samples + len(cases) * len(ARMS)
    verdict = "Puerta del filtro superada." if not failures else "Puerta del filtro fallida."
    counts = (f"{samples} muestras y {checked} salidas exactas con calentamientos. "
              f"{verified} comprobaciones previas.")
    lines.extend(("", *work, "", verdict, "", *(f"- {failure}" for failure in failures), "", counts))
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
        "timing": "Full sort including classification, scratch allocation and release, central copy and fallback. "
                  "Common input copy and exact std::sort verification outside.",
        "telemetry": "Classified keys per logical pass, keys copied from scratch, and partition fallbacks.",
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
        raise SystemExit("E060 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        raise SystemExit("E060 requires taskset -c 2")
    out = ROOT / "results/e060_four_ranges"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
