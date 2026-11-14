# Record permutation by source band

Experimental single-threaded AVX2 benchmark for applying a stable key-to-row permutation to fixed-size records. See [OP-001](../../../runs/2026-11-14-record-permutation/README.md) for the protocol and result.

The executable needs GCC with C++20, Highway, x86-simd-sort, and the ska_sort header. Use the vendor tree from the [continuity smoke test](../../../runs/2026-11-12-smoke/README.md), or prepare the pinned snapshots with the commands below. The archived ska_sort header has the exact hash recorded in this run.

```powershell
$vendor = 'lab/supersort-original/vendor'
New-Item -ItemType Directory -Force -Path lab/record-permutation | Out-Null
g++ -O3 -march=native -DNDEBUG -std=c++20 -Wall -Wextra -Wpedantic `
    -isystem "$vendor/highway" -isystem "$vendor/x86-simd-sort/src" -isystem $vendor `
    prototypes/agents/record-permutation/bench.cpp "$vendor/highway/hwy/abort.cc" `
    -o lab/record-permutation/bench.exe
& lab/record-permutation/bench.exe 65537 16 5731 0 8
& lab/record-permutation/bench.exe 8388608 16 174630147 5 8
```

For a fresh vendor directory, from the repository root:

```powershell
$vendor = 'lab/supersort-original/vendor'
New-Item -ItemType Directory -Force -Path $vendor | Out-Null
git clone https://github.com/google/highway.git "$vendor/highway"
git -C "$vendor/highway" checkout a3f6f68fcc368e5e3025ca25805eabda9d8a456f
git clone https://github.com/numpy/x86-simd-sort.git "$vendor/x86-simd-sort"
git -C "$vendor/x86-simd-sort" checkout 6e059b14975df2e3c74260ec905167a1be5a34ca
python -c "import subprocess, pathlib; pathlib.Path('lab/supersort-original/vendor/ska_sort.hpp').write_bytes(subprocess.check_output(['git', 'show', '195f578:prior-local/vendor/ska_sort.hpp']))"
```

Arguments are record count, record width, seed, number of measured rounds, and logical CPU. The executable emits CSV. Round 0 is a verified warm-up. Choose a CPU in the process's affinity mask. Build with `RECORD_BENCH_WITH_IPS`, the two IPS include paths, and oneTBB and platform-specific linker flags to attempt the optional IPS baselines where supported.
