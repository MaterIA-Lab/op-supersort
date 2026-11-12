"""Run a preregistered finalizer on captured Highway subtrees in Ubuntu WSL."""

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import math
import os
from pathlib import Path
import platform
import re
import shutil
from statistics import median
import sys

from e045_cells import HIGHWAY_COMMIT, command_output, run_logged, sha256
from e046_windows import check_hashes, write_json, write_text
from e056_binary import verified_count
from e062_position_bitmap import AFTER_RECURSE, RECURSE_HEADER, RECURSE_SORT, RECURSE_TEMPLATE


ROOT = Path(__file__).resolve().parent
N, CPU, REPEATS = 10_000_000, 2, 7
CASES = ("uniform", "prefix_distinct")
SEEDS = (42701, 91009)
ARMS = ("replay", "candidate", "vq")
TELEMETRY = ("spans", "keys", "accepted_spans", "accepted_keys")
FIELDS = ("round", "algorithm", "ms", *TELEMETRY)
SOURCE = "e069_frontier_filter.cpp"
HEADER = "hwy/contrib/sort/vqsort-inl.h"
CAPTURE = b"""
  if constexpr (Capture) {
    if (num <= FRONTIER_CUTOFF) ::frontier_filter::capture(keys, num, state, remaining_levels);
  }"""


def add_capture(header):
    upstream = header.read_bytes()
    if (upstream.count(RECURSE_HEADER) != 1 or upstream.count(AFTER_RECURSE) != 1
            or b"::frontier_filter::capture" in upstream):
        raise RuntimeError("Unexpected Highway anchors for frontier capture")
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


def build(out, options):
    repo = Path("vendor/highway")
    git = ["git", "-C", str(repo)]
    if command_output([*git, "rev-parse", "HEAD"]) != HIGHWAY_COMMIT:
        raise RuntimeError("Unexpected Highway revision")
    if command_output([*git, "status", "--porcelain", "--untracked-files=all"]):
        raise RuntimeError("Modified Highway checkout")

    names = ("frontier_filter.py", SOURCE, "e045_cells.py", "e046_windows.py",
             "e056_binary.py", "e062_position_bitmap.py", options.kernel, *options.extra_source)
    for name in dict.fromkeys(names):
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copyfile(ROOT / options.registration, out / "preregistration.md")
    shutil.copytree(ROOT / repo / "hwy", out / repo / "hwy")
    shutil.copyfile(ROOT / repo / "LICENSE", out / repo / "LICENSE")
    header = out / repo / HEADER
    upstream_hash = sha256(header)
    add_capture(header)
    sources = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}

    folder = out.relative_to(ROOT)
    highway = folder / repo
    exe = folder / "frontier_filter"
    command = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", f"-I{highway}",
               f"-I{folder}", f"-I{folder / 'include'}", f"-DFRONTIER_CUTOFF={options.cutoff}",
               f'-DFRONTIER_KERNEL="{options.kernel}"', str(folder / SOURCE),
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
        "upstream_header_sha256": upstream_hash,
        "executable_sha256": sha256(ROOT / exe),
        "dynamic_library_sha256": libraries,
        "vendor": {"highway": HIGHWAY_COMMIT},
    }


def read_case(path, cutoff):
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
        spans, keys, accepted_spans, accepted_keys = (int(row[field]) for field in TELEMETRY)
        if arm == "vq":
            if (spans, keys, accepted_spans, accepted_keys) != (0, 0, 0, 0):
                raise RuntimeError(f"Unexpected vqsort telemetry in {path}: {row}")
            continue
        if keys != N or not 0 < spans <= keys <= cutoff * spans:
            raise RuntimeError(f"Invalid subtree coverage in {path}: {row}")
        if not 0 <= accepted_spans <= spans or not accepted_spans <= accepted_keys <= cutoff * accepted_spans:
            raise RuntimeError(f"Invalid accepted coverage in {path}: {row}")
        fallback_spans, fallback_keys = spans - accepted_spans, keys - accepted_keys
        if not fallback_spans <= fallback_keys <= cutoff * fallback_spans:
            raise RuntimeError(f"Invalid fallback coverage in {path}: {row}")
        if arm == "replay" and (accepted_spans or accepted_keys):
            raise RuntimeError(f"Unexpected replay telemetry in {path}: {row}")
        coverage[int(row["round"]), arm] = spans, keys

    for round_ in range(REPEATS):
        if coverage[round_, "replay"] != coverage[round_, "candidate"]:
            raise RuntimeError(f"Different subtree coverage in {path}, round {round_}")
    return rows


