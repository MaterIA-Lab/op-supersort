"""Run the supplementary DriftSort comparison with the frozen candidate source."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from run import DELTA_BLOB, HOLDOUT, REPEATS, ROOT, RUN, SOURCE, checked, sha256


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("binary", type=Path)
    parser.add_argument("delta_source", type=Path)
    parser.add_argument("--output", type=Path, default=RUN)
    args = parser.parse_args()
    binary = args.binary.resolve()
    args.output.mkdir(parents=True, exist_ok=True)
    raw = args.output / "reference-audit.csv"
    meta_path = args.output / "reference-audit.json"
    if raw.exists() or meta_path.exists():
        raise SystemExit("reference audit already exists in the output directory")
    metadata = json.loads((RUN / "holdout.json").read_text(encoding="utf-8"))
    for path, digest in metadata["source_sha256"].items():
        if sha256(ROOT / path) != digest:
            raise SystemExit(f"frozen source changed: {path}")
    if checked(["git", "hash-object", "--no-filters", str(args.delta_source)]).strip() != DELTA_BLOB:
        raise SystemExit("upstream DeltaSort source hash changed")
    if checked(["rustc", "--version", "--verbose"]).splitlines() != metadata["compiler"]:
        raise SystemExit("compiler differs from the registered build")
    audit_sources = [SOURCE / "audit.rs", SOURCE / "audit.py", RUN / "reference-audit.md"]
    metadata["source_sha256"].update({p.relative_to(ROOT).as_posix(): sha256(p) for p in audit_sources})
    metadata.update(stage="reference-audit", binary_sha256=sha256(binary),
                    started_utc=datetime.now(timezone.utc).isoformat())
    lines = []
    arguments = []
    for size, count, _ in HOLDOUT:
        for seed in (1234567, 98765431):
            argv = [str(size), str(count), str(seed), str(REPEATS), str(metadata["logical_cpu"])]
            result = checked([str(binary), *argv]).splitlines()
            if len(result) != 1 + 6 * (REPEATS + 1) or (lines and lines[0] != result[0]):
                raise RuntimeError("unexpected audit CSV")
            lines.extend(result[1:] if lines else result)
            arguments.append(argv)
            print(f"Verified {len(result) - 1} calls for {size} rows, seed {seed}", flush=True)
    metadata.update(arguments=arguments, finished_utc=datetime.now(timezone.utc).isoformat())
    with raw.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("\n".join(lines) + "\n")
    with meta_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(metadata, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
