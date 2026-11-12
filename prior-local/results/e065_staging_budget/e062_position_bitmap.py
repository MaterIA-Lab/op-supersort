"""Run and archive the E062 position-bitmap subtree filter in Ubuntu WSL."""

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
CASES = ("uniform", "prefix_distinct")
SEEDS = (42701, 91009)
ARMS = ("replay", "bitmap", "vq")
TELEMETRY = ("spans", "keys", "bitmap_spans")
FIELDS = ("round", "algorithm", "ms", *TELEMETRY)
MAX_SPAN = 512
SOURCE = "e062_position_bitmap.cpp"
HEADER = "hwy/contrib/sort/vqsort-inl.h"

RECURSE_TEMPLATE = b"template <RecurseMode mode, class D, class Traits, typename T>"
RECURSE_HEADER = RECURSE_TEMPLATE + b"""
HWY_NOINLINE void Recurse(D d, Traits st, T* HWY_RESTRICT keys,
                          const size_t num, T* HWY_RESTRICT buf,
                          uint64_t* HWY_RESTRICT state,
                          const size_t remaining_levels, const size_t k = 0) {
  HWY_DASSERT(num != 0);"""
AFTER_RECURSE = b"""}

// Returns true if sorting is finished.
template <class D, class Traits, typename T>
HWY_INLINE bool HandleSpecialCases"""
RECURSE_SORT = b"Recurse<RecurseMode::kSort>"
CAPTURE = f"""
  if constexpr (Capture) {{
    if (num <= {MAX_SPAN}) ::e062::capture(keys, num, state, remaining_levels);
  }}""".encode("ascii")


def add_capture(header):
    upstream = header.read_bytes()
    if (upstream.count(RECURSE_HEADER) != 1 or upstream.count(AFTER_RECURSE) != 1
            or b"::e062::capture" in upstream):
        raise RuntimeError("Unexpected Highway anchors for E062 capture")
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
    names = ("e062_position_bitmap.py", SOURCE, "include/supersort/position_bitmap_u32.hpp",
             "e045_cells.py", "e046_windows.py", "e056_binary.py")
    for name in names:
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copyfile(ROOT / "notes/E062 - Prerregistro mapas por posición.md", out / "preregistration.md")
    shutil.copytree(ROOT / repo / "hwy", out / repo / "hwy")
    shutil.copyfile(ROOT / repo / "LICENSE", out / repo / "LICENSE")
    header = out / repo / HEADER
    upstream_hash = sha256(header)
    add_capture(header)
    sources = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}

    folder = out.relative_to(ROOT)
    highway = folder / repo
    exe = folder / "e062_position_bitmap"
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
        ms = float(row["ms"])
        if not math.isfinite(ms) or ms <= 0:
            raise RuntimeError(f"Invalid time in {path}: {row}")
        arm = row["algorithm"]
        spans, keys, bitmap_spans = (int(row[field]) for field in TELEMETRY)
        if arm == "vq":
            if (spans, keys, bitmap_spans) != (0, 0, 0):
                raise RuntimeError(f"Unexpected vqsort telemetry in {path}: {row}")
            continue
        if not 0 < spans <= keys <= min(N, MAX_SPAN * spans):
            raise RuntimeError(f"Invalid subtree coverage in {path}: {row}")
        if not 0 <= bitmap_spans <= spans or (arm == "replay" and bitmap_spans != 0):
            raise RuntimeError(f"Invalid bitmap coverage in {path}: {row}")
        coverage[int(row["round"]), arm] = spans, keys

    for round_ in range(REPEATS):
        if coverage[round_, "replay"] != coverage[round_, "bitmap"]:
            raise RuntimeError(f"Different subtree coverage in {path}, round {round_}")
    return rows


def summarize(out, cases, verified):
    lines = ["# E062 — Ordenar posiciones dentro de subárboles de vqsort", "",
             "Tiempos en ms. Replay y bitmap repiten los mismos tramos capturados. "
             "El ahorro es la mediana de las diferencias por ronda. La meta usa el tiempo completo de vqsort.", "",
             "| Familia | Semilla | Replay | Bitmap | Vqsort | Ahorro pareado | Ahorro requerido | Tramos | Claves | Tramos bitmap |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    failures = []
    for (family, seed), rows in cases.items():
        times = {(int(row["round"]), row["algorithm"]): float(row["ms"]) for row in rows}
        replay, bitmap, vq = (median(times[round_, arm] for round_ in range(REPEATS)) for arm in ARMS)
        saving = median(times[round_, "replay"] - times[round_, "bitmap"] for round_ in range(REPEATS))
        required = 0.2 * vq
        if saving < required:
            failures.append(f"{family}/{seed} ahorró {saving:.6f} ms frente a {required:.6f} ms requeridos.")
        bitmap_rows = [row for row in rows if row["algorithm"] == "bitmap"]
        counts = (median(int(row[field]) for row in bitmap_rows) for field in TELEMETRY)
        values = (replay, bitmap, vq, saving, required)
        cells = [family, str(seed), *(f"{value:.6f}" for value in values), *(str(count) for count in counts)]
        lines.append("| " + " | ".join(cells) + " |")

    samples = sum(len(rows) for rows in cases.values())
    checked_arms = samples + len(cases) * len(ARMS)
    checked_captures = len(cases) * (REPEATS + 1)
    verdict = ("Puerta superada para probar la integración."
               if not failures else "Puerta fallida. Se cierra esta implementación.")
    counts = (f"{samples} muestras, {checked_arms} salidas exactas de los brazos con calentamientos "
              f"y {checked_captures} capturas verificadas. {verified} comprobaciones previas.")
    lines.extend(("", verdict, "", *(f"- {failure}" for failure in failures), "", counts))
    write_text(out / "summary.md", "\n".join(lines))
    write_json(out / "gate.json", {"passed": not failures, "failures": failures,
                                   "samples": samples, "checked": checked_arms + checked_captures,
                                   "checked_arms": checked_arms, "checked_captures": checked_captures,
                                   "verified": verified})
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
        "timing": "Replay and bitmap include all subtree work, scratch, fallback, emission and final copy. "
                  "Vqsort sorts the full array. Capture, common input copy and std::sort checks are outside.",
        "vq_dispatch": "Highway static native. Capture only in explicit Recurse<kSort, true>.",
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
        raise SystemExit("E062 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        raise SystemExit("E062 requires taskset -c 2")
    out = ROOT / "results/e062_position_bitmap"
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
