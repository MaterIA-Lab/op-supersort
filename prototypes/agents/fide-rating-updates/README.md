# FIDE monthly rating update benchmark

Author: agent:gpt-6.2-sol (Codex).

The harness imports the earlier [direct-span benchmark](../key-correction-spans/README.md)
and holds the candidate source fixed. Its references include the original
DeltaSort, full-array bulk extraction-sort-merge in either direction, Rust
stable and unstable sort, interval-limited bulk extraction-sort-merge and a
counting sort on 16-bit rating keys. The counting reference stores compact
indices by dense ID, scatters indices into rating buckets in tie order,
prefetches source rows during gather, then copies the records back.
[Protocol and results](../../../runs/2026-11-23-fide-rating-updates/README.md)

## Reproduce

Use Python 3.10+ and an x86-64 Rust installation supporting `znver3`. The
original measurements used Rust 1.96.0. Download the [June ZIP](https://ratings.fide.com/download/standard_jun24frl.zip),
the [July ZIP](https://ratings.fide.com/download/standard_jul24frl.zip), and
the unmodified [pinned DeltaSort lib.rs](https://github.com/shudv/deltasort/blob/89322c7bfb8d5b28b179650d08249398cbe0a977/src/lib.rs).
Place the ZIPs and the DeltaSort source at the paths below. Compare the source
ZIP hashes in `geometry.json` against the published hashes. Keep the ZIPs and
the row-level fixture under `lab/` when running this project locally.

```powershell
New-Item -ItemType Directory -Force lab/fide-ratings | Out-Null
python -X utf8 prototypes/agents/fide-rating-updates/prepare.py lab/standard_jun24frl.zip lab/standard_jul24frl.zip lab/fide-ratings/fixture.csv lab/fide-ratings/geometry.json
python -X utf8 prototypes/agents/fide-rating-updates/run.py lab/fide-ratings/fixture.csv lab/fide-ratings/geometry.json lab/deltasort/lib.rs lab/fide-ratings lab/fide-ratings --cpu 8
python -X utf8 runs/2026-11-23-fide-rating-updates/analyze.py lab/fide-ratings
```

Omit the directory from the last command to verify and recompute statistics
from the published CSV. Every measured run verifies the complete destination
array. The geometry pass checks ID uniqueness and records hashes and aggregate
counts without exporting original player IDs.
