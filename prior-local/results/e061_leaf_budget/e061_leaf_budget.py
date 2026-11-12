"""Measure the budget of Highway's terminal sorting networks in WSL."""

import csv
from datetime import datetime, timezone
import gzip
import os
from pathlib import Path
import platform
import random
import shutil
from statistics import mean, median
import sys

from e045_cells import HIGHWAY_COMMIT, command_output, run_logged, sha256
from e046_windows import check_hashes, write_json, write_text


ROOT = Path(__file__).resolve().parent
N, CPU, REPEATS = 10_000_000, 2, 7
CASES = ("uniform", "prefix_distinct")
SEEDS = (42701, 91009)
ARMS = ("clean", "trace")
BINS = (16, 32, 64, 128)
SOURCE = "e061_leaf_budget.cpp"
HOOK = b"""  if (HWY_UNLIKELY(num <= Constants::BaseCaseNumLanes(N))) {
    BaseCase(d, st, keys, num, buf);
    return;
  }"""
REPLACEMENT = b"""  if (HWY_UNLIKELY(num <= Constants::BaseCaseNumLanes(N))) {
#ifdef SUPERSORT_TRACE_LEAVES
    if constexpr (mode == RecurseMode::kSort && std::is_same_v<T, uint32_t>) {
      ::e061::trace_leaf(keys, num, [&] { BaseCase(d, st, keys, num, buf); });
    } else
#endif
    {
      BaseCase(d, st, keys, num, buf);
    }
    return;
  }"""


def build(out):
    repo = Path("vendor/highway")
    git = ["git", "-C", str(repo)]
    if command_output([*git, "rev-parse", "HEAD"]) != HIGHWAY_COMMIT:
        raise RuntimeError("Unexpected Highway revision")
    if command_output([*git, "status", "--porcelain", "--untracked-files=all"]):
        raise RuntimeError("Modified Highway checkout")
    for name in (SOURCE, "e061_leaf_budget.py", "e045_cells.py", "e046_windows.py"):
        shutil.copyfile(ROOT / name, out / name)
    shutil.copyfile(ROOT / "notes/E061 - Prerregistro presupuesto de hojas.md", out / "preregistration.md")
    shutil.copytree(ROOT / repo / "hwy", out / repo / "hwy")
    shutil.copyfile(ROOT / repo / "LICENSE", out / repo / "LICENSE")
    header = out / repo / "hwy/contrib/sort/vqsort-inl.h"
    upstream_hash = sha256(header)
    content = header.read_bytes()
    if content.count(HOOK) != 1:
        raise RuntimeError("Leaf hook is ambiguous")
    header.write_bytes(content.replace(HOOK, REPLACEMENT))
    sources = {p.relative_to(out).as_posix(): sha256(p) for p in sorted(out.rglob("*")) if p.is_file()}
    folder = out.relative_to(ROOT)
    highway = folder / repo
    flags = ["g++", "-O3", "-march=native", "-DNDEBUG", "-std=c++17", f"-I{highway}",
             str(folder / SOURCE), str(highway / "hwy/abort.cc"), "-pthread"]
    binaries, commands, libraries = {}, {}, {}
    for arm in ARMS:
        exe = folder / f"e061_{arm}"
        binaries[arm] = str(exe)
        define = ["-DSUPERSORT_TRACE_LEAVES"] if arm == "trace" else []
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
        "upstream_header_sha256": upstream_hash,
        "executable_sha256": {arm: sha256(ROOT / exe) for arm, exe in binaries.items()},
        "dynamic_library_sha256": libraries,
        "vendor": {"highway": HIGHWAY_COMMIT},
    }


def read_run(path, arm):
    total, layout, last_end, keys = None, None, 0, 0
    counts = dict.fromkeys(BINS, 0)
    timed = {upper: [] for upper in BINS}
    clocks = []
    with path.open(newline="", encoding="ascii") as stream:
        for tag, *fields in csv.reader(stream):
            values = tuple(map(int, fields))
            if tag == "total" and len(values) == 1 and total is None:
                total = values[0]
            elif tag == "layout" and len(values) == 3 and layout is None:
                layout = values
            elif arm == "trace" and tag == "clock" and len(values) == 1:
                clocks.extend(values)
            elif arm == "trace" and tag == "leaf" and len(values) == 3:
                offset, size, ns = values
                if offset < last_end or offset + size > N or not 1 <= size <= BINS[-1] or ns < -1:
                    raise RuntimeError(f"Invalid leaf {values} in {path}")
                last_end = offset + size
                keys += size
                upper = next(upper for upper in BINS if size <= upper)
                counts[upper] += 1
                if ns >= 0:
                    timed[upper].append(ns)
            else:
                raise RuntimeError(f"Invalid record {tag} in {path}")
    if total is None or total <= 0 or layout != (8, 128, 0):
        raise RuntimeError(f"Unexpected total or AVX2 layout in {path}: {total}, {layout}")
    metrics = {"total_ns": total}
    if arm == "clean":
        return metrics

    num_timed = sum(map(len, timed.values()))
    num_leaves = sum(counts.values())
    if (len(clocks) != 2048 or min(clocks) < 0 or not keys or num_leaves / 20 > num_timed
            or num_timed > num_leaves / 12 or sum(sum(values) for values in timed.values()) > total):
        raise RuntimeError(f"Incomplete or invalid trace in {path}")
    clock = median(clocks)
    metrics.update(clock_ns=clock, covered_keys=keys)
    for upper, values in timed.items():
        count = counts[upper]
        raw = mean(values) if values else 0
        metrics[f"count_{upper}"] = count
        metrics[f"sampled_{upper}"] = len(values)
        metrics[f"raw_ns_{upper}"] = raw * count
        metrics[f"corrected_ns_{upper}"] = max(0, raw - clock) * count
    metrics["gross_ns"] = sum(metrics[f"raw_ns_{upper}"] for upper in BINS)
    metrics["corrected_ns"] = sum(metrics[f"corrected_ns_{upper}"] for upper in BINS)
    metrics["ideal_ns"] = metrics["corrected_ns_128"] * 7 / 8
    return metrics


