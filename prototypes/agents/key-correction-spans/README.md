# Direct span moves after key corrections

This prototype applies a batch of replacement keys to an array already ordered
by `(key, id)`. The caller provides the original positions in any order. The
rows are 64-byte aligned, 128 bytes wide and have a unique persistent ID. The
output occupies the same array. A caller must provide distinct in-bounds
positions and preserve the original key order until the call. See the
[registered workload and methods](../../../runs/2026-11-23-key-correction-spans/protocol.md).

## Why the moves preserve every row

Copy the edited rows out, set their new keys and sort their descriptors. For
each new `(key, id)`, search the original keys for the insertion gap. Merging
those gaps with the original edit positions gives a list of unchanged spans.
All rows within one span have the same displacement. A gap before a removed
row is processed before that removal, and multiple insertions at the same
gap preserve their sorted order.

The destination of each unchanged row is strictly increasing with its source
position. When moving a row to the left, any earlier unchanged row that stays
in place or moves right has a destination at or after its own source, and
before the moving row's destination. Its source is therefore safe. A later
row's source lies beyond the left move. Process left moves in ascending order
to preserve the sources of other pending left moves. Then process right moves
in descending order. They are safe by the same monotone order and cannot
overwrite any placed left move because final destinations are disjoint. Each
`copy_within` preserves overlapping sources inside its own span. The last
writes put edited rows into the remaining slots.

For `k` edits in `n` rows, planning uses `O(k log n)` comparisons and `O(k)`
scratch. It writes each unchanged row with nonzero displacement exactly once.
The logical write count is the number of rows covered by those moves, without
counting cache line traffic or the edited rows saved in scratch.

## Reproduce the local experiment

The harness uses Rust 1.96.0 and the upstream MIT-licensed DeltaSort library.
Fetch the library at the pinned revision into `lab/`, where third-party files
stay with their license. The benchmark consumes its unmodified `rust/src/lib.rs`.

```powershell
New-Item -ItemType Directory -Force lab/2026-11-23/reproduction | Out-Null
git clone https://github.com/shudv/deltasort.git lab/2026-11-23/reproduction/deltasort
git -C lab/2026-11-23/reproduction/deltasort checkout --detach 89322c7bfb8d5b28b179650d08249398cbe0a977
$vendor = 'lab/2026-11-23/reproduction/deltasort/rust/src/lib.rs'
$build = 'lab/2026-11-23/reproduction'
$rustFlags = @('--edition=2021', '-C', 'opt-level=3', '-C', 'target-cpu=znver3', '-C', 'codegen-units=1')
rustc @rustFlags --crate-type=rlib --crate-name deltasort $vendor -o "$build/libdeltasort.rlib"
rustc @rustFlags --extern "deltasort=$build/libdeltasort.rlib" `
    prototypes/agents/key-correction-spans/bench.rs -o "$build/bench.exe"
& "$build/bench.exe" --verify
python -X utf8 prototypes/agents/key-correction-spans/run.py development `
    "$build/bench.exe" $vendor --cpu 8 --output "$build/samples"
python -X utf8 runs/2026-11-23-key-correction-spans/analyze.py development `
    "$build/samples/development.csv"
```

Use an available logical CPU on the test system. A checkout that configured
Git to translate line endings should use LF for the upstream library so its
Git blob hash matches the recorded bytes. For the registered holdout matrix,
run the same commands with `holdout` as the stage and `holdout.csv` as input
to the analyzer. Preserve the development executable for this validation.

The supplemental comparison builds `audit.rs` with the same flags and
DeltaSort rlib. It uses the same candidate source and adds Rust's stable
adaptive sorter. Its runner reproduces the recorded compiler and CPU slot.
[Supplemental protocol](../../../runs/2026-11-23-key-correction-spans/reference-audit.md)

```powershell
rustc @rustFlags --extern "deltasort=$build/libdeltasort.rlib" `
    prototypes/agents/key-correction-spans/audit.rs -o "$build/audit.exe"
python -X utf8 prototypes/agents/key-correction-spans/audit.py "$build/audit.exe" $vendor `
    --output "$build/samples"
```