def summarize(out, cases, verified, options):
    lines = [f"# {options.tag.upper().split('_', 1)[0]} — Finalizador en la frontera de vqsort", "",
             f"Núcleo `{options.kernel}` y frontera de hasta {options.cutoff} claves por tramo.", "",
             "Tiempos en ms. Replay y candidato reciben los mismos tramos capturados. "
             "El ahorro es la mediana de las diferencias por ronda y la meta usa el tiempo de vqsort completo.", "",
             "| Familia | Semilla | Replay | Candidato | Vqsort | Ahorro pareado | Ahorro requerido | Tramos | Claves | Tramos aceptados | Claves aceptadas |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    failures = []
    for (family, seed), rows in cases.items():
        times = {(int(row["round"]), row["algorithm"]): float(row["ms"]) for row in rows}
        replay, candidate, vq = (median(times[round_, arm] for round_ in range(REPEATS)) for arm in ARMS)
        saving = median(times[round_, "replay"] - times[round_, "candidate"] for round_ in range(REPEATS))
        required = 0.2 * vq
        if saving < required:
            failures.append(f"{family}/{seed} registró un ahorro de {saving:.6f} ms frente a los {required:.6f} ms requeridos.")
        candidate_rows = [row for row in rows if row["algorithm"] == "candidate"]
        counts = (median(int(row[field]) for row in candidate_rows) for field in TELEMETRY)
        values = (replay, candidate, vq, saving, required)
        cells = [family, str(seed), *(f"{value:.6f}" for value in values), *(str(count) for count in counts)]
        lines.append("| " + " | ".join(cells) + " |")

    samples = sum(len(rows) for rows in cases.values())
    checked_arms = samples + len(cases) * len(ARMS)
    checked_captures = len(cases) * (REPEATS + 1)
    verdict = "Puerta superada para probar la integración." if not failures else "Puerta fallida."
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


def execute(out, options):
    exe, evidence = build(out, options)
    write_text(out / "lscpu.txt", command_output(["lscpu"]))
    write_json(out / "metadata.json", {
        **evidence,
        "utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "affinity": sorted(os.sched_getaffinity(0)),
        "page_size": os.sysconf("SC_PAGE_SIZE"),
        "matrix": {"n": N, "cases": CASES, "seeds": SEEDS, "arms": ARMS, "repeats": REPEATS, "warmups": 1},
        "kernel": options.kernel,
        "max_subtree_keys": options.cutoff,
        "timing": "Replay and candidate include all subtree work, scratch, fallback and final writes. "
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
                rows = read_case(path, options.cutoff)
                cases[family, seed] = rows
                writer.writerows(dict(row, n=N, family=family, seed=seed) for row in rows)
                stream.flush()

    check_hashes(out, evidence["source_files_sha256"])
    if sha256(ROOT / exe) != evidence["executable_sha256"]:
        raise RuntimeError("Executable changed during measurement")
    for path, digest in evidence["dynamic_library_sha256"].items():
        if sha256(Path(path)) != digest:
            raise RuntimeError(f"Dynamic dependency changed during measurement: {path}")
    summarize(out, cases, verified, options)


def repo_file(value):
    path = (ROOT / value).resolve()
    if not path.is_relative_to(ROOT) or not path.is_file():
        raise argparse.ArgumentTypeError(f"Expected an existing repository file, got {value!r}")
    return path.relative_to(ROOT).as_posix()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--kernel", type=repo_file, required=True)
    parser.add_argument("--cutoff", type=int, required=True)
    parser.add_argument("--registration", type=repo_file, required=True)
    parser.add_argument("--extra-source", type=repo_file, action="append", default=[])
    options = parser.parse_args()
    if not re.fullmatch(r"e\d{3}_[a-z0-9_]+", options.tag):
        parser.error("--tag must be an experiment name such as e069_radix24")
    if not 1 <= options.cutoff < N:
        parser.error("--cutoff must be positive and below the full input size")
    if not re.fullmatch(r"[\w./-]+", options.kernel, re.ASCII):
        parser.error("--kernel must use a portable include path")
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        raise SystemExit("The frontier filter requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        raise SystemExit("The frontier filter requires taskset -c 2")
    out = ROOT / "results" / options.tag
    out.mkdir(exist_ok=False)
    try:
        execute(out, options)
    except Exception as error:
        write_text(out / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
