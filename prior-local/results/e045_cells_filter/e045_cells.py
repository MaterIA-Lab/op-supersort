"""Archive, verify and run the preregistered E045 leaf comparison on Windows."""

import argparse
from collections import Counter
import csv
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parent
HIGHWAY = Path("vendor/highway")
HIGHWAY_COMMIT = "a3f6f68fcc368e5e3025ca25805eabda9d8a456f"
REGISTRATION = ROOT / "notes/E045 - Prerregistro celdas.md"
CPU = 2
N = 10_000_000
SEEDS = (47143, 92671)
REPEATS = 7
PRIMARY = ("uniform", "dense16", "skew", "bimodal", "mixed",
           "prefix_distinct", "few", "late_overflow")
DISTRIBUTIONS = (*PRIMARY, "near_sorted")
ALGORITHMS = ("leaf_vq", "leaf_cells")
DRIVER_FIELDS = ("repeat", "algorithm", "ms", "skipped", "aborted",
                 "completed", "attempt_reads", "residual")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command_output(command):
    return subprocess.check_output(command, cwd=ROOT, text=True).strip()


def archive_sources(out):
    commit = command_output(["git", "-C", str(HIGHWAY), "rev-parse", "HEAD"])
    if commit != HIGHWAY_COMMIT:
        raise RuntimeError(f"Unexpected Highway commit {commit}")
    dirty = command_output(["git", "-C", str(HIGHWAY), "status",
                            "--porcelain", "--untracked-files=all"])
    if dirty:
        raise RuntimeError(f"Highway sources differ from the pinned tree:\n{dirty}")

    for name in ("e045_cells.py", "e045_cells.cpp", "vq_bridge.cpp",
                 "include/supersort/cells_u32.hpp"):
        target = out / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, target)
    shutil.copyfile(REGISTRATION, out / "preregistration.md")
    shutil.copytree(ROOT / HIGHWAY / "hwy", out / HIGHWAY / "hwy")
    shutil.copyfile(ROOT / HIGHWAY / "LICENSE", out / HIGHWAY / "LICENSE")
    return {p.relative_to(out).as_posix(): sha256(p)
            for p in sorted(out.rglob("*")) if p.is_file()}


def pin_windows(cpu):
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
    kernel.SetProcessAffinityMask.restype = wintypes.BOOL
    kernel.GetProcessAffinityMask.argtypes = [
        wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
    kernel.GetProcessAffinityMask.restype = wintypes.BOOL
    process = kernel.GetCurrentProcess()
    if not kernel.SetProcessAffinityMask(process, 1 << cpu):
        raise ctypes.WinError(ctypes.get_last_error())
    mask, system = ctypes.c_size_t(), ctypes.c_size_t()
    if not kernel.GetProcessAffinityMask(process, ctypes.byref(mask), ctypes.byref(system)):
        raise ctypes.WinError(ctypes.get_last_error())
    if mask.value != 1 << cpu:
        raise RuntimeError(f"Unexpected process affinity mask {mask.value:#x}")
    return {"process_mask": hex(mask.value), "system_mask": hex(system.value)}


def run_logged(out, label, command):
    print(label, flush=True)
    start = time.monotonic()
    stdout_path = out / f"{label}.stdout.txt"
    stderr_path = out / f"{label}.stderr.txt"
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, check=False)
    with (out / "commands.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"label": label, "cwd": str(ROOT), "command": command,
                                 "returncode": result.returncode,
                                 "elapsed_s": time.monotonic() - start}) + "\n")
    if result.returncode:
        raise RuntimeError(f"{label} exited with {result.returncode}. See {stderr_path}.")
    return stdout_path


def read_case(path):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream, fieldnames=DRIVER_FIELDS))
    actual = Counter((int(row["repeat"]), row["algorithm"]) for row in rows)
    expected = Counter((rep, alg) for rep in range(REPEATS) for alg in ALGORITHMS)
    if actual != expected:
        raise RuntimeError(f"Wrong count or identity of measurements in {path}")
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise RuntimeError(f"Unexpected CSV columns in {path}")
        ms = float(row["ms"])
        if not math.isfinite(ms) or ms <= 0:
            raise RuntimeError(f"Invalid measured time in {path}")
        if any(int(row[field]) < 0 for field in DRIVER_FIELDS[3:]):
            raise RuntimeError(f"Negative work counter in {path}")
    return rows


