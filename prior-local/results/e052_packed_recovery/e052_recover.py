"""Complete the unexecuted E052 cases once with the original WSL executable."""

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import platform
import shutil
import sys

import e052_packed as experiment


ROOT = experiment.ROOT
ORIGINAL = ROOT / "results/e052_packed_filter"
RECOVERY = ROOT / "results/e052_packed_recovery"
ALL_CASES = tuple((n, dist, seed) for n, dists in experiment.MATRIX.items()
                  for dist in dists for seed in experiment.SEEDS)
IMPORTED = ALL_CASES[:5]


def case_command(executable, case):
    n, dist, seed = case
    return [str(executable), str(n), dist, str(seed), str(experiment.REPEATS)]


def case_label(case):
    return "case-{}-{}-{}".format(*case)


def check_origin(metadata, executable):
    experiment.check_hashes(ORIGINAL, metadata["source_files_sha256"])
    if experiment.sha256(ROOT / executable) != metadata["executable_sha256"]:
        raise RuntimeError("Original executable differs from its recorded hash")
    for name, digest in metadata["dynamic_library_sha256"].items():
        if experiment.sha256(Path(name)) != digest:
            raise RuntimeError(f"Dynamic dependency differs from the original run: {name}")


def load_original():
    metadata = json.loads((ORIGINAL / "metadata.json").read_text(encoding="utf-8"))
    executable = Path(metadata["executable"])
    if ROOT / executable != ORIGINAL / "e052_packed" or metadata["affinity"] != [experiment.CPU]:
        raise RuntimeError("Unexpected original executable path or CPU affinity")
    check_origin(metadata, executable)
    with (ORIGINAL / "commands.jsonl").open(encoding="utf-8") as stream:
        commands = [json.loads(line) for line in stream]
    expected = [("build", metadata["flags"]), ("verify", [str(executable), "--verify"]),
                *((case_label(case), case_command(executable, case)) for case in IMPORTED)]
    if ([(item["label"], item["command"]) for item in commands] != expected
            or any(item["returncode"] != 0 for item in commands)):
        raise RuntimeError("Original command log differs from the five successful case invocations")
    marker, _, count = (ORIGINAL / "verify.stdout.txt").read_text(encoding="utf-8").strip().partition(",")
    if marker != "verified" or not count.isascii() or not count.isdecimal() or int(count) <= 0:
        raise RuntimeError("Invalid original verification marker")

    cases = {}
    prefix = []
    for case in IMPORTED:
        n, dist, seed = case
        cases[case] = experiment.read_case(ORIGINAL / f"{case_label(case)}.stdout.txt", n)
        if case != IMPORTED[-1]:
            prefix.extend(dict(row, n=str(n), distribution=dist, seed=str(seed))
                          for row in cases[case][0])
    with (ORIGINAL / "raw.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != experiment.RAW_FIELDS or list(reader) != prefix:
            raise RuntimeError("Original partial CSV differs from the first four case logs")
    return metadata, executable, cases, int(count)


def execute(out, amendment):
    metadata, executable, cases, verified = load_original()
    originals = ("preregistration.md", "verify.stdout.txt", "verify.stderr.txt", "commands.jsonl",
                 "metadata.json", "raw.csv", "failure.txt", "ldd.txt", "lscpu.txt",
                 *(f"{case_label(case)}.{stream}.txt" for case in IMPORTED
                   for stream in ("stdout", "stderr")))
    original_hashes = {}
    for name in originals:
        target = out / f"original-{name}"
        shutil.copyfile(ORIGINAL / name, target)
        original_hashes[name] = experiment.sha256(target)
    for name in ("e052_recover.py", "e052_packed.py", "e045_cells.py", "e046_windows.py"):
        shutil.copyfile(ROOT / name, out / name)
    shutil.copyfile(amendment, out / "recovery-preregistration.md")
    experiment.write_text(out / "lscpu.txt", experiment.command_output(["lscpu"]))
    experiment.write_json(out / "metadata.json", {
        **metadata,
        "utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "python": sys.version,
        "affinity": sorted(os.sched_getaffinity(0)),
        "original_directory": ORIGINAL.relative_to(ROOT).as_posix(),
        "original_artifacts_sha256": original_hashes,
        "recovery_sources_sha256": {path.name: experiment.sha256(path) for path in out.glob("*.py")},
        "imported_cases": IMPORTED,
        "recovery_cases": ALL_CASES[len(IMPORTED):],
    })

    failures = []
    with (out / "raw.csv").open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=experiment.RAW_FIELDS)
        writer.writeheader()
        for case in ALL_CASES:
            n, dist, seed = case
            if case not in cases:
                try:
                    path = experiment.run_logged(out, case_label(case), case_command(executable, case))
                    cases[case] = experiment.read_case(path, n)
                except (OSError, RuntimeError, ValueError) as error:
                    failures.append({"case": case, "error": str(error)})
                    print(f"{case_label(case)}: {error}", flush=True)
                    continue
            writer.writerows(dict(row, n=n, distribution=dist, seed=seed) for row in cases[case][0])
            stream.flush()
    check_origin(metadata, executable)
    experiment.check_hashes(ORIGINAL, original_hashes)
    experiment.write_json(out / "recovery-status.json", {
        "complete": not failures, "completed_cases": len(cases), "failures": failures,
    })
    if failures:
        raise RuntimeError(f"Incomplete E052 recovery: {len(failures)} cases failed")
    experiment.analyze(out, cases, verified)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--amendment", required=True, type=Path)
    args = parser.parse_args()
    if not args.amendment.is_file():
        parser.error("The recovery amendment must exist")
    if platform.system() != "Linux" or "microsoft" not in platform.release().lower():
        parser.error("E052 recovery requires the original Ubuntu WSL environment")
    if os.sched_getaffinity(0) != {experiment.CPU}:
        parser.error("E052 recovery requires taskset -c 2")
    RECOVERY.mkdir(exist_ok=False)
    try:
        execute(RECOVERY, args.amendment)
    except Exception as error:
        experiment.write_text(RECOVERY / "failure.txt", f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
