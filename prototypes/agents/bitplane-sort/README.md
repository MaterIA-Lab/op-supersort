# Bitplane membership sorting

Experimental stable sorting of independent 32-row groups with uint8 keys and
uint32 payloads in ordinary separate arrays. The candidate transposes keys
into eight membership masks, traverses key prefixes without moving records,
and writes each output row once. It is retained as a negative result, not as a
recommended sorter. [Protocol and results](../../../runs/2026-11-22-bitplane-sort/README.md)

The benchmark also implements a direct AVX2 bitonic network on stable 16-bit
key/position tags, two pinned library sorters on 32-bit tags and stable counting
sort. The network and libraries also move payloads only at materialization.
All methods include encoding, local scratch initialization and final output.

From the repository root in PowerShell, with the dependencies prepared as in
the [record permutation benchmark](../record-permutation/README.md):

```powershell
$vendor = 'lab/supersort-original/vendor'
New-Item -ItemType Directory -Force -Path lab/2026-11-22 | Out-Null
g++ -O3 -march=znver3 -mavx2 -DNDEBUG -std=c++20 -Wall -Wextra -Wpedantic `
    -isystem "$vendor/highway" -isystem "$vendor/x86-simd-sort/src" `
    prototypes/agents/bitplane-sort/bench.cpp "$vendor/highway/hwy/abort.cc" `
    -o lab/2026-11-22/bitplane-sort.exe
& lab/2026-11-22/bitplane-sort.exe --verify
& lab/2026-11-22/bitplane-sort.exe 65536 uniform 104729 7 8
```

Arguments are group count, distribution (`uniform` or `eight`), seed, measured
rounds and logical CPU. All timing samples, including warm-up round zero,
are verified against an independent stable sort. Large cases flush both
input and output lines explicitly before timing. The supplied run used GCC
16.1.0 on a Ryzen 7 5800X, one thread on logical CPU 8, and the pinned reference
revisions in [metadata.json](../../../runs/2026-11-22-bitplane-sort/metadata.json).

`run.py` executes the six registered cells sequentially, writes CSV and hashes,
and refuses to overwrite an existing `raw.csv`. Archive old results locally
before using it for another measurement. To recompute the published table
without rerunning benchmarks:

```powershell
python -X utf8 runs/2026-11-22-bitplane-sort/analyze.py `
    runs/2026-11-22-bitplane-sort/raw.csv
```