def summarize(out, samples):
    lines = ["# E061 — Presupuesto de hojas de vqsort", "",
             "Medianas por entrada. Los tiempos están en ms y el coste del reloj en ns. "
             "El presupuesto optimista de ocho aplica 7/8 al coste corregido de 65–128.", "",
             "| Familia | Semilla | Vqsort | Traza | Hojas bruto | Hojas corregido | 65–128 corregido | Ideal ×8 | Requerido | Reloj (ns) | Claves en hojas |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    breakdown = ["## Coste por franja", "",
                 "| Familia | Semilla | Tamaños | Hojas | Cronometradas | Bruto (ms) | Corregido (ms) | Rondas con hojas sin observación |",
                 "|---|---:|---|---:|---:|---:|---:|---:|"]
    failed, uncertain = [], []
    for family in CASES:
        for seed in SEEDS:
            rows = [row for row in samples if (row["family"], row["seed"]) == (family, seed)]
            base = [row["total_ns"] for row in rows if row["arm"] == "clean"]
            trace = [row for row in rows if row["arm"] == "trace"]
            if len(base) != REPEATS or len(trace) != REPEATS:
                raise RuntimeError("Wrong number of measured rounds")
            clean = median(base)
            p = {field: median(row[field] for row in trace) for field in trace[0]
                 if field not in ("family", "seed", "round", "arm")}
            target = clean / 5
            values = (clean, p["total_ns"], p["gross_ns"], p["corrected_ns"],
                      p["corrected_ns_128"], p["ideal_ns"], target)
            cells = [family, str(seed), *(f"{ns / 1e6:.3f}" for ns in values),
                     f"{p['clock_ns']:g}", str(p["covered_keys"])]
            lines.append("| " + " | ".join(cells) + " |")
            margin = p["ideal_ns"] - target
            label = f"{family}/{seed}"
            if abs(margin) < 0.5e6 or (p["total_ns"] > 1.1 * clean and abs(margin) < 1.5e6):
                uncertain.append(label)
            elif margin < 0:
                failed.append(label)

            lower = 1
            for upper in BINS:
                omitted = sum(row[f"count_{upper}"] > 0 and row[f"sampled_{upper}"] == 0 for row in trace)
                cells = [family, str(seed), f"{lower}–{upper}", str(p[f"count_{upper}"]),
                         str(p[f"sampled_{upper}"]), f"{p[f'raw_ns_{upper}'] / 1e6:.3f}",
                         f"{p[f'corrected_ns_{upper}'] / 1e6:.3f}", str(omitted)]
                breakdown.append("| " + " | ".join(cells) + " |")
                lower = upper + 1

    decision = "descartar" if failed else "recalibrar" if uncertain else "contrastar lote"
    measured, checked = len(samples), 2 * len(samples)
    lines.extend(("", *breakdown, "", f"**Decisión: {decision}.**", "",
                  "Por debajo en el modelo de ocho: " + (", ".join(failed) or "ninguna") + ".",
                  "Margen incierto: " + (", ".join(uncertain) or "ninguna") + ".", "",
                  f"{measured} tiempos completos y {checked} salidas exactas con calentamientos."))
    write_text(out / "summary.md", "\n".join(lines))
    write_json(out / "gate.json", {"decision": decision, "failed": failed, "uncertain": uncertain,
                                   "samples": measured, "checked": checked})
    print(f"{measured} tiempos y {checked} salidas exactas, decisión: {decision}", flush=True)


def main():
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        raise SystemExit("E061 requires Ubuntu WSL")
    if os.sched_getaffinity(0) != {CPU}:
        raise SystemExit("E061 requires taskset -c 2")
    out = ROOT / "results/e061_leaf_budget"
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
            "seeds": SEEDS, "repeats": REPEATS, "warmups_per_process": 1, "arms": ARMS,
            "order": "Separate processes, shuffled arms per round, paired pivot states, 64-byte data alignment",
            "raw_format": "total,ns | layout,lanes,max_leaf,address_mod64 | clock,ns | leaf,offset,size,ns (-1 unsampled)",
        })
        samples = []
        for family in CASES:
            for seed in SEEDS:
                order = random.Random(seed ^ 0x09BCAC24CE2FA4A1)
                for round_ in range(REPEATS):
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
