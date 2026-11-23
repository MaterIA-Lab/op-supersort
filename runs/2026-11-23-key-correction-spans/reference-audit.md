# Comparison with adaptive full sorting

Author: agent:gpt-6.2-sol (Codex). Registered after the first held-out matrix
and before timing this comparison.

The DeltaSort paper chose Rust's stable `slice::sort_by` (DriftSort) for its
full-sort control because it detects existing runs. The first SuperSort test
used `sort_unstable_by_key` for that control. Audit the stronger adaptive
reference with the original direct-span algorithm and both bulk ESM directions.
Include unmodified DeltaSort and the original full-sort control in the same
rounds. The original source and results stay available for verification.
See [Section 5 of Dwivedi's paper](https://drops.dagstuhl.de/storage/00lipics/lipics-vol371-sea2026/html/LIPIcs.SEA.2026.18/LIPIcs.SEA.2026.18.html#S5).

Use the original contract and code for input generation, exact output
verification, cache flushing, CPU pinning and one thread. Compare two new
fixed seeds, `1234567` and `98765431`, at 1,048,576 rows with 1,024 uniform
edits and 2,097,152 rows with 2,048 uniform edits. Collect one warm-up and
seven measured repetitions with shuffled order. Apply edits inside timing.
Use the better median of all five references in each cell and report each
cell. The audit uses a separate executable that includes the original candidate
source unchanged. Compile with the same flags and pinned upstream DeltaSort.
