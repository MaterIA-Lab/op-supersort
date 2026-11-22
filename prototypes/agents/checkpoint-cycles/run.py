"""Run the registered checkpoint-cycle screen sequentially, preserving all calls."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "runs/2026-11-22-checkpoint-cycles"
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
        raise SystemExit("raw.csv already exists; archive prior measurements before rerunning")
    started = datetime.now(timezone.utc).isoformat()
    (RUN / "verification.txt").write_text(checked([str(binary), "--verify"]), encoding="utf-8")

    cells = [(1048576, "uniform"), (8192, "uniform"), (1048576, "eight")]
    arguments = []
    with (RUN / "raw.csv").open("w", encoding="utf-8", newline="\n") as output:
        first = True
        for records, distribution in cells:
            for seed in (48071, 65827):
                command = [str(binary), str(records), distribution, str(seed), "5", str(args.cpu)]
                lines = checked(command).splitlines()
                if len(lines) != 37:
                    raise RuntimeError(f"unexpected row count: {len(lines)}")
                if first:
                    output.write(lines[0] + "\n")
                    first = False
                output.write("\n".join(lines[1:]) + "\n")
                output.flush()
                arguments.append(command[1:])
                print(f"Verified all 36 calls: rows={records}, keys={distribution}, seed={seed}", flush=True)

    sources = [
        Path("prototypes/agents/checkpoint-cycles/bench.cpp"),
        Path("prototypes/agents/checkpoint-cycles/permutation.hpp"),
        Path("prototypes/agents/checkpoint-cycles/run.py"),
        Path("runs/2026-11-22-checkpoint-cycles/protocol.md"),
    ]
    references = {}
    for name in ("highway", "x86-simd-sort"):
        path = ROOT / "lab/supersort-original/vendor" / name
        references[name] = {
            "commit": checked(["git", "-C", str(path), "rev-parse", "HEAD"]).strip(),
            "working_tree_clean": not checked(["git", "-C", str(path), "status", "--porcelain"]).strip(),
        }
    pdqsort_path = ROOT / "lab/supersort-original/vendor/pdqsort.h"
    metadata = {
        "started_utc": started,
        "finished_utc": datetime.now(timezone.utc).isoformat(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "compiler": checked(["g++", "--version"]).splitlines()[0],
        "flags": FLAGS,
        "logical_cpu": args.cpu,
        "threads": 1,
        "row_bytes": 128,
        "checkpoint_budget": 64,
        "references": references,
        "pdqsort_header_sha256": hashlib.sha256(pdqsort_path.read_bytes()).hexdigest(),
        "source_sha256": {p.as_posix(): hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in sources},
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "binary_arguments": arguments,
        "timing": "key/index extraction, sort and complete in-place materialization; all copy-back work included",
        "workspace": "caller-owned reusable N uint64 tags and N rows, allocated and touched outside timing",
        "large_cache_state": "CLFLUSH working rows, tags and payload scratch, then MFENCE before each call",
        "small_cache_state": "no explicit flush; harness buffers resident",
        "model": "GPT-6 (Codex); exact deployment variant and reasoning settings unavailable",
        "tokens": "not captured",
        "session_cost": "not captured",
        "local_screen_external_compute_spend": 0,
    }
    (RUN / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
