"""Run and archive the E055 counted vs. single-read partition filter in WSL."""

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


ROOT = Path(__file__).resolve().parent
N = 10_000_000
CPU = 2
REPEATS = 7
SEEDS = (42701, 91009)
TARGETS = ("uniform", "prefix_distinct", "mixed")
CASES = (*TARGETS, "dense16")
ARMS = ("counted", "virtual", "vq")
FIELDS = ("round", "algorithm", "ms", "largest_bucket")
GOAL = 1.25
MECHANISM_GOAL = 1.05


def archive_sources(out):
    for name in ("e055_virtual.py", "e045_cells.py", "e046_windows.py", "e055_virtual.cpp",
                 "e047_vq_bridge.cpp", "include/supersort/scatter_nt.hpp"):
        dest = out / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    shutil.copyfile(ROOT / "notes/E055 - Prerregistro cubetas virtuales.md", out / "preregistration.md")
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
    exe = folder / "e055_virtual"
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", f"-I{highway}",
               str(folder / "e055_virtual.cpp"), str(folder / "e047_vq_bridge.cpp"),
               str(highway / "hwy/abort.cc"), "-pthread", "-o", str(exe)]
    run_logged(out, "build", command)
    check_hashes(out, sources)
    linkage = command_output(["ldd", str(exe)])
    write_text(out / "ldd.txt", linkage)
    libraries = {}
    for line in linkage.splitlines():
        if "=> not found" in line:
            raise RuntimeError(f"Unresolved dependency: {line.strip()}")
        path = line.split("=>", 1)[-1].strip().split(maxsplit=1)[0]
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


def verified_count(path):
    marker, _, count = path.read_text(encoding="utf-8").strip().partition(",")
    if marker != "verified" or not count.isdecimal() or int(count) <= 0:
        raise RuntimeError(f"Invalid verification marker in {path}")
    return int(count)


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
        ms, largest = float(row["ms"]), int(row["largest_bucket"])
        if not math.isfinite(ms) or ms <= 0 or not 0 <= largest <= N:
            raise RuntimeError(f"Invalid measurement in {path}")
        if row["algorithm"] == "vq" and largest != 0:
            raise RuntimeError(f"Unexpected route for vqsort in {path}")
    return rows


def summarize(out, cases, verified):
    lines = ["# E055 — Reparto por prefijo sin histograma global", "",
             "Medianas en ms y cocientes frente al reparto con tramos virtuales. `dense16` es un control.", "",
             "| Familia | Semilla | Contado | Virtual | Vqsort | Contado / virtual | Vqsort / virtual | Mayor cubeta |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    failures = []
    samples = 0
    for (family, seed), rows in cases.items():
        samples += len(rows)
        times = {arm: median(float(r["ms"]) for r in rows if r["algorithm"] == arm) for arm in ARMS}
        sizes = {int(r["largest_bucket"]) for r in rows if r["algorithm"] != "vq"}
        ratio = times["vq"] / times["virtual"]
        gain = times["counted"] / times["virtual"]
        label = f"{family}/{seed}"
        if 0 in sizes:
            failures.append(f"{label} registró respaldo por reserva durante la tanda.")
        if family in TARGETS and ratio < GOAL:
            failures.append(f"{label} alcanzó {ratio:.6f} frente a vqsort, por debajo de {GOAL}.")
        if family in TARGETS[:2] and gain < MECHANISM_GOAL:
            failures.append(f"{label} alcanzó {gain:.6f} frente al control, por debajo de {MECHANISM_GOAL}.")
        medians = " | ".join(f"{times[arm]:.6f}" for arm in ARMS)
        sizes_text = ", ".join(map(str, sorted(sizes)))
        lines.append(f"| {family} | {seed} | {medians} | {gain:.6f} | {ratio:.6f} | {sizes_text} |")

    checked = samples + len(cases) * len(ARMS)
    verdict = "Puerta del filtro superada." if not failures else "Puerta del filtro fallida."
    lines.extend(("", verdict, ""))
    lines.extend(f"- {failure}" for failure in failures)
    lines.extend(("", f"{samples} muestras y {checked} salidas exactas con calentamientos. "
                  f"{verified} comprobaciones previas con guardas, incluido el fallo forzado de reserva."))
    write_text(out / "summary.md", "\n".join(lines) + "\n")
    write_json(out / "gate.json", {"passed": not failures, "failures": failures,
                                   "samples": samples, "checked": checked, "verified": verified})
    print(lines[-1], flush=True)
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
        "overcommit_memory": Path("/proc/sys/vm/overcommit_memory").read_text().strip(),
        "matrix": {"n": N, "cases": CASES, "seeds": SEEDS, "arms": ARMS, "repeats": REPEATS, "warmups": 1},
        "timing": "Full sort including mappings and release, final output and fallback. "
                  "Common input copy and exact std::sort verification outside.",
        "vq_dispatch": "Highway VQSortStatic native with default pivot state",
    })
    verified = verified_count(run_logged(out, "verify", [str(exe), "--verify"]))
    verified += verified_count(run_logged(out, "verify-reserve",
                                         ["prlimit", "--as=67108864", "--", str(exe), "--verify-reserve"]))
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
        raise SystemExit("E055 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        raise SystemExit("E055 requires taskset -c 2")
    out = ROOT / "results/e055_virtual_filter_recovery"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
