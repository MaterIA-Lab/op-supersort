"""Complete the missing E045 cases once with the original native executable."""

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import platform
import shutil
import statistics

import e045_cells as experiment


ROOT = experiment.ROOT
ORIGINAL = ROOT / "results/e045_cells_filter"
RECOVERY = ROOT / "results/e045_cells_recovery"
ALL_CASES = tuple((dist, seed) for dist in experiment.DISTRIBUTIONS for seed in experiment.SEEDS)
ORIGINAL_CASES = ALL_CASES[:2]
RAW_FIELDS = ("n", "distribution", "seed", *experiment.DRIVER_FIELDS)


def write_json(path, data):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(data, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def load_original():
    metadata = json.loads((ORIGINAL / "metadata.json").read_text(encoding="utf-8"))
    executable = ORIGINAL / "e045_cells.exe"
    if experiment.sha256(executable) != metadata["executable_sha256"]:
        raise RuntimeError("Original executable differs from its recorded hash")

    cases = {}
    expected_raw = []
    for dist, seed in ORIGINAL_CASES:
        rows = experiment.read_case(ORIGINAL / f"case-{dist}-{seed}.stdout.txt")
        cases[dist, seed] = rows
        expected_raw.extend(dict(row, n=str(experiment.N), distribution=dist, seed=str(seed))
                            for row in rows)
    with (ORIGINAL / "raw.csv").open(newline="", encoding="utf-8") as stream:
        raw = csv.DictReader(stream)
        if tuple(raw.fieldnames) != RAW_FIELDS or list(raw) != expected_raw:
            raise RuntimeError("Original partial CSV differs from the two completed case logs")
    return metadata, executable, cases


def partial_report(out, cases, failures):
    lines = ["# E045 — Recuperación parcial", "",
             "La matriz quedó incompleta. El filtro prerregistrado requiere todas las entradas.",
             "", "| Familia | Semilla | vqsort local, ms | Celdas, ms | vq/celdas |",
             "|---|---:|---:|---:|---:|"]
    for dist, seed in ALL_CASES:
        rows = cases.get((dist, seed))
        if rows is None:
            lines.append(f"| {dist} | {seed} | — | — | — |")
            continue
        control, cells = (statistics.median(float(row["ms"]) for row in rows if row["algorithm"] == alg)
                          for alg in experiment.ALGORITHMS)
        lines.append(f"| {dist} | {seed} | {control:.6f} | {cells:.6f} | {control / cells:.6f} |")
    samples = sum(map(len, cases.values()))
    checked = samples + len(cases) * len(experiment.ALGORITHMS)
    lines += ["", f"{len(cases)} de {len(ALL_CASES)} entradas completas. "
              f"{samples} muestras y {checked} salidas exactas con calentamientos "
              "en las entradas completas.", ""]
    lines.extend(f"- {item['distribution']}/{item['seed']} falló. {item['error']}" for item in failures)
    with (out / "analysis-partial.md").open("x", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")
    print(lines[-len(failures)-2], flush=True)


def execute(out, amendment):
    metadata, executable, cases = load_original()
    for name in ("preregistration.md", "verify.stdout.txt", "commands.jsonl",
                 "metadata.json", "raw.csv", "failure.txt"):
        shutil.copyfile(ORIGINAL / name, out / f"original-{name}")
    for dist, seed in ORIGINAL_CASES:
        name = f"case-{dist}-{seed}.stdout.txt"
        shutil.copyfile(ORIGINAL / name, out / name)
    shutil.copyfile(Path(__file__), out / "e045_recover.py")
    shutil.copyfile(Path(experiment.__file__), out / "e045_cells.py")
    shutil.copyfile(amendment, out / "recovery-preregistration.md")

    affinity = experiment.pin_windows(experiment.CPU)
    write_json(out / "metadata.json", {
        **metadata,
        "utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "affinity": affinity,
        "original_directory": str(ORIGINAL.relative_to(ROOT)),
        "original_executable": str(executable.relative_to(ROOT)),
        "original_raw_sha256": experiment.sha256(out / "original-raw.csv"),
        "original_cases": ORIGINAL_CASES,
        "recovery_cases": ALL_CASES[len(ORIGINAL_CASES):],
    })

    failures = []
    with (out / "raw.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=RAW_FIELDS)
        writer.writeheader()
        for dist, seed in ALL_CASES:
            if (dist, seed) not in cases:
                try:
                    path = experiment.run_logged(
                        out, f"case-{dist}-{seed}",
                        [str(executable), str(experiment.N), dist, str(seed), str(experiment.REPEATS)])
                    cases[dist, seed] = experiment.read_case(path)
                except (OSError, RuntimeError, ValueError) as error:
                    failures.append({"distribution": dist, "seed": seed, "error": str(error)})
                    print(failures[-1], flush=True)
                    continue
            writer.writerows(dict(row, n=experiment.N, distribution=dist, seed=seed)
                             for row in cases[dist, seed])
            stream.flush()
    if experiment.sha256(executable) != metadata["executable_sha256"]:
        raise RuntimeError("Original executable changed during recovery")
    write_json(out / "recovery-status.json", {
        "complete": not failures, "completed_cases": len(cases), "failed_cases": failures,
    })
    if failures:
        partial_report(out, cases, failures)
    else:
        experiment.analyze(out, cases)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amendment", type=Path, required=True)
    args = parser.parse_args()
    if not args.amendment.is_file():
        parser.error("The recovery amendment must exist")
    if platform.system() != "Windows":
        parser.error("Recovery requires the original native Windows environment")
    RECOVERY.mkdir(exist_ok=False)
    try:
        execute(RECOVERY, args.amendment)
    except Exception as error:
        with (RECOVERY / "failure.txt").open("x", encoding="utf-8") as stream:
            stream.write(f"{type(error).__name__}: {error}\n")
        raise


if __name__ == "__main__":
    main()
