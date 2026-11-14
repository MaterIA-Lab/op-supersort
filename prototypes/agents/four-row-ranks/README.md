# Stable rank inversion for four-record groups

Each group has four packed 32-bit rows. The high half of each row is the ascending key and the low half is a payload. Ties keep their input order. The candidate computes ranks for two groups per AVX2 register, packs each group's inverse permutation into four bytes, and reorders the original rows. See [OP-003](../../../runs/2026-11-14-four-row-ranks/README.md) for the result and scope.

Use GCC with C++20, an AVX2 CPU and the Highway and x86-simd-sort revisions recorded in the run. The [record permutation benchmark](../record-permutation/README.md) contains commands to prepare both pinned dependencies. From the repository root in PowerShell:

```powershell
$vendor = 'lab/supersort-original/vendor'
New-Item -ItemType Directory -Force -Path lab/four-row-ranks | Out-Null
g++ -O3 -march=native -DNDEBUG -std=c++20 -Wall -Wextra -Wpedantic `
    -isystem "$vendor/highway" -isystem "$vendor/x86-simd-sort/src" `
    prototypes/agents/four-row-ranks/bench.cpp "$vendor/highway/hwy/abort.cc" `
    -o lab/four-row-ranks/bench.exe
& lab/four-row-ranks/bench.exe --verify
& lab/four-row-ranks/bench.exe 1048576 uniform 31876423 7 8
```

Arguments are group count, key distribution, seed, measured repetitions, and logical CPU. Choose a CPU in the process's affinity mask. The CSV includes verified warm-up round 0.