def analyze(out, cases):
    ratios = {}
    lines = ["# E045 — Filtro causal de las hojas", "",
             "10M claves. Las medianas usan siete rondas medidas por entrada. "
             "La preparación por byte alto queda fuera del reloj de ambos brazos.", "",
             "| Familia | Semilla | vqsort local, ms | Celdas, ms | vq/celdas | "
             "Omitidos | Abortados | Completados | Claves leídas | Residuo |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for (dist, seed), rows in cases.items():
        timings = {alg: [float(row["ms"]) for row in rows if row["algorithm"] == alg]
                   for alg in ALGORITHMS}
        control, cells = (statistics.median(timings[alg]) for alg in ALGORITHMS)
        ratio = ratios[dist, seed] = control / cells
        counts = {tuple(int(row[field]) for field in DRIVER_FIELDS[3:])
                  for row in rows if row["algorithm"] == "leaf_cells"}
        if len(counts) != 1:
            raise RuntimeError(f"Inconsistent work counters for {dist}/{seed}")
        work = " | ".join(str(count) for count in next(iter(counts)))
        lines.append(f"| {dist} | {seed} | {control:.6f} | {cells:.6f} | "
                     f"{ratio:.6f} | {work} |")
    uniform = all(ratios["uniform", seed] >= 1.10 for seed in SEEDS)
    additional = [dist for dist in PRIMARY[1:]
                  if all(ratios[dist, seed] >= 1.10 for seed in SEEDS)]
    mixed_required = any(dist in additional for dist in ("skew", "bimodal", "mixed"))
    regressions = [(dist, seed) for dist in PRIMARY for seed in SEEDS
                   if ratios[dist, seed] < 0.90]
    passed = uniform and len(additional) >= 2 and mixed_required and not regressions
    samples = sum(map(len, cases.values()))
    checked = samples + len(cases) * len(ALGORITHMS)
    lines += ["", f"**Filtro {'superado' if passed else 'fallido'}.**", "",
              f"- Uniforme ≥1,10 en ambas semillas: {'sí' if uniform else 'no'}.",
              f"- Familias adicionales ≥1,10 en ambas semillas: "
              f"{', '.join(additional) if additional else 'ninguna'}.",
              f"- Al menos una familia entre skew, bimodal y mixed: "
              f"{'sí' if mixed_required else 'no'}.",
              "- Casos principales por debajo de 0,90: "
              + (", ".join(f"{dist}/{seed}" for dist, seed in regressions) or "ninguno") + ".",
              f"- {samples} muestras y {checked} salidas comparadas exactamente con "
              "`std::sort`, incluidos los calentamientos."]
    with (out / "summary.md").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    print("\n".join(lines[-7:]), flush=True)


def execute(out):
    manifest = archive_sources(out)
    archive = out.relative_to(ROOT)
    executable = archive / "e045_cells.exe"
    compiler = shutil.which("g++")
    if compiler is None:
        raise RuntimeError("g++ no está en PATH")
    flags = [compiler, "-O3", "-march=native", "-DNDEBUG", "-std=c++17",
             str(archive / "e045_cells.cpp"), str(archive / "vq_bridge.cpp"),
             str(archive / HIGHWAY / "hwy/abort.cc"), f"-I{archive / HIGHWAY}",
             "-o", str(executable)]
    metadata = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "windows": platform.win32_ver(),
        "processor": platform.processor(),
        "logical_cpu": CPU,
        "python": sys.version,
        "uv": command_output(["uv", "--version"]),
        "compiler": command_output([compiler, "--version"]),
        "compiler_target": command_output([compiler, "-dumpmachine"]),
        "flags": flags,
        "source_files_sha256": manifest,
        "vendor": {"highway": {"commit": HIGHWAY_COMMIT,
                               "dispatch": "VQSORT_ONLY_STATIC + HWY_COMPILE_ONLY_STATIC"}},
        "matrix": {"n": N, "seeds": SEEDS, "primary": PRIMARY, "secondary": ["near_sorted"],
                   "repeats": REPEATS, "warmups": 1, "algorithms": ALGORITHMS},
        "timing": "Prepared prefix groups; full leaf dispatch and auxiliary allocation/deallocation; exact std::sort verification outside timing."
    }
    run_logged(out, "build", flags)
    if any(sha256(out / name) != digest for name, digest in manifest.items()):
        raise RuntimeError("Archived sources changed during compilation")
    metadata["executable_sha256"] = sha256(ROOT / executable)
    metadata["affinity"] = pin_windows(CPU)
    with (out / "metadata.json").open("x", encoding="utf-8") as stream:
        json.dump(metadata, stream, indent=2, ensure_ascii=False)
        stream.write("\n")

    run_logged(out, "verify", [str(executable), "--verify"])
    cases = {}
    with (out / "raw.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=("n", "distribution", "seed", *DRIVER_FIELDS))
        writer.writeheader()
        for dist in DISTRIBUTIONS:
            for seed in SEEDS:
                path = run_logged(out, f"case-{dist}-{seed}",
                                  [str(executable), str(N), dist, str(seed), str(REPEATS)])
                rows = read_case(path)
                cases[dist, seed] = rows
                writer.writerows(dict(row, n=N, distribution=dist, seed=seed) for row in rows)
                stream.flush()
    if sha256(ROOT / executable) != metadata["executable_sha256"]:
        raise RuntimeError("Archived executable changed during measurement")
    analyze(out, cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", default="e045_cells_filter",
                        help="New results directory. Use a unique tag when recovering a failed run.")
    args = parser.parse_args()
    if not args.tag.startswith("e045_") or not args.tag.replace("_", "").isalnum():
        parser.error("Tag must start with e045_ and contain only letters, digits and underscores")
    if platform.system() != "Windows":
        parser.error("The E045 preregistration fixes native Windows")
    out = ROOT / "results" / args.tag
    out.mkdir(exist_ok=False)
    try:
        execute(out)
    except Exception as error:
        with (out / "failure.txt").open("x", encoding="utf-8") as stream:
            stream.write(f"{type(error).__name__}: {error}\n")
        raise


if __name__ == "__main__":
    main()
