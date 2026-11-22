"""Run the preregistered local screen sequentially and preserve raw samples."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "runs/2026-11-22-bitplane-sort"
FLAGS = "-O3 -march=znver3 -mavx2 -DNDEBUG -std=c++20 -Wall -Wextra -Wpedantic"


def checked(command: list[str]) -> str:
    return subprocess.run(command, check=True, capture_output=True, text=True).stdout


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("--cpu", type=int, default=8)
    args = parser.parse_args()
    binary = args.binary.resolve()
    if (RUN / "raw.csv").exists():
        raise SystemExit("raw.csv exists; archive the previous run before measuring again")

    started = datetime.now(timezone.utc).isoformat()
    verification = checked([str(binary), "--verify"])
    (RUN / "verification.txt").write_text(verification, encoding="utf-8")
    cells = [(65536, "uniform"), (128, "uniform"), (65536, "eight")]
    commands = []
    with (RUN / "raw.csv").open("w", encoding="utf-8", newline="\n") as output:
        first = True
        for groups, distribution in cells:
            for seed in (104729, 130363):
                command = [str(binary), str(groups), distribution, str(seed), "7", str(args.cpu)]
                result = checked(command)
                rows = result.splitlines()
                if not rows or len(rows) != 41:
                    raise RuntimeError("unexpected sample count")
                if first:
                    output.write(rows[0] + "\n")
                    first = False
                output.write("\n".join(rows[1:]) + "\n")
                output.flush()
                commands.append(command[1:])
                print(f"Verified all 40 calls: groups={groups}, keys={distribution}, seed={seed}", flush=True)

    references = {}
    for name in ("highway", "x86-simd-sort"):
        vendor = ROOT / "lab/supersort-original/vendor" / name
        references[name] = checked(["git", "-C", str(vendor), "rev-parse", "HEAD"]).strip()
    tracked = [
        Path("prototypes/agents/bitplane-sort/bench.cpp"),
        Path("prototypes/agents/bitplane-sort/run.py"),
        Path("runs/2026-11-22-bitplane-sort/protocol.md"),
    ]
    metadata = {
        "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "compiler": checked(["g++", "--version"]).splitlines()[0],
        "flags": FLAGS,
        "logical_cpu": args.cpu,
        "threads": 1,
        "references": references,
        "source_sha256": {p.as_posix(): hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in tracked},
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "binary_arguments": commands,
        "large_cache_state": "CLFLUSH on input and output lines, followed by MFENCE before timing",
        "small_cache_state": "no explicit flush; buffers resident after generation and verification",
        "timing": "batch call only; per-group stack work and all encoding/materialization included",
        "external_compute_spend": 0,
        "tokens": "not captured",
        "subscription_cost": "not captured",
        "model": "GPT-6 (Codex), exact deployment variant and reasoning settings unavailable",
    }
    (RUN / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
