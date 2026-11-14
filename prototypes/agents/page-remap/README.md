# Assemble sorted extents through Windows page mappings

This microbenchmark compares building a contiguous read-only mapping and copying already ordered extents into a contiguous buffer. See [OP-002](../../../runs/2026-11-14-page-remap/README.md) for the input and timing contract, results and raw samples.

Use Windows 10 version 1803 or newer, an x86-64 CPU with AVX2, and GCC with C++20 and current MinGW-w64 headers. Run from the repository root in PowerShell:

```powershell
New-Item -ItemType Directory -Force -Path lab/page-remap | Out-Null
g++ -O3 -march=native -DNDEBUG -std=c++20 -D_WIN32_WINNT=0x0A00 -Wall -Wextra -Wpedantic `
    prototypes/agents/page-remap/bench.cpp -o lab/page-remap/bench.exe
& lab/page-remap/bench.exe 4194304 4096 523 0 8
& lab/page-remap/bench.exe 268435456 65536 40577317 5 8
```

Arguments are total bytes, extent bytes, seed, measured rounds, and logical CPU. Extents must be multiples of 4 KiB, and the total must be a multiple of the extent size. Use a CPU in the process's affinity mask. The executable emits CSV with verified warm-up round 0.
