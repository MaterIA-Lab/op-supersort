# Sparse saved-row cycle cuts

Research prototype for stable in-place sorting of 128-byte rows. It sorts compact
key/index tags, saves at most 64 original rows at regularly spaced positions,
and interleaves permutation paths closed by those saved rows. The private tag
array supplies a visited bit. Untouched cycles use ordinary cycle rotation.

The mechanism aims to overlap independent memory requests inside a long cycle
without discovering that cycle's structure first, and to avoid a second full
payload array and a copy-back pass. Sorting the compact tags uses existing
libraries; novelty of the permutation mechanism remains unconfirmed.
[Registered protocol](../../../runs/2026-11-22-checkpoint-cycles/protocol.md)

## Why interleaving is safe

A permutation graph has one incoming and one outgoing edge per vertex. Cutting
the edge entering each saved position breaks every touched cycle into disjoint
open paths rooted at the saved positions. The implementation starts at each
root, copies its next source into the current destination, and advances. Each
non-root source on a path is still original when read: no other path contains
it. At a saved source, read its original backup and stop instead of continuing
into a different path. Saving every root before any write makes the paths safe
in any interleaving. Uncut cycles remain untouched for the scalar fallback.

Marks distinguish completed destinations during the final scan. The tag array
is private scratch, so its marks do not need to be restored. Row movement and
the scan are linear in N; there is no guaranteed minimum speedup and the last
unfinished path can still be latency-bound. Sizes must fit in 31-bit indices.
Non-power-of-two lengths are supported by a power-of-two checkpoint stride.

## Build and run

Use an AVX2-capable CPU and the pinned dependencies prepared as in the
[record-permutation benchmark](../record-permutation/README.md). From the
repository root in PowerShell:

```powershell
$vendor = 'lab/supersort-original/vendor'
g++ -O3 -march=znver3 -mavx2 -DNDEBUG -std=c++20 -Wall -Wextra -Wpedantic `
    -isystem "$vendor" -isystem "$vendor/highway" `
    -isystem "$vendor/x86-simd-sort/src" `
    prototypes/agents/checkpoint-cycles/bench.cpp "$vendor/highway/hwy/abort.cc" `
    -o lab/2026-11-22/checkpoint-cycles.exe
& lab/2026-11-22/checkpoint-cycles.exe --verify
& lab/2026-11-22/checkpoint-cycles.exe 1048576 uniform 48071 5 8
```

Arguments are row count, key distribution (`uniform` or `eight`), seed,
measured rounds and logical CPU. `--verify` exhausts permutations through
length eight and tests arbitrary lengths, long cycles, mixed checkpoint paths,
untouched cycles and complete sorts.

The benchmark's six methods receive the same reusable caller-owned scratch.
Every timed call includes key extraction, sorting and final in-place record
movement, including any copy-back. Its CSV preserves index, materialization and
total time for every verified call. Direct pdqsort's entire operation appears
in the first phase, with zero separately timed materialization.

`run.py` runs the fixed matrix sequentially and refuses to overwrite existing
samples. Recompute results without benchmarking:

```powershell
python -X utf8 runs/2026-11-22-checkpoint-cycles/analyze.py `
    runs/2026-11-22-checkpoint-cycles/raw.csv
```
