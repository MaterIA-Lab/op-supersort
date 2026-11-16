# Prepared inputs and page-aligned merge

Experimental Windows/AVX2 harness for producing two contiguous stable batches and a contiguous combined view. The shifted method calculates a starting offset for each batch before writing it into a pagefile-backed section. It aliases aligned full pages at the ends of the merged virtual range, then copies the remaining rows.

From the repository root with GCC/MinGW-w64 and an AVX2 CPU:

```powershell
New-Item -ItemType Directory -Force -Path lab/producer-page-placement | Out-Null
g++ -O3 -march=native -DNDEBUG -std=c++20 -D_WIN32_WINNT=0x0A00 -Wall -Wextra -Wpedantic `
    prototypes/agents/producer-page-placement/bench.cpp -o lab/producer-page-placement/bench.exe
& lab/producer-page-placement/bench.exe --smoke
& lab/producer-page-placement/bench.exe --bench > lab/producer-page-placement/raw.csv
python runs/2026-11-16-producer-page-placement/analyze.py lab/producer-page-placement/raw.csv
```

The executable pins its sole benchmark thread to logical CPU 8 and requires 4 KiB pages. The timing run emits round zero as a verified warm-up. The [run record](../../../runs/2026-11-16-producer-page-placement/README.md) documents the full contract and the measured result.

On x86-64 Linux with AVX2 and 4 KiB pages, use the same source with the Linux backend:

```sh
mkdir -p lab/producer-page-placement
g++ -O3 -march=native -DNDEBUG -std=c++20 -Wall -Wextra -Wpedantic \
    prototypes/agents/producer-page-placement/bench.cpp -o lab/producer-page-placement/bench
lab/producer-page-placement/bench --smoke
lab/producer-page-placement/bench --bench > lab/producer-page-placement/linux.csv
python3 runs/2026-11-16-linux-producer-placement/analyze.py lab/producer-page-placement/linux.csv
```

The Linux benchmark pins the thread to the highest vCPU allowed by the operating system. The [Linux protocol](../../../runs/2026-11-16-linux-producer-placement/protocol.md) records the fresh seeds, the eager alias variant and the shared output contract.
